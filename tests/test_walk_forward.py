"""Tests for walk-forward / OOS validation module."""

import pytest
import pandas as pd

from backtester.data import DataLoader
from backtester.parameter_scan import STRATEGY_SMA, METRIC_TOTAL_RETURN
from backtester.walk_forward import (
    WF_MODE_FIXED,
    WF_MODE_OPTIMIZE,
    WF_WINDOW_ROLLING,
    count_walk_forward_folds,
    iter_walk_forward_slices,
    run_walk_forward,
    stitch_oos_equity_curves,
    validate_walk_forward_config,
    window_length_to_bars,
    aggregate_fold_metrics,
    plot_walk_forward_fold_returns,
    plot_walk_forward_oos_equity,
)


def test_window_length_to_bars_months():
    assert window_length_to_bars(3, "months") == 63


def test_count_folds_rolling():
    n = 500
    train, test, step = 200, 50, 50
    assert count_walk_forward_folds(n, train, test, step, anchored=False) == 6


def test_iter_slices_cover_test_bars():
    loader = DataLoader()
    data = loader.load_csv("data/sample/SPY_sample.csv")
    slices = iter_walk_forward_slices(data, 40, 10, 10, anchored=False)
    assert len(slices) >= 1
    _, train_df, test_df, _, _ = slices[0]
    assert len(train_df) == 40
    assert len(test_df) == 10


def test_validate_rejects_too_many_folds():
    loader = DataLoader()
    data = loader.load_csv("data/sample/SPY_sample.csv")
    ok, msg = validate_walk_forward_config(
        data=data,
        train_bars=20,
        test_bars=5,
        step_bars=1,
        anchored=False,
        mode=WF_MODE_FIXED,
        strategy_type=STRATEGY_SMA,
        param_grid=None,
    )
    if len(data) >= 25 + 5 and count_walk_forward_folds(len(data), 20, 5, 1, False) > 24:
        assert not ok
        assert "folds" in msg.lower() or "折" in msg


def test_run_walk_forward_fixed_on_sample():
    loader = DataLoader()
    data = loader.load_csv("data/sample/SPY_sample.csv")
    ok, _ = validate_walk_forward_config(
        data=data,
        train_bars=40,
        test_bars=10,
        step_bars=20,
        anchored=False,
        mode=WF_MODE_FIXED,
        strategy_type=STRATEGY_SMA,
        param_grid=None,
    )
    assert ok
    result = run_walk_forward(
        data=data,
        strategy_type=STRATEGY_SMA,
        train_bars=40,
        test_bars=10,
        step_bars=20,
        anchored=False,
        mode=WF_MODE_FIXED,
        fixed_params={"fast_period": 10, "slow_period": 30},
        param_grid=None,
        rank_metric="sharpe_ratio",
        initial_capital=10000.0,
        commission=0.001,
        slippage=0.0005,
        position_size=0.95,
    )
    assert not result.folds.empty
    assert f"oos_{METRIC_TOTAL_RETURN}" in result.folds.columns
    assert result.aggregate.get("fold_count") == len(result.folds)
    assert not result.oos_equity.empty


def test_run_walk_forward_optimize_small_grid():
    loader = DataLoader()
    data = loader.load_csv("data/sample/SPY_sample.csv")
    grid = {"fast_period": [5, 10], "slow_period": [20, 30]}
    result = run_walk_forward(
        data=data,
        strategy_type=STRATEGY_SMA,
        train_bars=50,
        test_bars=10,
        step_bars=30,
        anchored=False,
        mode=WF_MODE_OPTIMIZE,
        fixed_params={},
        param_grid=grid,
        rank_metric="sharpe_ratio",
        initial_capital=10000.0,
        commission=0.001,
        slippage=0.0005,
        position_size=0.95,
    )
    assert len(result.folds) >= 1
    assert "fast_period" in result.folds.columns


def test_stitch_oos_equity_compounds():
    idx = pd.date_range("2020-01-01", periods=5, freq="D")
    eq1 = pd.DataFrame({"Equity": [100.0, 110.0]}, index=idx[:2])
    eq2 = pd.DataFrame({"Equity": [100.0, 105.0]}, index=idx[2:4])
    stitched = stitch_oos_equity_curves([eq1, eq2], 100.0)
    assert stitched["Equity"].iloc[-1] == pytest.approx(115.5)


def test_aggregate_fold_metrics():
    df = pd.DataFrame(
        {
            f"oos_{METRIC_TOTAL_RETURN}": [10.0, -5.0],
            "oos_sharpe_ratio": [1.0, 0.5],
            "oos_max_drawdown_pct": [-3.0, -8.0],
        }
    )
    agg = aggregate_fold_metrics(df)
    assert agg["fold_count"] == 2
    assert agg[f"{METRIC_TOTAL_RETURN}_mean"] == 2.5


def test_plot_walk_forward_smoke():
    df = pd.DataFrame({"fold": [1, 2], f"oos_{METRIC_TOTAL_RETURN}": [1.0, 2.0]})
    assert plot_walk_forward_fold_returns(df, theme="light") is not None
    eq = pd.DataFrame({"Equity": [100, 101]}, index=pd.date_range("2020-01-01", periods=2))
    assert plot_walk_forward_oos_equity(eq, theme="dark") is not None
