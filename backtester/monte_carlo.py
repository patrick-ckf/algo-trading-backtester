"""
Monte Carlo / bootstrap uncertainty analysis for completed single-asset backtests.

Post-hoc research layer: resamples observed daily equity returns or trade returns
to explore distribution of summary metrics. Does not alter L0 backtest logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Literal, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from backtester.engine import Trade

MAX_SIMULATIONS = 2000
DEFAULT_SIMULATIONS = 500
MIN_SIMULATIONS = 50

BootstrapSource = Literal["daily_returns", "trade_returns"]

METRIC_TOTAL_RETURN = "total_return_pct"
METRIC_MAX_DRAWDOWN = "max_drawdown_pct"
METRIC_SHARPE = "sharpe_ratio"

METRIC_LABELS: Dict[str, str] = {
    METRIC_TOTAL_RETURN: "終端總回報 / Terminal Total Return",
    METRIC_MAX_DRAWDOWN: "最大回撤 / Max Drawdown",
    METRIC_SHARPE: "夏普比率 / Sharpe Ratio",
}

SOURCE_LABELS: Dict[str, str] = {
    "daily_returns": "日權益報酬重抽樣 / Daily equity return bootstrap",
    "trade_returns": "交易報酬重抽樣 / Trade return bootstrap",
}


def metric_label(metric_key: str) -> str:
    return METRIC_LABELS.get(metric_key, metric_key)


def source_label(source: str) -> str:
    return SOURCE_LABELS.get(source, source)


def _percentile_tails(confidence_level: float) -> Tuple[float, float]:
    """Return lower/upper percentile ranks (0–100) for a two-sided interval."""
    if not 0.5 < confidence_level < 1.0:
        raise ValueError("confidence_level must be between 0.5 and 1.0 (exclusive of 0.5)")
    alpha = (1.0 - confidence_level) / 2.0
    return alpha * 100.0, (1.0 - alpha) * 100.0


def equity_daily_returns(equity: pd.Series) -> np.ndarray:
    """Simple returns from equity levels (drop NaNs)."""
    rets = equity.astype(float).pct_change().dropna().values
    return rets.astype(float)


def trade_return_fractions(trades: List[Trade]) -> np.ndarray:
    """Trade return_pct is stored as percent; convert to decimal returns."""
    if not trades:
        return np.array([], dtype=float)
    return np.array([t.return_pct / 100.0 for t in trades], dtype=float)


def metrics_from_equity_path(
    equity_values: np.ndarray,
    initial_capital: float,
    risk_free_rate: float = 0.0,
) -> Dict[str, float]:
    """Compute terminal return, max drawdown, and Sharpe from a simulated equity path."""
    if len(equity_values) == 0:
        return {
            METRIC_TOTAL_RETURN: 0.0,
            METRIC_MAX_DRAWDOWN: 0.0,
            METRIC_SHARPE: 0.0,
        }

    eq = pd.Series(equity_values.astype(float))
    final_equity = eq.iloc[-1]
    total_return_pct = ((final_equity / initial_capital) - 1.0) * 100.0

    running_max = eq.expanding().max()
    drawdown = (eq - running_max) / running_max * 100.0
    max_drawdown_pct = float(drawdown.min()) if len(drawdown) else 0.0

    daily_returns = eq.pct_change().dropna()
    if len(daily_returns) > 1 and daily_returns.std() != 0:
        excess = daily_returns.mean() - (risk_free_rate / 252.0)
        sharpe = float((excess / daily_returns.std()) * np.sqrt(252))
    else:
        sharpe = 0.0

    return {
        METRIC_TOTAL_RETURN: float(total_return_pct),
        METRIC_MAX_DRAWDOWN: float(max_drawdown_pct),
        METRIC_SHARPE: sharpe,
    }


def _build_equity_from_returns(
    initial_capital: float,
    sampled_returns: np.ndarray,
) -> np.ndarray:
    """Compound sampled simple returns into an equity path (length n+1)."""
    equity = np.empty(len(sampled_returns) + 1, dtype=float)
    equity[0] = initial_capital
    for i, r in enumerate(sampled_returns):
        equity[i + 1] = equity[i] * (1.0 + r)
    return equity


def _sample_returns_iid(
    rng: np.random.Generator,
    pool: np.ndarray,
    n: int,
) -> np.ndarray:
    if pool.size == 0 or n == 0:
        return np.array([], dtype=float)
    indices = rng.integers(0, pool.size, size=n)
    return pool[indices]


def _sample_returns_block(
    rng: np.random.Generator,
    pool: np.ndarray,
    n: int,
    block_size: int,
) -> np.ndarray:
    if pool.size == 0 or n == 0:
        return np.array([], dtype=float)
    block_size = max(1, min(block_size, pool.size))
    out: List[float] = []
    while len(out) < n:
        start = int(rng.integers(0, pool.size))
        for j in range(block_size):
            if len(out) >= n:
                break
            out.append(float(pool[(start + j) % pool.size]))
    return np.array(out[:n], dtype=float)


@dataclass
class BootstrapResult:
    """Container for bootstrap simulation outputs."""

    source: BootstrapSource
    n_simulations: int
    confidence_level: float
    seed: int
    initial_capital: float
    actual_metrics: Dict[str, float]
    metric_samples: pd.DataFrame
    percentile_table: pd.DataFrame
    equity_fan: Optional[pd.DataFrame]
    reference_index: Optional[pd.DatetimeIndex]
    block_size: Optional[int]


def run_bootstrap(
    *,
    equity_curve: pd.DataFrame,
    trades: List[Trade],
    initial_capital: float,
    n_simulations: int = DEFAULT_SIMULATIONS,
    seed: int = 42,
    confidence_level: float = 0.90,
    source: BootstrapSource = "daily_returns",
    block_size: int = 0,
    risk_free_rate: float = 0.0,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> BootstrapResult:
    """
    Bootstrap resampling of observed returns to estimate metric uncertainty.

    Args:
        equity_curve: DataFrame with Equity column (Date index).
        trades: Completed trades from the L0 engine.
        initial_capital: Starting capital used in the backtest.
        n_simulations: Number of bootstrap draws (capped by MAX_SIMULATIONS).
        seed: RNG seed for reproducibility.
        confidence_level: Two-sided interval (e.g. 0.90 → 5th–95th percentiles).
        source: Resample daily equity returns or per-trade returns.
        block_size: If > 1, use block bootstrap on the return pool (daily or trade).
        risk_free_rate: Annual rate for Sharpe on simulated paths.
    """
    if equity_curve.empty or "Equity" not in equity_curve.columns:
        raise ValueError("equity_curve must contain an Equity column")

    n_simulations = int(max(MIN_SIMULATIONS, min(n_simulations, MAX_SIMULATIONS)))
    rng = np.random.default_rng(seed)

    equity = equity_curve["Equity"].astype(float)
    actual_metrics = metrics_from_equity_path(
        equity.values,
        initial_capital,
        risk_free_rate=risk_free_rate,
    )

    if source == "daily_returns":
        pool = equity_daily_returns(equity)
        n_steps = len(pool)
        reference_index = equity.index[1:] if len(equity.index) > 1 else equity.index
    elif source == "trade_returns":
        pool = trade_return_fractions(trades)
        n_steps = len(pool)
        reference_index = None
        if n_steps == 0:
            raise ValueError(
                "No completed trades for trade-return bootstrap; use daily returns or run a backtest with trades."
            )
    else:
        raise ValueError(f"Unknown bootstrap source: {source}")

    if n_steps == 0:
        raise ValueError("Not enough return observations to bootstrap")

    use_block = block_size is not None and int(block_size) > 1
    block_size_int = int(block_size) if use_block else None

    sample_fn = (
        (lambda: _sample_returns_block(rng, pool, n_steps, block_size_int))
        if use_block
        else (lambda: _sample_returns_iid(rng, pool, n_steps))
    )

    rows: List[Dict[str, float]] = []
    fan_matrix = np.zeros((n_simulations, n_steps + 1), dtype=float)

    for sim in range(n_simulations):
        sampled = sample_fn()
        path = _build_equity_from_returns(initial_capital, sampled)
        fan_matrix[sim, :] = path
        m = metrics_from_equity_path(path, initial_capital, risk_free_rate=risk_free_rate)
        m["simulation"] = sim
        rows.append(m)
        if progress_callback is not None:
            progress_callback(sim + 1, n_simulations)

    metric_samples = pd.DataFrame(rows)

    lo_pct, hi_pct = _percentile_tails(confidence_level)
    percentile_rows = []
    for key in (METRIC_TOTAL_RETURN, METRIC_MAX_DRAWDOWN, METRIC_SHARPE):
        samples = metric_samples[key].values
        percentile_rows.append(
            {
                "metric": key,
                "metric_label": metric_label(key),
                "actual": actual_metrics[key],
                "p_lower": float(np.percentile(samples, lo_pct)),
                "p_median": float(np.percentile(samples, 50)),
                "p_upper": float(np.percentile(samples, hi_pct)),
                "lower_pct": lo_pct,
                "upper_pct": hi_pct,
            }
        )
    percentile_table = pd.DataFrame(percentile_rows)

    equity_fan: Optional[pd.DataFrame] = None
    if source == "daily_returns" and len(reference_index) == n_steps:
        # Fan chart uses same calendar as original backtest (descriptive alignment).
        lo = np.percentile(fan_matrix[:, 1:], lo_pct, axis=0)
        med = np.percentile(fan_matrix[:, 1:], 50, axis=0)
        hi = np.percentile(fan_matrix[:, 1:], hi_pct, axis=0)
        equity_fan = pd.DataFrame(
            {
                "p_lower": lo,
                "p_median": med,
                "p_upper": hi,
            },
            index=reference_index,
        )
    elif source == "trade_returns":
        steps = np.arange(n_steps + 1)
        lo = np.percentile(fan_matrix, lo_pct, axis=0)
        med = np.percentile(fan_matrix, 50, axis=0)
        hi = np.percentile(fan_matrix, hi_pct, axis=0)
        equity_fan = pd.DataFrame(
            {"p_lower": lo, "p_median": med, "p_upper": hi},
            index=steps,
        )

    return BootstrapResult(
        source=source,
        n_simulations=n_simulations,
        confidence_level=confidence_level,
        seed=seed,
        initial_capital=initial_capital,
        actual_metrics=actual_metrics,
        metric_samples=metric_samples,
        percentile_table=percentile_table,
        equity_fan=equity_fan,
        reference_index=reference_index if source == "daily_returns" else None,
        block_size=block_size_int,
    )


def plot_bootstrap_histogram(
    metric_samples: pd.DataFrame,
    metric_key: str,
    actual_value: float,
    theme: str = "dark",
) -> go.Figure:
    """Histogram of simulated metric values with vertical line for actual backtest."""
    if theme == "light":
        paper_bg = "#FFFFFF"
        plot_bg = "#F8F9FA"
        font_color = "#1F2937"
        grid_color = "rgba(128,128,128,0.2)"
    else:
        paper_bg = "rgba(0,0,0,0)"
        plot_bg = "rgba(0,0,0,0)"
        font_color = "#FAFAFA"
        grid_color = "rgba(128,128,128,0.15)"

    values = metric_samples[metric_key]
    fig = go.Figure()
    fig.add_trace(
        go.Histogram(
            x=values,
            nbinsx=min(40, max(10, len(values) // 10)),
            name="Bootstrap / 重抽樣",
            marker_color="#2E86DE",
            opacity=0.85,
        )
    )
    fig.add_vline(
        x=actual_value,
        line_dash="dash",
        line_color="#E74C3C",
        annotation_text="實際 / Actual",
        annotation_font_color=font_color,
    )
    fig.update_layout(
        title=dict(
            text=f"Bootstrap 分佈 / Distribution — {metric_label(metric_key)}",
            font=dict(color=font_color),
        ),
        xaxis_title=metric_label(metric_key),
        yaxis_title="次數 / Count",
        template="plotly",
        plot_bgcolor=plot_bg,
        paper_bgcolor=paper_bg,
        font=dict(family="sans-serif", size=12, color=font_color),
        xaxis=dict(color=font_color, gridcolor=grid_color),
        yaxis=dict(color=font_color, gridcolor=grid_color),
        bargap=0.05,
    )
    return fig


def plot_bootstrap_fan(
    equity_fan: pd.DataFrame,
    actual_equity: Optional[pd.Series],
    source: BootstrapSource,
    confidence_level: float,
    theme: str = "dark",
) -> go.Figure:
    """Fan chart of equity confidence bands from bootstrap paths."""
    if theme == "light":
        paper_bg = "#FFFFFF"
        plot_bg = "#F8F9FA"
        font_color = "#1F2937"
        grid_color = "rgba(128,128,128,0.2)"
        band_color = "rgba(46,134,222,0.25)"
    else:
        paper_bg = "rgba(0,0,0,0)"
        plot_bg = "rgba(0,0,0,0)"
        font_color = "#FAFAFA"
        grid_color = "rgba(128,128,128,0.15)"
        band_color = "rgba(46,134,222,0.35)"

    lo_pct, hi_pct = _percentile_tails(confidence_level)
    x = equity_fan.index

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=x,
            y=equity_fan["p_upper"],
            mode="lines",
            line=dict(width=0),
            showlegend=False,
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x,
            y=equity_fan["p_lower"],
            mode="lines",
            fill="tonexty",
            fillcolor=band_color,
            line=dict(width=0),
            name=f"{lo_pct:.0f}–{hi_pct:.0f}% 區間 / band",
            hovertemplate="權益 / Equity: $%{y:,.0f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x,
            y=equity_fan["p_median"],
            mode="lines",
            name="中位數路徑 / Median path",
            line=dict(color="#2E86DE", width=2),
        )
    )

    if actual_equity is not None and not actual_equity.empty:
        fig.add_trace(
            go.Scatter(
                x=actual_equity.index,
                y=actual_equity.values,
                mode="lines",
                name="實際回測 / Actual backtest",
                line=dict(color="#E74C3C", width=2, dash="dash"),
            )
        )

    x_title = (
        "日期 / Date"
        if source == "daily_returns"
        else "交易序號 / Trade sequence"
    )
    fig.update_layout(
        title=dict(
            text="Bootstrap 權益區間 / Equity confidence band",
            font=dict(color=font_color),
        ),
        xaxis_title=x_title,
        yaxis_title="權益 / Equity ($)",
        template="plotly",
        plot_bgcolor=plot_bg,
        paper_bgcolor=paper_bg,
        font=dict(family="sans-serif", size=12, color=font_color),
        xaxis=dict(color=font_color, gridcolor=grid_color),
        yaxis=dict(color=font_color, gridcolor=grid_color),
        hovermode="x unified",
    )
    return fig
