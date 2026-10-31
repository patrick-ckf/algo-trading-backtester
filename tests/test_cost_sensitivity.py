"""Tests for transaction cost sensitivity scan."""

import pandas as pd

from backtester.data import DataLoader
from backtester.cost_sensitivity import (
    MAX_COST_COMBINATIONS,
    METRIC_SHARPE,
    METRIC_TOTAL_RETURN,
    SWEEP_BOTH,
    SWEEP_COMMISSION,
    SWEEP_SLIPPAGE,
    count_cost_combinations,
    float_range_decimals,
    pivot_cost_heatmap,
    plot_cost_heatmap,
    plot_cost_line,
    run_cost_sensitivity_grid,
    validate_cost_grid,
)
from backtester.strategies.sma_crossover import SMACrossover


def test_float_range_decimals_inclusive():
    vals = float_range_decimals(0.0, 0.001, 0.0005)
    assert vals == [0.0, 0.0005, 0.001]


def test_count_cost_combinations_both():
    assert count_cost_combinations(SWEEP_BOTH, [0.0, 0.001], [0.0, 0.0005]) == 4


def test_validate_cost_grid_limit():
    comm = float_range_decimals(0.0, 0.01, 0.0001)
    slip = float_range_decimals(0.0, 0.01, 0.0001)
    ok, msg = validate_cost_grid(SWEEP_BOTH, comm, slip, 0.0, 0.0)
    assert not ok
    assert str(MAX_COST_COMBINATIONS) in msg


def test_run_cost_sensitivity_grid_degrades_with_higher_commission():
    loader = DataLoader()
    data = loader.load_csv("data/sample/SPY_sample.csv")

    def factory():
        return SMACrossover(fast_period=5, slow_period=15)

    df = run_cost_sensitivity_grid(
        data=data,
        strategy_factory=factory,
        sweep_mode=SWEEP_COMMISSION,
        commission_grid=[0.0, 0.005, 0.01],
        slippage_grid=[],
        fixed_commission=0.0,
        fixed_slippage=0.0005,
        initial_capital=10000.0,
        position_size=0.95,
    )
    assert len(df) == 3
    assert METRIC_TOTAL_RETURN in df.columns
    zero_comm = df.loc[df["commission"] == 0.0, METRIC_TOTAL_RETURN].iloc[0]
    high_comm = df.loc[df["commission"] == 0.01, METRIC_TOTAL_RETURN].iloc[0]
    assert zero_comm >= high_comm


def test_pivot_cost_heatmap_2d():
    df = pd.DataFrame(
        {
            "commission_pct": [0.0, 0.0, 0.1, 0.1],
            "slippage_pct": [0.0, 0.05, 0.0, 0.05],
            "commission": [0.0, 0.0, 0.001, 0.001],
            "slippage": [0.0, 0.0005, 0.0, 0.0005],
            METRIC_SHARPE: [1.0, 0.9, 0.8, 0.7],
        }
    )
    pivot = pivot_cost_heatmap(df, METRIC_SHARPE)
    assert pivot is not None
    assert pivot.shape == (2, 2)


def test_plot_cost_charts_smoke():
    df = pd.DataFrame(
        {
            "commission_pct": [0.0, 0.1],
            "slippage_pct": [0.05, 0.05],
            METRIC_SHARPE: [1.0, 0.5],
        }
    )
    pivot = pd.DataFrame([[1.0, 0.5]], index=[0.05], columns=[0.0, 0.1])
    assert plot_cost_heatmap(pivot, METRIC_SHARPE, theme="dark") is not None
    assert plot_cost_line(df, "commission_pct", "x", METRIC_SHARPE, theme="light") is not None


def test_slippage_only_sweep_count():
    assert count_cost_combinations(SWEEP_SLIPPAGE, [], [0.0, 0.0005, 0.001]) == 3
