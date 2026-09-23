"""
Unit tests for performance metrics calculations.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from backtester.metrics import PerformanceMetrics, calculate_buy_and_hold
from backtester.engine import Trade


def create_equity_curve(initial: float, returns: list) -> pd.DataFrame:
    """Create equity curve from returns."""
    dates = pd.date_range("2020-01-01", periods=len(returns), freq="D")
    equity = [initial]
    for ret in returns[1:]:
        equity.append(equity[-1] * (1 + ret))
    return pd.DataFrame({"Equity": equity}, index=dates)


def test_total_return_calculation():
    """Test total return percentage calculation."""
    equity = create_equity_curve(10000, [0, 0.1, 0.05, -0.03, 0.08])
    metrics_calc = PerformanceMetrics(equity, [], 10000)
    metrics = metrics_calc.calculate_all()
    
    final = equity["Equity"].iloc[-1]
    expected_return = ((final / 10000) - 1) * 100
    
    assert abs(metrics["total_return_pct"] - expected_return) < 0.01


def test_max_drawdown_simple():
    """Test max drawdown on simple equity curve."""
    equity = pd.DataFrame({
        "Equity": [100, 110, 105, 90, 95, 100]
    }, index=pd.date_range("2020-01-01", periods=6, freq="D"))
    
    metrics_calc = PerformanceMetrics(equity, [], 100)
    metrics = metrics_calc.calculate_all()
    
    # Peak at 110, trough at 90: (90-110)/110 = -18.18%
    assert metrics["max_drawdown_pct"] < -18
    assert metrics["max_drawdown_pct"] > -19


def test_max_drawdown_no_decline():
    """Test max drawdown when equity only increases."""
    equity = pd.DataFrame({
        "Equity": [100, 105, 110, 115, 120]
    }, index=pd.date_range("2020-01-01", periods=5, freq="D"))
    
    metrics_calc = PerformanceMetrics(equity, [], 100)
    metrics = metrics_calc.calculate_all()
    
    assert metrics["max_drawdown_pct"] == 0.0


def test_cagr_one_year():
    """Test CAGR calculation for approximately one year."""
    # 252 trading days = 1 year
    equity = pd.DataFrame({
        "Equity": [10000] + [10000 * 1.2] * 251
    }, index=pd.date_range("2020-01-01", periods=252, freq="D"))
    
    metrics_calc = PerformanceMetrics(equity, [], 10000)
    metrics = metrics_calc.calculate_all()
    
    # 20% gain over 1 year = 20% CAGR
    assert abs(metrics["cagr_pct"] - 20) < 0.5


def test_sharpe_ratio_calculation():
    """Test Sharpe ratio with known returns."""
    # Create equity with positive returns and low volatility
    np.random.seed(42)
    returns = np.random.normal(0.001, 0.01, 252)
    equity_values = [10000]
    for ret in returns:
        equity_values.append(equity_values[-1] * (1 + ret))
    
    equity = pd.DataFrame({
        "Equity": equity_values
    }, index=pd.date_range("2020-01-01", periods=253, freq="D"))
    
    metrics_calc = PerformanceMetrics(equity, [], 10000, risk_free_rate=0.0)
    metrics = metrics_calc.calculate_all()
    
    assert "sharpe_ratio" in metrics
    assert not np.isnan(metrics["sharpe_ratio"])
    assert not np.isinf(metrics["sharpe_ratio"])


def test_sharpe_ratio_zero_volatility():
    """Test Sharpe ratio when there's no volatility."""
    equity = pd.DataFrame({
        "Equity": [10000] * 100
    }, index=pd.date_range("2020-01-01", periods=100, freq="D"))
    
    metrics_calc = PerformanceMetrics(equity, [], 10000)
    metrics = metrics_calc.calculate_all()
    
    # Zero volatility should give Sharpe of 0
    assert metrics["sharpe_ratio"] == 0.0


def test_win_rate_all_wins():
    """Test win rate with all winning trades."""
    trades = [
        Trade(
            entry_date=pd.Timestamp("2020-01-01"),
            exit_date=pd.Timestamp("2020-01-05"),
            entry_price=100,
            exit_price=110,
            shares=10,
            pnl=100,
            return_pct=10.0
        ) for _ in range(5)
    ]
    
    equity = pd.DataFrame({"Equity": [10000]})
    metrics_calc = PerformanceMetrics(equity, trades, 10000)
    metrics = metrics_calc.calculate_all()
    
    assert metrics["win_rate_pct"] == 100.0
    assert metrics["trade_count"] == 5


def test_win_rate_mixed():
    """Test win rate with mixed winning and losing trades."""
    trades = [
        Trade(
            entry_date=pd.Timestamp("2020-01-01"),
            exit_date=pd.Timestamp("2020-01-05"),
            entry_price=100,
            exit_price=110,
            shares=10,
            pnl=100,
            return_pct=10.0
        ),
        Trade(
            entry_date=pd.Timestamp("2020-01-06"),
            exit_date=pd.Timestamp("2020-01-10"),
            entry_price=100,
            exit_price=95,
            shares=10,
            pnl=-50,
            return_pct=-5.0
        ),
        Trade(
            entry_date=pd.Timestamp("2020-01-11"),
            exit_date=pd.Timestamp("2020-01-15"),
            entry_price=100,
            exit_price=105,
            shares=10,
            pnl=50,
            return_pct=5.0
        ),
    ]
    
    equity = pd.DataFrame({"Equity": [10000]})
    metrics_calc = PerformanceMetrics(equity, trades, 10000)
    metrics = metrics_calc.calculate_all()
    
    # 2 wins out of 3 = 66.67%
    assert abs(metrics["win_rate_pct"] - 66.67) < 0.1
    assert metrics["trade_count"] == 3


def test_no_trades():
    """Test metrics with no trades executed."""
    equity = create_equity_curve(10000, [0, 0.01, 0.02, -0.01])
    metrics_calc = PerformanceMetrics(equity, [], 10000)
    metrics = metrics_calc.calculate_all()
    
    assert metrics["trade_count"] == 0
    assert metrics["win_rate_pct"] == 0.0
    assert metrics["avg_trade_return_pct"] == 0.0


def test_empty_equity_curve():
    """Test metrics with empty equity curve."""
    equity = pd.DataFrame({"Equity": []})
    metrics_calc = PerformanceMetrics(equity, [], 10000)
    metrics = metrics_calc.calculate_all()
    
    assert metrics == {}


def test_avg_trade_return():
    """Test average trade return calculation."""
    trades = [
        Trade(
            entry_date=pd.Timestamp("2020-01-01"),
            exit_date=pd.Timestamp("2020-01-05"),
            entry_price=100,
            exit_price=110,
            shares=10,
            pnl=100,
            return_pct=10.0
        ),
        Trade(
            entry_date=pd.Timestamp("2020-01-06"),
            exit_date=pd.Timestamp("2020-01-10"),
            entry_price=100,
            exit_price=105,
            shares=10,
            pnl=50,
            return_pct=5.0
        ),
    ]
    
    equity = pd.DataFrame({"Equity": [10000]})
    metrics_calc = PerformanceMetrics(equity, trades, 10000)
    metrics = metrics_calc.calculate_all()
    
    # Average of 10% and 5% = 7.5%
    assert abs(metrics["avg_trade_return_pct"] - 7.5) < 0.01


def test_trailing_nan_equity_handling():
    """
    Regression test: equity curve with trailing NaN should not produce nan metrics.
    This simulates the Yahoo Finance bug where Close=NaN on recent dates.
    """
    # Create equity curve with trailing NaN (like the bug scenario)
    equity_values = [10000, 10500, 11000, 11200, np.nan]
    dates = pd.date_range("2020-01-01", periods=5, freq="D")
    equity = pd.DataFrame({"Equity": equity_values}, index=dates)
    
    metrics_calc = PerformanceMetrics(equity, [], 10000)
    metrics = metrics_calc.calculate_all()
    
    # Should use last finite value (11200) not NaN
    assert "final_equity" in metrics
    assert not np.isnan(metrics["final_equity"])
    assert metrics["final_equity"] == 11200
    
    # Total return should be computed from finite value
    assert not np.isnan(metrics["total_return_pct"])
    expected_return = ((11200 / 10000) - 1) * 100
    assert abs(metrics["total_return_pct"] - expected_return) < 0.01
    
    # CAGR should also be finite
    assert not np.isnan(metrics["cagr_pct"])
    assert np.isfinite(metrics["cagr_pct"])


def test_all_nan_equity():
    """Test metrics when all equity values are NaN."""
    equity = pd.DataFrame({
        "Equity": [np.nan, np.nan, np.nan]
    }, index=pd.date_range("2020-01-01", periods=3, freq="D"))
    
    metrics_calc = PerformanceMetrics(equity, [], 10000)
    metrics = metrics_calc.calculate_all()
    
    # Should return empty metrics dict when no finite values
    assert metrics == {}


def test_buy_and_hold_calculation():
    """Test buy-and-hold benchmark calculation."""
    data = pd.DataFrame({
        "Close": [100, 105, 110, 108, 115],
    }, index=pd.date_range("2020-01-01", periods=5, freq="D"))
    
    buy_hold = calculate_buy_and_hold(data, initial_capital=10000, commission=0.0)
    
    assert not buy_hold.empty
    assert "BuyHoldEquity" in buy_hold.columns
    assert len(buy_hold) == len(data)
    
    # Should buy 100 shares at $100 each
    # Final equity should be 100 * 115 = 11500
    assert abs(buy_hold["BuyHoldEquity"].iloc[-1] - 11500) < 1


def test_buy_and_hold_with_commission():
    """Test buy-and-hold with commission applied."""
    data = pd.DataFrame({
        "Close": [100, 110, 120],
    }, index=pd.date_range("2020-01-01", periods=3, freq="D"))
    
    commission = 0.001  # 0.1%
    buy_hold = calculate_buy_and_hold(data, initial_capital=10000, commission=commission)
    
    # After 0.1% commission, can buy 99 shares (9990 / 100)
    # Final equity should be 99 * 120 = 11880
    assert abs(buy_hold["BuyHoldEquity"].iloc[-1] - 11880) < 10


def test_buy_and_hold_empty_data():
    """Test buy-and-hold with empty data."""
    data = pd.DataFrame()
    buy_hold = calculate_buy_and_hold(data, initial_capital=10000, commission=0.0)
    
    assert buy_hold.empty


def test_metrics_with_buy_hold_benchmark():
    """Test metrics calculation includes buy-and-hold comparison."""
    equity = create_equity_curve(10000, [0, 0.1, 0.05, -0.03, 0.08])
    
    data = pd.DataFrame({
        "Close": [100, 105, 110, 108, 115],
    }, index=equity.index)
    
    buy_hold = calculate_buy_and_hold(data, initial_capital=10000, commission=0.0)
    
    metrics_calc = PerformanceMetrics(equity, [], 10000, buy_hold_curve=buy_hold)
    metrics = metrics_calc.calculate_all()
    
    assert "buy_hold_final" in metrics
    assert "buy_hold_return_pct" in metrics
    assert metrics["buy_hold_final"] > 0
    assert metrics["buy_hold_return_pct"] != 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
