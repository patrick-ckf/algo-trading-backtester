"""
Unit tests for performance metrics calculations.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from backtester.metrics import PerformanceMetrics
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
