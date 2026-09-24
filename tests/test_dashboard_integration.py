"""
Integration tests for dashboard functionality.
Tests that the dashboard can properly call the backtesting engine.
"""

import pytest
import pandas as pd
from pathlib import Path
import sys
import os

# Add parent directory to path to import streamlit_app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtester.data import DataLoader
from backtester.engine import BacktestEngine
from backtester.metrics import PerformanceMetrics
from backtester.strategies.sma_crossover import SMACrossover
from backtester.strategies.rsi_mean_reversion import RSIMeanReversion


def test_dashboard_sma_workflow():
    """Test complete SMA backtest workflow as used in dashboard."""
    loader = DataLoader()
    data = loader.load_csv("data/sample/SPY_sample.csv")
    
    strategy = SMACrossover(fast_period=10, slow_period=20)
    
    engine = BacktestEngine(
        initial_capital=10000.0,
        commission=0.001,
        slippage=0.0005,
        position_size_type="fixed_fraction",
        position_size_value=0.95,
    )
    
    equity_curve = engine.run(strategy, data)
    
    assert not equity_curve.empty
    assert "Equity" in equity_curve.columns
    
    metrics_calculator = PerformanceMetrics(
        equity_curve=equity_curve,
        trades=engine.trades,
        initial_capital=10000.0,
    )
    metrics = metrics_calculator.calculate_all()
    
    assert "total_return_pct" in metrics
    assert "cagr_pct" in metrics
    assert "sharpe_ratio" in metrics
    assert "trade_count" in metrics


def test_dashboard_rsi_workflow():
    """Test complete RSI backtest workflow as used in dashboard."""
    loader = DataLoader()
    data = loader.load_csv("data/sample/SPY_sample.csv")
    
    strategy = RSIMeanReversion(period=14, oversold=30, overbought=70)
    
    engine = BacktestEngine(
        initial_capital=10000.0,
        commission=0.001,
        slippage=0.0005,
        position_size_type="fixed_fraction",
        position_size_value=0.95,
    )
    
    equity_curve = engine.run(strategy, data)
    
    assert not equity_curve.empty
    assert "Equity" in equity_curve.columns
    
    metrics_calculator = PerformanceMetrics(
        equity_curve=equity_curve,
        trades=engine.trades,
        initial_capital=10000.0,
    )
    metrics = metrics_calculator.calculate_all()
    
    assert isinstance(metrics, dict)
    assert len(metrics) > 0


def test_trades_dataframe_export():
    """Test that trades can be exported as DataFrame (for CSV download)."""
    loader = DataLoader()
    data = loader.load_csv("data/sample/SPY_sample.csv")
    
    strategy = SMACrossover(fast_period=5, slow_period=10)
    
    engine = BacktestEngine(
        initial_capital=10000.0,
        commission=0.0,
        slippage=0.0,
    )
    
    equity_curve = engine.run(strategy, data)
    trades_df = engine.get_trades_df()
    
    assert isinstance(trades_df, pd.DataFrame)


def test_plot_equity_curve_with_tz_aware_index():
    """
    Test that plot_equity_curve handles timezone-aware equity index
    and naive event dates without TypeError.
    
    Reproduces the bug: equity index from yfinance is tz-aware (America/New_York),
    but calendar/earnings event dates are naive datetime64[us].
    """
    from streamlit_app import plot_equity_curve
    
    # Create tz-aware equity curve (like yfinance returns)
    dates = pd.date_range("2024-01-01", periods=10, freq="D", tz="America/New_York")
    equity_df = pd.DataFrame({
        "Equity": [10000 + i * 100 for i in range(10)]
    }, index=dates)
    
    # Create naive event markers (like calendar CSV parsing)
    event_dates = pd.to_datetime(["2024-01-03", "2024-01-07"])
    event_markers = pd.DataFrame({
        "Date": event_dates,
        "Event": ["CPI Release", "NFP Release"],
        "Type": ["CPI", "NFP"],
        "Country": ["US", "US"]
    })
    
    # Create naive earnings markers
    earnings_dates = pd.to_datetime(["2024-01-05"])
    earnings_markers = pd.DataFrame({
        "Date": earnings_dates,
        "Symbol": ["AAPL"],
        "Event": ["Q4 Earnings"]
    })
    
    # This should not raise TypeError about datetime64 comparison
    try:
        fig = plot_equity_curve(
            equity_df=equity_df,
            event_markers=event_markers,
            earnings_markers=earnings_markers
        )
        # Verify figure was created
        assert fig is not None
        assert len(fig.data) > 0  # Should have at least equity curve trace
    except TypeError as e:
        if "Cannot compare dtypes" in str(e):
            pytest.fail(f"Timezone comparison bug not fixed: {e}")
        raise


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
