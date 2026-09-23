"""
Integration tests for dashboard functionality.
Tests that the dashboard can properly call the backtesting engine.
"""

import pytest
import pandas as pd
from pathlib import Path

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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
