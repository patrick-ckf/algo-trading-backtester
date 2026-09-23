"""
Tests for the backtesting engine.
"""

import pytest
import pandas as pd
import numpy as np

from backtester.engine import BacktestEngine
from backtester.strategy import Strategy, Signal


class SimpleStrategy(Strategy):
    """Test strategy that buys on bar 2 and sells on bar 5."""
    
    def __init__(self):
        super().__init__(name="SimpleTest")
    
    def on_bar(self, index: int, row: pd.Series) -> Signal:
        if index == 2:
            return "BUY"
        elif index == 5:
            return "SELL"
        return "HOLD"


def create_test_data(bars: int = 10) -> pd.DataFrame:
    """Create simple test OHLCV data."""
    dates = pd.date_range("2020-01-01", periods=bars, freq="D")
    data = pd.DataFrame({
        "Open": 100.0,
        "High": 101.0,
        "Low": 99.0,
        "Close": 100.0,
        "Volume": 1000000,
    }, index=dates)
    data.index.name = "Date"
    return data


def test_engine_initialization():
    """Test engine initializes with correct defaults."""
    engine = BacktestEngine(initial_capital=50000.0)
    assert engine.initial_capital == 50000.0
    assert engine.cash == 50000.0
    assert engine.shares == 0


def test_simple_buy_sell():
    """Test basic buy and sell execution."""
    data = create_test_data(bars=10)
    strategy = SimpleStrategy()
    engine = BacktestEngine(
        initial_capital=10000.0,
        commission=0.0,
        slippage=0.0,
        position_size_value=0.9,
    )
    
    equity_curve = engine.run(strategy, data)
    
    assert len(equity_curve) == 10
    assert len(engine.trades) == 1
    
    trade = engine.trades[0]
    assert trade.shares > 0
    assert engine.shares == 0


def test_equity_curve_tracking():
    """Test that equity is tracked correctly."""
    data = create_test_data(bars=10)
    strategy = SimpleStrategy()
    engine = BacktestEngine(initial_capital=10000.0)
    
    equity_curve = engine.run(strategy, data)
    
    assert "Equity" in equity_curve.columns
    assert len(equity_curve) == len(data)
    assert equity_curve["Equity"].iloc[0] > 0


def test_commission_applied():
    """Test that commission reduces equity."""
    data = create_test_data(bars=10)
    strategy = SimpleStrategy()
    
    engine_no_comm = BacktestEngine(
        initial_capital=10000.0,
        commission=0.0,
        slippage=0.0,
    )
    equity_no_comm = engine_no_comm.run(strategy, data)
    
    engine_with_comm = BacktestEngine(
        initial_capital=10000.0,
        commission=0.01,
        slippage=0.0,
    )
    equity_with_comm = engine_with_comm.run(strategy, data)
    
    final_no_comm = equity_no_comm["Equity"].iloc[-1]
    final_with_comm = equity_with_comm["Equity"].iloc[-1]
    
    assert final_with_comm < final_no_comm


def test_no_trades_when_no_signals():
    """Test that no trades execute without signals."""
    
    class HoldStrategy(Strategy):
        def on_bar(self, index: int, row: pd.Series) -> Signal:
            return "HOLD"
    
    data = create_test_data(bars=10)
    strategy = HoldStrategy()
    engine = BacktestEngine(initial_capital=10000.0)
    
    engine.run(strategy, data)
    
    assert len(engine.trades) == 0
    assert engine.shares == 0
    assert engine.cash == 10000.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
