"""
Transaction cost / friction sensitivity for single-asset L0 backtests.

Re-runs the same strategy on OHLCV data under a grid of commission and slippage
assumptions using BacktestEngine (no signal changes). Research layer only.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple, Type

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from backtester.engine import BacktestEngine
from backtester.metrics import PerformanceMetrics, calculate_buy_and_hold
from backtester.parameter_scan import (
    MAX_GRID_COMBINATIONS,
    METRIC_MAX_DRAWDOWN,
    METRIC_SHARPE,
    METRIC_TOTAL_RETURN,
    metric_label,
)
from backtester.strategy import Strategy

MAX_COST_COMBINATIONS = MAX_GRID_COMBINATIONS

SWEEP_BOTH = "both"
SWEEP_COMMISSION = "commission"
SWEEP_SLIPPAGE = "slippage"

SWEEP_MODE_LABELS: Dict[str, str] = {
    SWEEP_BOTH: "佣金 × 滑點 / Commission × Slippage",
    SWEEP_COMMISSION: "僅佣金（滑點固定）/ Commission only (slippage fixed)",
    SWEEP_SLIPPAGE: "僅滑點（佣金固定）/ Slippage only (commission fixed)",
}


def float_range_decimals(start: float, end: float, step: float) -> List[float]:
    """Inclusive decimal range with positive step (rates as decimals, e.g. 0.001 = 0.1%)."""
    if step <= 0:
        raise ValueError("step must be positive")
    if end < start - 1e-12:
        return []
    values: List[float] = []
    n = 0
    while True:
        v = start + n * step
        if v > end + step * 1e-9:
            break
        values.append(round(v, 8))
        n += 1
        if n > 10_000:
            break
    return values


def count_cost_combinations(
    sweep_mode: str,
    commission_grid: Sequence[float],
    slippage_grid: Sequence[float],
) -> int:
    return len(
        list(
            iter_cost_combinations(
                sweep_mode, commission_grid, slippage_grid, 0.0, 0.0
            )
        )
    )


def iter_cost_combinations(
    sweep_mode: str,
    commission_grid: Sequence[float],
    slippage_grid: Sequence[float],
    fixed_commission: float,
    fixed_slippage: float,
) -> Iterable[Tuple[float, float]]:
    """Yield (commission, slippage) decimal pairs for each grid point."""
    if sweep_mode == SWEEP_BOTH:
        for comm in commission_grid:
            for slip in slippage_grid:
                yield float(comm), float(slip)
    elif sweep_mode == SWEEP_COMMISSION:
        for comm in commission_grid:
            yield float(comm), float(fixed_slippage)
    elif sweep_mode == SWEEP_SLIPPAGE:
        for slip in slippage_grid:
            yield float(fixed_commission), float(slip)
    else:
        raise ValueError(f"Unknown sweep mode: {sweep_mode}")


def validate_cost_grid(
    sweep_mode: str,
    commission_grid: Sequence[float],
    slippage_grid: Sequence[float],
    fixed_commission: float,
    fixed_slippage: float,
) -> Tuple[bool, str]:
    n = count_cost_combinations(
        sweep_mode, commission_grid, slippage_grid
    )
    if n == 0:
        return False, (
            "成本網格無有效組合（請檢查範圍與步長）/ "
            "Cost grid has no valid combinations (check range and step)."
        )
    if n > MAX_COST_COMBINATIONS:
        return False, (
            f"成本網格共 {n} 組，超過上限 {MAX_COST_COMBINATIONS}。"
            f"請縮小範圍或加大步長 / Cost grid has {n} points, limit is "
            f"{MAX_COST_COMBINATIONS}. Reduce range or increase step."
        )
    return True, ""


def run_single_cost_point(
    data: pd.DataFrame,
    strategy: Strategy,
    initial_capital: float,
    commission: float,
    slippage: float,
    position_size: float,
) -> Dict[str, Any]:
    """Run one L0 backtest at a commission/slippage assumption."""
    engine = BacktestEngine(
        initial_capital=initial_capital,
        commission=commission,
        slippage=slippage,
        position_size_type="fixed_fraction",
        position_size_value=position_size,
    )
    equity_curve = engine.run(strategy, data)
    buy_hold_curve = calculate_buy_and_hold(
        data=data,
        initial_capital=initial_capital,
        commission=commission,
    )
    calc = PerformanceMetrics(
        equity_curve=equity_curve,
        trades=engine.trades,
        initial_capital=initial_capital,
        buy_hold_curve=buy_hold_curve,
    )
    metrics = calc.calculate_all()
    return {
        "commission": commission,
        "slippage": slippage,
        "commission_pct": commission * 100.0,
        "slippage_pct": slippage * 100.0,
        "trade_count": metrics.get("trade_count", 0),
        METRIC_SHARPE: metrics.get(METRIC_SHARPE, float("nan")),
        METRIC_TOTAL_RETURN: metrics.get(METRIC_TOTAL_RETURN, float("nan")),
        METRIC_MAX_DRAWDOWN: metrics.get(METRIC_MAX_DRAWDOWN, float("nan")),
    }


def run_cost_sensitivity_grid(
    data: pd.DataFrame,
    strategy_factory: Callable[[], Strategy],
    sweep_mode: str,
    commission_grid: Sequence[float],
    slippage_grid: Sequence[float],
    fixed_commission: float,
    fixed_slippage: float,
    initial_capital: float,
    position_size: float,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> pd.DataFrame:
    """
    Sweep commission and/or slippage; strategy signals are recomputed each run
    (OHLCV-only, independent of costs).
    """
    ok, msg = validate_cost_grid(
        sweep_mode,
        commission_grid,
        slippage_grid,
        fixed_commission,
        fixed_slippage,
    )
    if not ok:
        raise ValueError(msg)

    pairs = list(
        iter_cost_combinations(
            sweep_mode,
            commission_grid,
            slippage_grid,
            fixed_commission,
            fixed_slippage,
        )
    )
    total = len(pairs)
    rows: List[Dict[str, Any]] = []
    for i, (comm, slip) in enumerate(pairs):
        if progress_callback:
            progress_callback(i + 1, total)
        strategy = strategy_factory()
        rows.append(
            run_single_cost_point(
                data=data,
                strategy=strategy,
                initial_capital=initial_capital,
                commission=comm,
                slippage=slip,
                position_size=position_size,
            )
        )
    df = pd.DataFrame(rows)
    return df.sort_values(
        by=["commission", "slippage"], ascending=True
    ).reset_index(drop=True)


def pivot_cost_heatmap(
    df: pd.DataFrame,
    metric_key: str,
) -> Optional[pd.DataFrame]:
    """2D pivot when both commission and slippage vary."""
    if df.empty:
        return None
    if df["commission"].nunique() < 2 or df["slippage"].nunique() < 2:
        return None
    pivot = df.pivot_table(
        index="slippage_pct",
        columns="commission_pct",
        values=metric_key,
        aggfunc="first",
    )
    return pivot


def plot_cost_heatmap(
    pivot: pd.DataFrame,
    metric_key: str,
    theme: str = "dark",
) -> go.Figure:
    if theme == "light":
        paper_bg = "#FFFFFF"
        plot_bg = "#F8F9FA"
        font_color = "#1F2937"
    else:
        paper_bg = "rgba(0,0,0,0)"
        plot_bg = "rgba(0,0,0,0)"
        font_color = "#FAFAFA"

    z = pivot.values
    fig = go.Figure(
        data=go.Heatmap(
            z=z,
            x=[f"{c:.3g}%" for c in pivot.columns],
            y=[f"{r:.3g}%" for r in pivot.index],
            colorscale="RdYlGn",
            text=np.round(z, 3),
            texttemplate="%{text}",
            colorbar=dict(title=metric_label(metric_key)),
        )
    )
    fig.update_layout(
        title=dict(
            text=(
                "成本敏感度熱圖 / Cost Sensitivity Heatmap — "
                f"{metric_label(metric_key)}"
            ),
            font=dict(color=font_color),
        ),
        xaxis_title="佣金 / Commission (%)",
        yaxis_title="滑點 / Slippage (%)",
        template="plotly",
        plot_bgcolor=plot_bg,
        paper_bgcolor=paper_bg,
        font=dict(family="sans-serif", size=12, color=font_color),
        xaxis=dict(color=font_color),
        yaxis=dict(color=font_color),
    )
    return fig


def plot_cost_line(
    df: pd.DataFrame,
    x_col: str,
    x_title: str,
    metric_key: str,
    theme: str = "dark",
) -> go.Figure:
    if theme == "light":
        paper_bg = "#FFFFFF"
        plot_bg = "#F8F9FA"
        font_color = "#1F2937"
    else:
        paper_bg = "rgba(0,0,0,0)"
        plot_bg = "rgba(0,0,0,0)"
        font_color = "#FAFAFA"

    plot_df = df.sort_values(by=x_col)
    fig = go.Figure(
        go.Scatter(
            x=plot_df[x_col],
            y=plot_df[metric_key],
            mode="lines+markers",
            line=dict(color="#2E86DE", width=2),
            marker=dict(size=8),
        )
    )
    fig.update_layout(
        title=dict(
            text=(
                "成本敏感度 / Cost Sensitivity — "
                f"{metric_label(metric_key)}"
            ),
            font=dict(color=font_color),
        ),
        xaxis_title=x_title,
        yaxis_title=metric_label(metric_key),
        template="plotly",
        plot_bgcolor=plot_bg,
        paper_bgcolor=paper_bg,
        font=dict(family="sans-serif", size=12, color=font_color),
    )
    return fig
