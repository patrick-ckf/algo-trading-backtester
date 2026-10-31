"""
Parameter grid search for single-asset backtests (research / optimization layer).

Runs independent L0 backtests over a parameter grid. Does not modify the default
backtest path unless the user explicitly enables the scan in the UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple, Type

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from backtester.engine import BacktestEngine
from backtester.metrics import PerformanceMetrics, calculate_buy_and_hold
from backtester.strategy import Strategy
from backtester.strategy_templates import (
    STRATEGY_BOLLINGER,
    STRATEGY_DONCHIAN,
    STRATEGY_MACD,
    STRATEGY_RSI,
    STRATEGY_SMA,
    CUSTOM_TEMPLATE_ID,
)
from backtester.strategies.bollinger_mean_reversion import BollingerMeanReversion
from backtester.strategies.donchian_breakout import DonchianBreakout
from backtester.strategies.macd_crossover import MACDCrossover
from backtester.strategies.rsi_mean_reversion import RSIMeanReversion
from backtester.strategies.sma_crossover import SMACrossover

# Streamlit Cloud: keep total backtests per scan bounded (documented in README/docs).
MAX_GRID_COMBINATIONS = 100

METRIC_SHARPE = "sharpe_ratio"
METRIC_TOTAL_RETURN = "total_return_pct"
METRIC_MAX_DRAWDOWN = "max_drawdown_pct"

RANK_METRIC_OPTIONS: Tuple[str, ...] = (
    METRIC_SHARPE,
    METRIC_TOTAL_RETURN,
    METRIC_MAX_DRAWDOWN,
)

METRIC_LABELS: Dict[str, str] = {
    METRIC_SHARPE: "夏普比率 / Sharpe",
    METRIC_TOTAL_RETURN: "總回報 / Total Return",
    METRIC_MAX_DRAWDOWN: "最大回撤 / Max Drawdown",
}


def metric_label(metric_key: str) -> str:
    return METRIC_LABELS.get(metric_key, metric_key)


def rank_ascending(metric_key: str) -> bool:
    """Whether lower metric values rank better. All supported metrics: higher is better."""
    return False


def arange_params(start: int, end: int, step: int) -> List[int]:
    """Inclusive integer range with positive step."""
    if step <= 0:
        raise ValueError("step must be positive")
    if end < start:
        return []
    values = list(range(int(start), int(end) + 1, int(step)))
    return values


def count_valid_combinations(strategy_type: str, param_grid: Dict[str, Sequence[int]]) -> int:
    """Count combinations that will actually be backtested (after strategy constraints)."""
    return len(list(iter_param_combinations(strategy_type, param_grid)))


def iter_param_combinations(
    strategy_type: str,
    param_grid: Dict[str, Sequence[int]],
) -> Iterable[Dict[str, int]]:
    """Yield parameter dicts for each valid grid point."""
    if strategy_type == STRATEGY_SMA:
        fast_vals = param_grid.get("fast_period", [])
        slow_vals = param_grid.get("slow_period", [])
        for fast in fast_vals:
            for slow in slow_vals:
                if fast < slow:
                    yield {"fast_period": int(fast), "slow_period": int(slow)}
    elif strategy_type == STRATEGY_RSI:
        period_vals = param_grid.get("rsi_period", [])
        oversold_vals = param_grid.get("rsi_oversold", [])
        overbought_vals = param_grid.get("rsi_overbought", [])
        for period in period_vals:
            for oversold in oversold_vals:
                for overbought in overbought_vals:
                    if oversold < overbought:
                        yield {
                            "rsi_period": int(period),
                            "rsi_oversold": int(oversold),
                            "rsi_overbought": int(overbought),
                        }
    elif strategy_type == STRATEGY_DONCHIAN:
        for channel in param_grid.get("channel_period", []):
            yield {"channel_period": int(channel)}
    elif strategy_type == STRATEGY_MACD:
        fast_vals = param_grid.get("fast_period", [])
        slow_vals = param_grid.get("slow_period", [])
        signal_vals = param_grid.get("signal_period", [9])
        for fast in fast_vals:
            for slow in slow_vals:
                if fast < slow:
                    for signal in signal_vals:
                        yield {
                            "fast_period": int(fast),
                            "slow_period": int(slow),
                            "signal_period": int(signal),
                        }
    elif strategy_type == STRATEGY_BOLLINGER:
        period_vals = param_grid.get("bb_period", [])
        std_vals = param_grid.get("bb_std", [])
        for period in period_vals:
            for std in std_vals:
                if std > 0:
                    yield {"bb_period": int(period), "bb_std": float(std)}
    else:
        return


def validate_grid_size(strategy_type: str, param_grid: Dict[str, Sequence[int]]) -> Tuple[bool, str]:
    """Return (ok, message). Message is bilingual-friendly single string."""
    n = count_valid_combinations(strategy_type, param_grid)
    if n == 0:
        return False, (
            "網格無有效組合（請檢查範圍與 fast<slow 等條件）/ "
            "Grid has no valid combinations (check ranges and constraints)."
        )
    if n > MAX_GRID_COMBINATIONS:
        return False, (
            f"網格共 {n} 組，超過上限 {MAX_GRID_COMBINATIONS}。"
            f"請縮小範圍或加大步長 / Grid has {n} points, limit is {MAX_GRID_COMBINATIONS}. "
            "Reduce range or increase step."
        )
    return True, ""


def strategy_class_for_type(strategy_type: str) -> Type[Strategy]:
    if strategy_type == STRATEGY_SMA:
        return SMACrossover
    if strategy_type == STRATEGY_RSI:
        return RSIMeanReversion
    if strategy_type == STRATEGY_DONCHIAN:
        return DonchianBreakout
    if strategy_type == STRATEGY_MACD:
        return MACDCrossover
    if strategy_type == STRATEGY_BOLLINGER:
        return BollingerMeanReversion
    raise ValueError(f"Unknown strategy type: {strategy_type}")


def strategy_kwargs(strategy_type: str, params: Dict[str, int]) -> Dict[str, Any]:
    if strategy_type == STRATEGY_SMA:
        return {
            "fast_period": params["fast_period"],
            "slow_period": params["slow_period"],
        }
    if strategy_type == STRATEGY_RSI:
        return {
            "period": params["rsi_period"],
            "oversold": params["rsi_oversold"],
            "overbought": params["rsi_overbought"],
        }
    if strategy_type == STRATEGY_DONCHIAN:
        return {"channel_period": params["channel_period"]}
    if strategy_type == STRATEGY_MACD:
        return {
            "fast_period": params["fast_period"],
            "slow_period": params["slow_period"],
            "signal_period": params["signal_period"],
        }
    if strategy_type == STRATEGY_BOLLINGER:
        return {
            "bb_period": params["bb_period"],
            "bb_std": params["bb_std"],
        }
    raise ValueError(f"Unknown strategy type: {strategy_type}")


def run_single_backtest_metrics(
    data: pd.DataFrame,
    strategy_type: str,
    params: Dict[str, int],
    initial_capital: float,
    commission: float,
    slippage: float,
    position_size: float,
) -> Dict[str, Any]:
    """Run one L0 backtest and return metrics plus params."""
    strategy_cls = strategy_class_for_type(strategy_type)
    strategy = strategy_cls(**strategy_kwargs(strategy_type, params))
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
    row = {**params}
    row["trade_count"] = metrics.get("trade_count", 0)
    row["win_rate_pct"] = metrics.get("win_rate_pct", 0.0)
    row[METRIC_SHARPE] = metrics.get(METRIC_SHARPE, float("nan"))
    row[METRIC_TOTAL_RETURN] = metrics.get(METRIC_TOTAL_RETURN, float("nan"))
    row[METRIC_MAX_DRAWDOWN] = metrics.get(METRIC_MAX_DRAWDOWN, float("nan"))
    return row


def run_parameter_grid(
    data: pd.DataFrame,
    strategy_type: str,
    param_grid: Dict[str, Sequence[int]],
    initial_capital: float,
    commission: float,
    slippage: float,
    position_size: float,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> pd.DataFrame:
    """
    Run backtests for all valid grid combinations.

    Returns a DataFrame sorted by rank metric is NOT applied here — use rank_grid_results.
    """
    ok, msg = validate_grid_size(strategy_type, param_grid)
    if not ok:
        raise ValueError(msg)

    combos = list(iter_param_combinations(strategy_type, param_grid))
    total = len(combos)
    rows: List[Dict[str, Any]] = []
    for i, params in enumerate(combos):
        if progress_callback:
            progress_callback(i + 1, total)
        rows.append(
            run_single_backtest_metrics(
                data=data,
                strategy_type=strategy_type,
                params=params,
                initial_capital=initial_capital,
                commission=commission,
                slippage=slippage,
                position_size=position_size,
            )
        )
    return pd.DataFrame(rows)


def rank_grid_results(df: pd.DataFrame, rank_metric: str) -> pd.DataFrame:
    """Sort results best-first for the chosen metric."""
    if df.empty or rank_metric not in df.columns:
        return df.copy()
    ascending = rank_ascending(rank_metric)
    ranked = df.sort_values(
        by=rank_metric,
        ascending=ascending,
        na_position="last",
    ).reset_index(drop=True)
    ranked.insert(0, "rank", range(1, len(ranked) + 1))
    return ranked


def pivot_for_heatmap(
    df: pd.DataFrame,
    strategy_type: str,
    rank_metric: str,
) -> Optional[Tuple[pd.DataFrame, str, str]]:
    """
    Build a 2D pivot table for heatmap if exactly two swept dimensions exist.

    Returns (pivot, x_col, y_col) or None if not 2D.
    """
    if strategy_type == STRATEGY_SMA:
        x_col, y_col = "fast_period", "slow_period"
    elif strategy_type == STRATEGY_RSI:
        if "rsi_oversold" in df.columns and df["rsi_oversold"].nunique() > 1:
            x_col, y_col = "rsi_period", "rsi_oversold"
        elif "rsi_overbought" in df.columns and df["rsi_overbought"].nunique() > 1:
            x_col, y_col = "rsi_period", "rsi_overbought"
        else:
            return None
    elif strategy_type == STRATEGY_DONCHIAN:
        return None
    elif strategy_type == STRATEGY_MACD:
        x_col, y_col = "fast_period", "slow_period"
    elif strategy_type == STRATEGY_BOLLINGER:
        x_col, y_col = "bb_period", "bb_std"
    else:
        return None

    if x_col not in df.columns or y_col not in df.columns:
        return None
    if df[x_col].nunique() < 2 or df[y_col].nunique() < 2:
        return None

    pivot = df.pivot_table(
        index=y_col,
        columns=x_col,
        values=rank_metric,
        aggfunc="first",
    )
    return pivot, x_col, y_col


def plot_scan_heatmap(
    pivot: pd.DataFrame,
    x_label: str,
    y_label: str,
    metric_key: str,
    theme: str = "dark",
) -> go.Figure:
    """Theme-adaptive Plotly heatmap for 2D scan results."""
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
            x=[str(c) for c in pivot.columns],
            y=[str(r) for r in pivot.index],
            colorscale="RdYlGn",
            text=np.round(z, 3),
            texttemplate="%{text}",
            colorbar=dict(title=metric_label(metric_key)),
        )
    )
    fig.update_layout(
        title=dict(
            text=f"參數掃描熱圖 / Parameter Scan Heatmap — {metric_label(metric_key)}",
            font=dict(color=font_color),
        ),
        xaxis_title=x_label,
        yaxis_title=y_label,
        template="plotly",
        plot_bgcolor=plot_bg,
        paper_bgcolor=paper_bg,
        font=dict(family="sans-serif", size=12, color=font_color),
        xaxis=dict(color=font_color),
        yaxis=dict(color=font_color),
    )
    return fig


def plot_scan_bar_1d(
    df: pd.DataFrame,
    param_col: str,
    metric_key: str,
    theme: str = "dark",
) -> go.Figure:
    """Bar chart for single-parameter sweeps (e.g. Donchian)."""
    if theme == "light":
        paper_bg = "#FFFFFF"
        plot_bg = "#F8F9FA"
        font_color = "#1F2937"
    else:
        paper_bg = "rgba(0,0,0,0)"
        plot_bg = "rgba(0,0,0,0)"
        font_color = "#FAFAFA"

    sorted_df = rank_grid_results(df, metric_key)
    fig = go.Figure(
        go.Bar(
            x=sorted_df[param_col].astype(str),
            y=sorted_df[metric_key],
            marker_color="#2E86DE",
        )
    )
    fig.update_layout(
        title=dict(
            text=f"參數掃描 / Parameter Scan — {metric_label(metric_key)}",
            font=dict(color=font_color),
        ),
        xaxis_title=param_col,
        yaxis_title=metric_label(metric_key),
        template="plotly",
        plot_bgcolor=plot_bg,
        paper_bgcolor=paper_bg,
        font=dict(family="sans-serif", size=12, color=font_color),
    )
    return fig


def apply_params_to_session(target: Dict[str, Any], strategy_type: str, params: Dict[str, Any]) -> None:
    """Write grid-selected parameters into Streamlit session_state and switch to Custom template."""
    target["strategy_template_picker"] = CUSTOM_TEMPLATE_ID
    target["strategy_type"] = strategy_type
    for key, value in params.items():
        if key.startswith("_"):
            continue
        target[key] = value


def param_columns_for_strategy(strategy_type: str) -> List[str]:
    if strategy_type == STRATEGY_SMA:
        return ["fast_period", "slow_period"]
    if strategy_type == STRATEGY_RSI:
        return ["rsi_period", "rsi_oversold", "rsi_overbought"]
    if strategy_type == STRATEGY_DONCHIAN:
        return ["channel_period"]
    if strategy_type == STRATEGY_MACD:
        return ["fast_period", "slow_period", "signal_period"]
    if strategy_type == STRATEGY_BOLLINGER:
        return ["bb_period", "bb_std"]
    return []
