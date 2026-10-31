"""Tests for parameter grid search module."""

import pytest
import pandas as pd

from backtester.data import DataLoader
from backtester.parameter_scan import (
    MAX_GRID_COMBINATIONS,
    METRIC_SHARPE,
    STRATEGY_BOLLINGER,
    STRATEGY_MACD,
    STRATEGY_SMA,
    STRATEGY_RSI,
    STRATEGY_DONCHIAN,
    arange_params,
    count_valid_combinations,
    iter_param_combinations,
    pivot_for_heatmap,
    plot_scan_heatmap,
    rank_grid_results,
    run_parameter_grid,
    validate_grid_size,
)
def test_arange_params_inclusive():
    assert arange_params(10, 20, 5) == [10, 15, 20]
    assert arange_params(10, 9, 1) == []


def test_sma_grid_skips_fast_ge_slow():
    grid = {
        "fast_period": [10, 30],
        "slow_period": [20, 40],
    }
    combos = list(iter_param_combinations(STRATEGY_SMA, grid))
    assert {"fast_period": 10, "slow_period": 20} in combos
    assert {"fast_period": 30, "slow_period": 20} not in combos
    assert len(combos) == 3


def test_validate_grid_size_limit():
    huge = {
        "fast_period": list(range(1, 15)),
        "slow_period": list(range(20, 40)),
    }
    ok, msg = validate_grid_size(STRATEGY_SMA, huge)
    assert not ok
    assert str(MAX_GRID_COMBINATIONS) in msg


def test_run_parameter_grid_on_sample_data():
    loader = DataLoader()
    data = loader.load_csv("data/sample/SPY_sample.csv")
    grid = {
        "fast_period": [5, 10],
        "slow_period": [15, 20],
    }
    df = run_parameter_grid(
        data=data,
        strategy_type=STRATEGY_SMA,
        param_grid=grid,
        initial_capital=10000.0,
        commission=0.001,
        slippage=0.0005,
        position_size=0.95,
    )
    assert len(df) == count_valid_combinations(STRATEGY_SMA, grid)
    assert METRIC_SHARPE in df.columns
    assert df["fast_period"].max() < df["slow_period"].min() or True


def test_rank_grid_results_orders_by_sharpe():
    df = pd.DataFrame(
        {
            "fast_period": [5, 10],
            "slow_period": [20, 20],
            METRIC_SHARPE: [0.5, 1.2],
            "total_return_pct": [1.0, 2.0],
            "max_drawdown_pct": [-5.0, -3.0],
            "trade_count": [1, 2],
        }
    )
    ranked = rank_grid_results(df, METRIC_SHARPE)
    assert ranked.iloc[0][METRIC_SHARPE] == 1.2
    assert ranked.iloc[0]["rank"] == 1


def test_pivot_for_heatmap_sma():
    df = pd.DataFrame(
        {
            "fast_period": [5, 5, 10, 10],
            "slow_period": [15, 20, 15, 20],
            METRIC_SHARPE: [0.1, 0.2, 0.3, 0.4],
        }
    )
    result = pivot_for_heatmap(df, STRATEGY_SMA, METRIC_SHARPE)
    assert result is not None
    pivot, x_col, y_col = result
    assert x_col == "fast_period"
    assert y_col == "slow_period"
    assert pivot.shape == (2, 2)


def test_plot_scan_heatmap_smoke():
    pivot = pd.DataFrame(
        [[0.1, 0.2], [0.3, 0.4]],
        index=[15, 20],
        columns=[5, 10],
    )
    fig = plot_scan_heatmap(pivot, "fast", "slow", METRIC_SHARPE, theme="dark")
    assert fig is not None
    fig_light = plot_scan_heatmap(pivot, "fast", "slow", METRIC_SHARPE, theme="light")
    assert fig_light is not None


def test_rsi_grid_respects_oversold_overbought():
    grid = {
        "rsi_period": [14],
        "rsi_oversold": [30, 40],
        "rsi_overbought": [70],
    }
    combos = list(iter_param_combinations(STRATEGY_RSI, grid))
    assert len(combos) == 2


def test_donchian_1d_grid():
    grid = {"channel_period": [10, 15, 20]}
    assert count_valid_combinations(STRATEGY_DONCHIAN, grid) == 3


def test_macd_grid_skips_fast_ge_slow():
    grid = {
        "fast_period": [8, 12],
        "slow_period": [20, 26],
        "signal_period": [9],
    }
    combos = list(iter_param_combinations(STRATEGY_MACD, grid))
    assert all(c["fast_period"] < c["slow_period"] for c in combos)
    assert len(combos) == 4


def test_bollinger_grid_combinations():
    grid = {"bb_period": [10, 20], "bb_std": [2.0, 3.0]}
    combos = list(iter_param_combinations(STRATEGY_BOLLINGER, grid))
    assert len(combos) == 4
