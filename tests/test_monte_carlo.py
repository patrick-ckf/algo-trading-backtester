"""
Unit tests for Monte Carlo / bootstrap post-hoc analysis.
"""

import numpy as np
import pandas as pd
import pytest

from backtester.engine import BacktestEngine, Trade
from backtester.metrics import PerformanceMetrics
from backtester.monte_carlo import (
    DEFAULT_SIMULATIONS,
    METRIC_MAX_DRAWDOWN,
    METRIC_SHARPE,
    METRIC_TOTAL_RETURN,
    run_bootstrap,
    metrics_from_equity_path,
)
from backtester.strategies.sma_crossover import SMACrossover
from backtester.data import DataLoader


def _load_sample_data():
    loader = DataLoader()
    return loader.load_csv("data/sample/SPY_sample.csv")


def test_bootstrap_reproducible_with_seed():
    data = _load_sample_data()
    engine = BacktestEngine(initial_capital=100_000)
    equity = engine.run(SMACrossover(fast_period=10, slow_period=30), data)

    r1 = run_bootstrap(
        equity_curve=equity,
        trades=engine.trades,
        initial_capital=100_000,
        n_simulations=200,
        seed=12345,
        confidence_level=0.90,
        source="daily_returns",
    )
    r2 = run_bootstrap(
        equity_curve=equity,
        trades=engine.trades,
        initial_capital=100_000,
        n_simulations=200,
        seed=12345,
        confidence_level=0.90,
        source="daily_returns",
    )

    pd.testing.assert_frame_equal(
        r1.metric_samples.reset_index(drop=True),
        r2.metric_samples.reset_index(drop=True),
    )
    pd.testing.assert_frame_equal(r1.percentile_table, r2.percentile_table)


def test_bootstrap_percentile_table_contains_actual():
    data = _load_sample_data()
    engine = BacktestEngine(initial_capital=50_000)
    equity = engine.run(SMACrossover(fast_period=5, slow_period=20), data)

    pm = PerformanceMetrics(equity, engine.trades, 50_000)
    actual = pm.calculate_all()

    result = run_bootstrap(
        equity_curve=equity,
        trades=engine.trades,
        initial_capital=50_000,
        n_simulations=150,
        seed=99,
        source="daily_returns",
    )

    row = result.percentile_table[
        result.percentile_table["metric"] == METRIC_TOTAL_RETURN
    ].iloc[0]
    assert abs(row["actual"] - actual["total_return_pct"]) < 1e-6
    assert row["p_lower"] <= row["p_median"] <= row["p_upper"]


def test_bootstrap_trade_returns_requires_trades():
    equity = pd.DataFrame(
        {"Equity": [100_000, 100_500, 101_000]},
        index=pd.date_range("2020-01-01", periods=3, freq="D"),
    )
    with pytest.raises(ValueError, match="No completed trades"):
        run_bootstrap(
            equity_curve=equity,
            trades=[],
            initial_capital=100_000,
            n_simulations=100,
            seed=1,
            source="trade_returns",
        )


def test_bootstrap_trade_returns_fixed_metrics_snapshot():
    """Regression guard: fixed seed + synthetic trades → stable percentiles."""
    trades = [
        Trade(
            entry_date=pd.Timestamp("2020-01-01"),
            exit_date=pd.Timestamp("2020-01-05"),
            entry_price=100.0,
            exit_price=105.0,
            shares=10,
            pnl=50.0,
            return_pct=5.0,
        ),
        Trade(
            entry_date=pd.Timestamp("2020-02-01"),
            exit_date=pd.Timestamp("2020-02-10"),
            entry_price=100.0,
            exit_price=98.0,
            shares=10,
            pnl=-20.0,
            return_pct=-2.0,
        ),
        Trade(
            entry_date=pd.Timestamp("2020-03-01"),
            exit_date=pd.Timestamp("2020-03-15"),
            entry_price=100.0,
            exit_price=110.0,
            shares=10,
            pnl=100.0,
            return_pct=10.0,
        ),
    ]
    equity = pd.DataFrame(
        {"Equity": np.linspace(100_000, 112_000, 20)},
        index=pd.date_range("2020-01-01", periods=20, freq="D"),
    )

    result = run_bootstrap(
        equity_curve=equity,
        trades=trades,
        initial_capital=100_000,
        n_simulations=500,
        seed=2026,
        confidence_level=0.90,
        source="trade_returns",
    )

    total_row = result.percentile_table[
        result.percentile_table["metric"] == METRIC_TOTAL_RETURN
    ].iloc[0]
    # Known snapshot from implementation (trade compounding bootstrap)
    assert abs(total_row["p_median"] - 13.190000000000012) < 1e-9
    assert result.n_simulations == 500
    assert len(result.metric_samples) == 500


def test_metrics_from_equity_path_matches_performance_metrics():
    data = _load_sample_data().head(100)
    engine = BacktestEngine(initial_capital=100_000)
    equity = engine.run(SMACrossover(fast_period=8, slow_period=25), data)

    pm = PerformanceMetrics(equity, engine.trades, 100_000).calculate_all()
    direct = metrics_from_equity_path(equity["Equity"].values, 100_000)

    assert abs(direct[METRIC_TOTAL_RETURN] - pm["total_return_pct"]) < 1e-4
    assert abs(direct[METRIC_MAX_DRAWDOWN] - pm["max_drawdown_pct"]) < 1e-4
    assert abs(direct[METRIC_SHARPE] - pm["sharpe_ratio"]) < 1e-4


def test_default_simulation_count_constant():
    assert DEFAULT_SIMULATIONS == 500
