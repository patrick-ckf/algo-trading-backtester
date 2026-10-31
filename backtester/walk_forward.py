"""
Walk-forward / out-of-sample validation for single-asset backtests (research layer).

Splits history into train/test folds, optionally optimizes on in-sample data using the
same parameter grid as parameter_scan, then evaluates on held-out bars via L0 backtests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import pandas as pd
import plotly.graph_objects as go

from backtester.parameter_scan import (
    METRIC_MAX_DRAWDOWN,
    METRIC_SHARPE,
    METRIC_TOTAL_RETURN,
    MAX_GRID_COMBINATIONS,
    metric_label,
    param_columns_for_strategy,
    rank_grid_results,
    run_parameter_grid,
    validate_grid_size,
)
from backtester.strategy_templates import (
    STRATEGY_BOLLINGER,
    STRATEGY_DONCHIAN,
    STRATEGY_MACD,
    STRATEGY_RSI,
    STRATEGY_SMA,
)

# Streamlit Cloud: cap folds and per-fold grid work (documented in docs/WALK-FORWARD.md).
MAX_WALK_FORWARD_FOLDS = 24
TRADING_DAYS_PER_MONTH = 21

WF_MODE_FIXED = "fixed"
WF_MODE_OPTIMIZE = "optimize"

WINDOW_UNIT_BARS = "bars"
WINDOW_UNIT_MONTHS = "months"

WF_WINDOW_ROLLING = "rolling"
WF_WINDOW_ANCHORED = "anchored"

OOS_METRIC_COLUMNS: Tuple[str, ...] = (
    METRIC_TOTAL_RETURN,
    METRIC_SHARPE,
    METRIC_MAX_DRAWDOWN,
    "win_rate_pct",
    "trade_count",
)


def window_length_to_bars(length: int, unit: str) -> int:
    """Convert user window length to bar count."""
    if length <= 0:
        raise ValueError("window length must be positive")
    if unit == WINDOW_UNIT_BARS:
        return int(length)
    if unit == WINDOW_UNIT_MONTHS:
        return int(length) * TRADING_DAYS_PER_MONTH
    raise ValueError(f"Unknown window unit: {unit}")


def count_walk_forward_folds(
    n_bars: int,
    train_bars: int,
    test_bars: int,
    step_bars: int,
    anchored: bool,
) -> int:
    """Return number of folds that would be generated (0 if insufficient data)."""
    if n_bars < train_bars + test_bars:
        return 0
    if anchored:
        # First test starts after train_bars; train window grows each step.
        first_test_start = train_bars
        remaining = n_bars - first_test_start - test_bars
        if remaining < 0:
            return 0
        return 1 + (remaining // step_bars)
    start = 0
    count = 0
    while start + train_bars + test_bars <= n_bars:
        count += 1
        start += step_bars
    return count


def iter_walk_forward_slices(
    data: pd.DataFrame,
    train_bars: int,
    test_bars: int,
    step_bars: int,
    anchored: bool,
) -> List[Tuple[int, pd.DataFrame, pd.DataFrame, pd.Timestamp, pd.Timestamp]]:
    """
    Yield fold index and train/test DataFrame slices.

    Returns list of (fold_idx, train_df, test_df, test_start, test_end).
    """
    n = len(data)
    folds: List[Tuple[int, pd.DataFrame, pd.DataFrame, pd.Timestamp, pd.Timestamp]] = []
    if train_bars <= 0 or test_bars <= 0 or step_bars <= 0:
        return folds

    if anchored:
        test_start_idx = train_bars
        fold_idx = 0
        while test_start_idx + test_bars <= n:
            train_df = data.iloc[0:test_start_idx]
            test_df = data.iloc[test_start_idx : test_start_idx + test_bars]
            folds.append(
                (
                    fold_idx,
                    train_df,
                    test_df,
                    test_df.index[0],
                    test_df.index[-1],
                )
            )
            fold_idx += 1
            test_start_idx += step_bars
        return folds

    start = 0
    fold_idx = 0
    while start + train_bars + test_bars <= n:
        train_df = data.iloc[start : start + train_bars]
        test_df = data.iloc[start + train_bars : start + train_bars + test_bars]
        folds.append(
            (
                fold_idx,
                train_df,
                test_df,
                test_df.index[0],
                test_df.index[-1],
            )
        )
        fold_idx += 1
        start += step_bars
    return folds


def validate_walk_forward_config(
    data: pd.DataFrame,
    train_bars: int,
    test_bars: int,
    step_bars: int,
    anchored: bool,
    mode: str,
    strategy_type: str,
    param_grid: Optional[Dict[str, Sequence[int]]],
) -> Tuple[bool, str]:
    """Return (ok, bilingual-friendly message)."""
    n = len(data)
    if train_bars < 10:
        return False, (
            "訓練窗口太短（至少 10 根 K 線）/ Train window too short (min 10 bars)."
        )
    if test_bars < 5:
        return False, (
            "測試窗口太短（至少 5 根 K 線）/ Test window too short (min 5 bars)."
        )
    if step_bars <= 0:
        return False, "步長須為正 / Step size must be positive."

    n_folds = count_walk_forward_folds(n, train_bars, test_bars, step_bars, anchored)
    if n_folds == 0:
        return False, (
            "數據長度不足以形成一個折（請縮短窗口或加長序列）/ "
            "Not enough bars for one fold (shorten windows or use more data)."
        )
    if n_folds > MAX_WALK_FORWARD_FOLDS:
        return False, (
            f"折數 {n_folds} 超過上限 {MAX_WALK_FORWARD_FOLDS}；"
            f"請加大步長或縮短範圍 / "
            f"{n_folds} folds exceeds limit {MAX_WALK_FORWARD_FOLDS}; "
            "increase step or shorten windows."
        )

    if mode == WF_MODE_OPTIMIZE:
        if not param_grid:
            return False, (
                "優化模式需要參數網格 / Optimize mode requires a parameter grid."
            )
        ok, msg = validate_grid_size(strategy_type, param_grid)
        if not ok:
            return False, msg

    return True, ""


def sidebar_fixed_params(
    strategy_type: str,
    fast_period: int,
    slow_period: int,
    rsi_period: int,
    rsi_oversold: int,
    rsi_overbought: int,
    channel_period: int,
    signal_period: int = 9,
    bb_period: int = 20,
    bb_std: float = 2.0,
) -> Dict[str, Any]:
    """Map sidebar strategy fields to parameter_scan grid keys."""
    if strategy_type == STRATEGY_SMA:
        return {"fast_period": int(fast_period), "slow_period": int(slow_period)}
    if strategy_type == STRATEGY_RSI:
        return {
            "rsi_period": int(rsi_period),
            "rsi_oversold": int(rsi_oversold),
            "rsi_overbought": int(rsi_overbought),
        }
    if strategy_type == STRATEGY_DONCHIAN:
        return {"channel_period": int(channel_period)}
    if strategy_type == STRATEGY_MACD:
        return {
            "fast_period": int(fast_period),
            "slow_period": int(slow_period),
            "signal_period": int(signal_period),
        }
    if strategy_type == STRATEGY_BOLLINGER:
        return {"bb_period": int(bb_period), "bb_std": float(bb_std)}
    return {}


def _oos_metrics_from_equity(
    equity_curve: pd.DataFrame,
    trades: List[Any],
    test_data: pd.DataFrame,
    initial_capital: float,
    commission: float,
) -> Dict[str, Any]:
    from backtester.metrics import PerformanceMetrics, calculate_buy_and_hold

    buy_hold = calculate_buy_and_hold(test_data, initial_capital, commission)
    calc = PerformanceMetrics(
        equity_curve=equity_curve,
        trades=trades,
        initial_capital=initial_capital,
        buy_hold_curve=buy_hold,
    )
    return calc.calculate_all()


def evaluate_oos_fold(
    test_data: pd.DataFrame,
    strategy_type: str,
    params: Dict[str, int],
    initial_capital: float,
    commission: float,
    slippage: float,
    position_size: float,
) -> Tuple[Dict[str, Any], pd.DataFrame]:
    """Run one OOS backtest; return metrics dict and equity curve."""
    from backtester.engine import BacktestEngine
    from backtester.parameter_scan import strategy_class_for_type, strategy_kwargs

    strategy_cls = strategy_class_for_type(strategy_type)
    strategy = strategy_cls(**strategy_kwargs(strategy_type, params))
    engine = BacktestEngine(
        initial_capital=initial_capital,
        commission=commission,
        slippage=slippage,
        position_size_type="fixed_fraction",
        position_size_value=position_size,
    )
    equity_curve = engine.run(strategy, test_data)
    metrics = _oos_metrics_from_equity(
        equity_curve, engine.trades, test_data, initial_capital, commission
    )
    return metrics, equity_curve


def _select_in_sample_params(
    train_data: pd.DataFrame,
    strategy_type: str,
    param_grid: Dict[str, Sequence[int]],
    rank_metric: str,
    initial_capital: float,
    commission: float,
    slippage: float,
    position_size: float,
) -> Dict[str, int]:
    grid_df = run_parameter_grid(
        data=train_data,
        strategy_type=strategy_type,
        param_grid=param_grid,
        initial_capital=initial_capital,
        commission=commission,
        slippage=slippage,
        position_size=position_size,
    )
    ranked = rank_grid_results(grid_df, rank_metric)
    if ranked.empty:
        raise ValueError("In-sample grid produced no results.")
    best = ranked.iloc[0]
    params: Dict[str, int] = {}
    for col in param_columns_for_strategy(strategy_type):
        params[col] = int(best[col])
    return params


def stitch_oos_equity_curves(
    equity_pieces: List[pd.DataFrame],
    initial_capital: float,
) -> pd.DataFrame:
    """Chain OOS test-window equity curves with compounding capital."""
    if not equity_pieces:
        return pd.DataFrame()

    segments: List[pd.Series] = []
    capital = float(initial_capital)
    for eq in equity_pieces:
        if eq.empty or "Equity" not in eq.columns:
            continue
        first = eq["Equity"].iloc[0]
        if first <= 0 or pd.isna(first):
            continue
        scale = capital / first
        scaled = eq["Equity"] * scale
        segments.append(scaled)
        capital = float(scaled.iloc[-1])

    if not segments:
        return pd.DataFrame()

    combined = pd.concat(segments)
    return pd.DataFrame({"Equity": combined}, index=combined.index)


@dataclass
class WalkForwardResult:
    mode: str
    folds: pd.DataFrame = field(default_factory=pd.DataFrame)
    aggregate: Dict[str, Any] = field(default_factory=dict)
    oos_equity: pd.DataFrame = field(default_factory=pd.DataFrame)


def aggregate_fold_metrics(folds_df: pd.DataFrame) -> Dict[str, Any]:
    """Summary stats across OOS folds (descriptive only — not significance testing)."""
    if folds_df.empty:
        return {}

    agg: Dict[str, Any] = {"fold_count": len(folds_df)}

    for col in OOS_METRIC_COLUMNS:
        oos_col = f"oos_{col}"
        if oos_col not in folds_df.columns:
            continue
        series = pd.to_numeric(folds_df[oos_col], errors="coerce")
        agg[f"{col}_mean"] = float(series.mean())
        agg[f"{col}_median"] = float(series.median())

    if f"oos_{METRIC_TOTAL_RETURN}" in folds_df.columns:
        rets = (
            pd.to_numeric(folds_df[f"oos_{METRIC_TOTAL_RETURN}"], errors="coerce") / 100.0
        )
        compound = float((1 + rets.fillna(0)).prod() - 1) * 100.0
        agg["compound_oos_return_pct"] = compound

    if f"oos_{METRIC_MAX_DRAWDOWN}" in folds_df.columns:
        dd = pd.to_numeric(folds_df[f"oos_{METRIC_MAX_DRAWDOWN}"], errors="coerce")
        agg["worst_fold_max_drawdown_pct"] = float(dd.min())

    return agg


def run_walk_forward(
    data: pd.DataFrame,
    strategy_type: str,
    *,
    train_bars: int,
    test_bars: int,
    step_bars: int,
    anchored: bool,
    mode: str,
    fixed_params: Dict[str, int],
    param_grid: Optional[Dict[str, Sequence[int]]],
    rank_metric: str,
    initial_capital: float,
    commission: float,
    slippage: float,
    position_size: float,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> WalkForwardResult:
    """
    Execute walk-forward validation.

    mode: WF_MODE_FIXED (sidebar params each fold) or WF_MODE_OPTIMIZE (grid on train, OOS test).
    """
    ok, msg = validate_walk_forward_config(
        data=data,
        train_bars=train_bars,
        test_bars=test_bars,
        step_bars=step_bars,
        anchored=anchored,
        mode=mode,
        strategy_type=strategy_type,
        param_grid=param_grid,
    )
    if not ok:
        raise ValueError(msg)

    slices = iter_walk_forward_slices(
        data, train_bars, test_bars, step_bars, anchored
    )
    total = len(slices)
    rows: List[Dict[str, Any]] = []
    oos_equity_pieces: List[pd.DataFrame] = []

    for i, (fold_idx, train_df, test_df, test_start, test_end) in enumerate(slices):
        if progress_callback:
            progress_callback(i + 1, total)

        if mode == WF_MODE_OPTIMIZE:
            assert param_grid is not None
            chosen = _select_in_sample_params(
                train_data=train_df,
                strategy_type=strategy_type,
                param_grid=param_grid,
                rank_metric=rank_metric,
                initial_capital=initial_capital,
                commission=commission,
                slippage=slippage,
                position_size=position_size,
            )
        else:
            chosen = dict(fixed_params)

        oos_metrics, oos_equity = evaluate_oos_fold(
            test_data=test_df,
            strategy_type=strategy_type,
            params=chosen,
            initial_capital=initial_capital,
            commission=commission,
            slippage=slippage,
            position_size=position_size,
        )

        fold_record: Dict[str, Any] = {
            "fold": fold_idx + 1,
            "train_bars": len(train_df),
            "test_bars": len(test_df),
            "test_start": test_start,
            "test_end": test_end,
        }
        for col in param_columns_for_strategy(strategy_type):
            fold_record[col] = chosen.get(col)
        for col in OOS_METRIC_COLUMNS:
            fold_record[f"oos_{col}"] = oos_metrics.get(col)

        rows.append(fold_record)
        oos_equity_pieces.append(oos_equity)

    folds_df = pd.DataFrame(rows)
    oos_equity = stitch_oos_equity_curves(oos_equity_pieces, initial_capital)
    aggregate = aggregate_fold_metrics(folds_df)

    return WalkForwardResult(
        mode=mode,
        folds=folds_df,
        aggregate=aggregate,
        oos_equity=oos_equity,
    )


def mode_label(mode: str) -> str:
    if mode == WF_MODE_OPTIMIZE:
        return "訓練期優化 + 樣本外測試 / In-sample optimize + OOS test"
    return "固定參數樣本外 / Fixed-params OOS"


def plot_walk_forward_fold_returns(
    folds_df: pd.DataFrame,
    theme: str = "dark",
) -> go.Figure:
    """Bar chart of OOS total return per fold."""
    if theme == "light":
        paper_bg = "#FFFFFF"
        plot_bg = "#F8F9FA"
        font_color = "#1F2937"
    else:
        paper_bg = "rgba(0,0,0,0)"
        plot_bg = "rgba(0,0,0,0)"
        font_color = "#FAFAFA"

    col = f"oos_{METRIC_TOTAL_RETURN}"
    if col not in folds_df.columns:
        col = METRIC_TOTAL_RETURN

    fig = go.Figure(
        go.Bar(
            x=folds_df["fold"].astype(str),
            y=folds_df[col],
            marker_color="#27AE60",
            name="OOS Return %",
        )
    )
    fig.update_layout(
        title=dict(
            text="各折樣本外總回報 / OOS Total Return by Fold",
            font=dict(color=font_color),
        ),
        xaxis_title="折 / Fold",
        yaxis_title=metric_label(METRIC_TOTAL_RETURN),
        template="plotly",
        plot_bgcolor=plot_bg,
        paper_bgcolor=paper_bg,
        font=dict(family="sans-serif", size=12, color=font_color),
    )
    return fig


def plot_walk_forward_oos_equity(
    oos_equity: pd.DataFrame,
    theme: str = "dark",
) -> go.Figure:
    """Line chart of stitched OOS equity."""
    if theme == "light":
        paper_bg = "#FFFFFF"
        plot_bg = "#F8F9FA"
        font_color = "#1F2937"
        line_color = "#2E86DE"
    else:
        paper_bg = "rgba(0,0,0,0)"
        plot_bg = "rgba(0,0,0,0)"
        font_color = "#FAFAFA"
        line_color = "#54A0FF"

    fig = go.Figure()
    if not oos_equity.empty and "Equity" in oos_equity.columns:
        fig.add_trace(
            go.Scatter(
                x=oos_equity.index,
                y=oos_equity["Equity"],
                mode="lines",
                name="OOS Equity",
                line=dict(color=line_color, width=2),
            )
        )
    fig.update_layout(
        title=dict(
            text="拼接樣本外權益曲線 / Stitched OOS Equity",
            font=dict(color=font_color),
        ),
        xaxis_title="Date",
        yaxis_title="Equity",
        template="plotly",
        plot_bgcolor=plot_bg,
        paper_bgcolor=paper_bg,
        font=dict(family="sans-serif", size=12, color=font_color),
        hovermode="x unified",
    )
    return fig
