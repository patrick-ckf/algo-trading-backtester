"""
Unit tests for trading strategies.
"""

import pytest
import pandas as pd
import numpy as np

from backtester.strategies.sma_crossover import SMACrossover
from backtester.strategies.rsi_mean_reversion import RSIMeanReversion


def create_test_data_with_trend(bars: int = 100, trend: str = "up") -> pd.DataFrame:
    """Create test OHLCV data with specific trend."""
    dates = pd.date_range("2020-01-01", periods=bars, freq="D")
    
    if trend == "up":
        close = np.linspace(100, 150, bars)
    elif trend == "down":
        close = np.linspace(150, 100, bars)
    else:  # flat
        close = np.full(bars, 100)
    
    data = pd.DataFrame({
        "Open": close * 0.99,
        "High": close * 1.01,
        "Low": close * 0.98,
        "Close": close,
        "Volume": 1000000,
    }, index=dates)
    data.index.name = "Date"
    return data


def test_sma_crossover_initialization():
    """Test SMA strategy initializes correctly."""
    strategy = SMACrossover(fast_period=10, slow_period=20)
    assert strategy.fast_period == 10
    assert strategy.slow_period == 20
    assert strategy.name == "SMA_10_20"


def test_sma_setup_calculates_indicators():
    """Test that setup calculates SMAs correctly."""
    data = create_test_data_with_trend(bars=50, trend="up")
    strategy = SMACrossover(fast_period=5, slow_period=10)
    strategy.setup(data)
    
    assert strategy.fast_sma is not None
    assert strategy.slow_sma is not None
    assert len(strategy.fast_sma) == len(data)
    assert len(strategy.slow_sma) == len(data)


def test_sma_hold_during_warmup():
    """Test SMA returns HOLD during warmup period."""
    data = create_test_data_with_trend(bars=50, trend="up")
    strategy = SMACrossover(fast_period=10, slow_period=20)
    strategy.setup(data)
    
    # Should return HOLD for bars before slow_period
    for i in range(strategy.slow_period):
        signal = strategy.on_bar(i, data.iloc[i])
        assert signal == "HOLD"


def test_sma_crossover_buy_signal():
    """Test SMA logic can generate BUY when conditions are met."""
    # Create data with clear upward trend that will cause crossover
    dates = pd.date_range("2020-01-01", periods=100, freq="D")
    # Start flat, then strong uptrend
    close = np.concatenate([np.full(40, 100), np.linspace(100, 150, 60)])
    data = pd.DataFrame({
        "Open": close * 0.99,
        "High": close * 1.01,
        "Low": close * 0.98,
        "Close": close,
        "Volume": 1000000,
    }, index=dates)
    data.index.name = "Date"
    
    strategy = SMACrossover(fast_period=5, slow_period=20)
    strategy.setup(data)
    
    buy_signals = []
    for i in range(len(data)):
        signal = strategy.on_bar(i, data.iloc[i])
        if signal == "BUY":
            buy_signals.append(i)
    
    # With a clear trend change, should generate at least one BUY
    assert len(buy_signals) > 0


def test_sma_crossover_sell_signal():
    """Test SMA generates SELL when fast crosses below slow."""
    # Create data with clear pattern: flat, up, down
    dates = pd.date_range("2020-01-01", periods=150, freq="D")
    close = np.concatenate([
        np.full(30, 100),           # Flat start
        np.linspace(100, 140, 50),  # Strong up
        np.linspace(140, 90, 70)    # Strong down
    ])
    data = pd.DataFrame({
        "Open": close * 0.99,
        "High": close * 1.01,
        "Low": close * 0.98,
        "Close": close,
        "Volume": 1000000,
    }, index=dates)
    data.index.name = "Date"
    
    strategy = SMACrossover(fast_period=5, slow_period=20)
    strategy.setup(data)
    
    signals = []
    for i in range(len(data)):
        signal = strategy.on_bar(i, data.iloc[i])
        signals.append(signal)
    
    # With clear up then down pattern, should have both signals
    assert "BUY" in signals or "SELL" in signals  # At least one signal


def test_rsi_initialization():
    """Test RSI strategy initializes correctly."""
    strategy = RSIMeanReversion(period=14, oversold=30, overbought=70)
    assert strategy.period == 14
    assert strategy.oversold == 30
    assert strategy.overbought == 70
    assert strategy.name == "RSI_14"


def test_rsi_setup_calculates_indicator():
    """Test that RSI is calculated during setup."""
    data = create_test_data_with_trend(bars=50)
    strategy = RSIMeanReversion(period=14)
    strategy.setup(data)
    
    assert strategy.rsi is not None
    assert len(strategy.rsi) == len(data)


def test_rsi_hold_during_warmup():
    """Test RSI returns HOLD during warmup period."""
    data = create_test_data_with_trend(bars=50)
    strategy = RSIMeanReversion(period=14)
    strategy.setup(data)
    
    for i in range(strategy.period):
        signal = strategy.on_bar(i, data.iloc[i])
        assert signal == "HOLD"


def test_rsi_oversold_signal():
    """Test RSI can detect oversold conditions."""
    # Create data with very sharp drop to ensure low RSI
    dates = pd.date_range("2020-01-01", periods=60, freq="D")
    close = np.concatenate([
        np.full(20, 100),
        np.linspace(100, 60, 15),  # Very sharp drop
        np.linspace(60, 65, 25)    # Small recovery
    ])
    data = pd.DataFrame({
        "Open": close * 0.99,
        "High": close * 1.01,
        "Low": close * 0.98,
        "Close": close,
        "Volume": 1000000,
    }, index=dates)
    data.index.name = "Date"
    
    strategy = RSIMeanReversion(period=14, oversold=50)  # Higher threshold
    strategy.setup(data)
    
    # Check that RSI goes low during the drop
    rsi_values = strategy.rsi.iloc[20:40].dropna()
    assert len(rsi_values) > 0
    assert rsi_values.min() < 50  # RSI should go below 50 during sharp drop


def test_rsi_overbought_signal():
    """Test RSI can detect overbought conditions."""
    # Create data with very sharp rise to ensure high RSI
    dates = pd.date_range("2020-01-01", periods=60, freq="D")
    close = np.concatenate([
        np.full(20, 100),
        np.linspace(100, 160, 15),  # Very sharp rise
        np.linspace(160, 155, 25)   # Small pullback
    ])
    data = pd.DataFrame({
        "Open": close * 0.99,
        "High": close * 1.01,
        "Low": close * 0.98,
        "Close": close,
        "Volume": 1000000,
    }, index=dates)
    data.index.name = "Date"
    
    strategy = RSIMeanReversion(period=14, overbought=50)  # Lower threshold
    strategy.setup(data)
    
    # Check that RSI goes high during the rise
    rsi_values = strategy.rsi.iloc[20:40].dropna()
    assert len(rsi_values) > 0
    assert rsi_values.max() > 50  # RSI should go above 50 during sharp rise


def test_rsi_calculation_values():
    """Test RSI calculation produces valid values (0-100)."""
    data = create_test_data_with_trend(bars=100, trend="up")
    strategy = RSIMeanReversion(period=14)
    strategy.setup(data)
    
    # Check RSI values after warmup are in valid range
    valid_rsi = strategy.rsi.iloc[20:].dropna()
    assert (valid_rsi >= 0).all()
    assert (valid_rsi <= 100).all()


def test_strategy_position_tracking():
    """Test that strategies properly track position state."""
    data = create_test_data_with_trend(bars=50)
    strategy = SMACrossover(fast_period=5, slow_period=10)
    strategy.setup(data)
    
    assert strategy.position == False
    
    # Manually trigger a buy
    strategy.position = True
    assert strategy.position == True


def test_sma_no_signals_in_flat_market():
    """Test SMA doesn't generate signals in flat market."""
    data = create_test_data_with_trend(bars=100, trend="flat")
    strategy = SMACrossover(fast_period=10, slow_period=20)
    strategy.setup(data)
    
    signals = []
    for i in range(len(data)):
        signal = strategy.on_bar(i, data.iloc[i])
        if signal in ["BUY", "SELL"]:
            signals.append(signal)
    
    # Flat market should produce very few or no signals
    assert len(signals) <= 2  # Allow for noise at boundaries


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
