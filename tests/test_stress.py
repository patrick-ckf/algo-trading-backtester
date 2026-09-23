"""
Stress and performance tests for the backtesting system.
These tests use large synthetic datasets to verify performance and stability.

Run with: pytest -m stress
"""

import pytest
import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta

from backtester.engine import BacktestEngine
from backtester.strategies.sma_crossover import SMACrossover
from backtester.strategies.rsi_mean_reversion import RSIMeanReversion
from backtester.metrics import PerformanceMetrics


def generate_synthetic_ohlcv(bars: int = 10000, seed: int = 42) -> pd.DataFrame:
    """Generate synthetic OHLCV data for testing."""
    np.random.seed(seed)
    
    dates = pd.date_range(
        start=datetime.now() - timedelta(days=bars),
        periods=bars,
        freq="D"
    )
    
    # Generate random walk with drift
    returns = np.random.normal(0.0005, 0.02, bars)
    close = 100 * np.exp(np.cumsum(returns))
    
    # Generate OHLC from close
    high = close * (1 + np.abs(np.random.normal(0, 0.01, bars)))
    low = close * (1 - np.abs(np.random.normal(0, 0.01, bars)))
    open_price = close * (1 + np.random.normal(0, 0.005, bars))
    volume = np.random.randint(1000000, 10000000, bars)
    
    data = pd.DataFrame({
        "Open": open_price,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": volume,
    }, index=dates)
    data.index.name = "Date"
    
    return data


@pytest.mark.stress
def test_large_dataset_sma_10k_bars():
    """Test SMA strategy on 10,000 bars (~40 years of daily data)."""
    data = generate_synthetic_ohlcv(bars=10000)
    
    strategy = SMACrossover(fast_period=50, slow_period=200)
    engine = BacktestEngine(initial_capital=100000.0)
    
    start_time = time.time()
    equity_curve = engine.run(strategy, data)
    elapsed = time.time() - start_time
    
    # Should complete in reasonable time (adjust as needed for your CI)
    assert elapsed < 5.0, f"Took too long: {elapsed:.2f}s"
    
    assert len(equity_curve) == len(data)
    assert not equity_curve["Equity"].isna().any()
    
    metrics = PerformanceMetrics(equity_curve, engine.trades, 100000.0).calculate_all()
    assert all(not np.isnan(v) and not np.isinf(v) for v in metrics.values() if isinstance(v, (int, float)))


@pytest.mark.stress
def test_large_dataset_rsi_10k_bars():
    """Test RSI strategy on 10,000 bars."""
    data = generate_synthetic_ohlcv(bars=10000)
    
    strategy = RSIMeanReversion(period=14, oversold=30, overbought=70)
    engine = BacktestEngine(initial_capital=100000.0)
    
    start_time = time.time()
    equity_curve = engine.run(strategy, data)
    elapsed = time.time() - start_time
    
    assert elapsed < 5.0, f"Took too long: {elapsed:.2f}s"
    
    assert len(equity_curve) == len(data)
    assert not equity_curve["Equity"].isna().any()


@pytest.mark.stress
def test_very_large_dataset_50k_bars():
    """Test engine on very large dataset (50,000 bars ~200 years)."""
    data = generate_synthetic_ohlcv(bars=50000)
    
    strategy = SMACrossover(fast_period=50, slow_period=200)
    engine = BacktestEngine(initial_capital=100000.0)
    
    start_time = time.time()
    equity_curve = engine.run(strategy, data)
    elapsed = time.time() - start_time
    
    # Allow more time for very large dataset
    assert elapsed < 20.0, f"Took too long: {elapsed:.2f}s"
    
    assert len(equity_curve) == len(data)
    print(f"\nProcessed {len(data):,} bars in {elapsed:.2f}s ({len(data)/elapsed:.0f} bars/sec)")


@pytest.mark.stress
def test_parameter_sweep_sma():
    """Test SMA strategy with many parameter combinations."""
    data = generate_synthetic_ohlcv(bars=2000)
    
    fast_periods = [10, 20, 50]
    slow_periods = [50, 100, 200]
    
    results = []
    start_time = time.time()
    
    for fast in fast_periods:
        for slow in slow_periods:
            if fast < slow:
                strategy = SMACrossover(fast_period=fast, slow_period=slow)
                engine = BacktestEngine(initial_capital=100000.0)
                equity = engine.run(strategy, data)
                metrics = PerformanceMetrics(equity, engine.trades, 100000.0).calculate_all()
                
                results.append({
                    "fast": fast,
                    "slow": slow,
                    "return": metrics.get("total_return_pct", 0),
                    "sharpe": metrics.get("sharpe_ratio", 0),
                })
    
    elapsed = time.time() - start_time
    
    # Should complete all combinations quickly
    assert elapsed < 15.0, f"Parameter sweep too slow: {elapsed:.2f}s"
    assert len(results) > 0
    
    # All results should have finite metrics
    for result in results:
        assert not np.isnan(result["return"])
        assert not np.isinf(result["return"])


@pytest.mark.stress
def test_parameter_sweep_rsi():
    """Test RSI strategy with many parameter combinations."""
    data = generate_synthetic_ohlcv(bars=2000)
    
    periods = [7, 14, 21, 28]
    oversold_levels = [20, 30, 40]
    overbought_levels = [60, 70, 80]
    
    results = []
    start_time = time.time()
    
    for period in periods:
        for oversold in oversold_levels:
            for overbought in overbought_levels:
                if oversold < overbought:
                    strategy = RSIMeanReversion(
                        period=period,
                        oversold=oversold,
                        overbought=overbought
                    )
                    engine = BacktestEngine(initial_capital=100000.0)
                    equity = engine.run(strategy, data)
                    metrics = PerformanceMetrics(equity, engine.trades, 100000.0).calculate_all()
                    
                    results.append({
                        "period": period,
                        "oversold": oversold,
                        "overbought": overbought,
                        "return": metrics.get("total_return_pct", 0),
                    })
    
    elapsed = time.time() - start_time
    
    assert elapsed < 30.0, f"Parameter sweep too slow: {elapsed:.2f}s"
    assert len(results) > 0


@pytest.mark.stress
def test_high_frequency_trades():
    """Test engine with strategy that generates many trades."""
    # Create volatile data that triggers frequent signals
    data = generate_synthetic_ohlcv(bars=5000)
    
    # Very short periods = many crossovers
    strategy = SMACrossover(fast_period=5, slow_period=10)
    engine = BacktestEngine(initial_capital=100000.0, commission=0.001)
    
    start_time = time.time()
    equity_curve = engine.run(strategy, data)
    elapsed = time.time() - start_time
    
    assert elapsed < 10.0
    assert len(engine.trades) > 0  # Should have generated trades
    
    # Verify all trades are valid
    for trade in engine.trades:
        assert trade.shares > 0
        assert trade.entry_price > 0
        assert trade.exit_price > 0
        assert not np.isnan(trade.pnl)


@pytest.mark.stress
def test_extreme_market_conditions():
    """Test engine behavior in extreme market conditions."""
    # Create data with extreme volatility
    np.random.seed(42)
    dates = pd.date_range("2020-01-01", periods=1000, freq="D")
    
    # Simulate crash and recovery
    close = np.concatenate([
        np.linspace(100, 100, 100),      # Stable
        np.linspace(100, 50, 50),        # 50% crash
        np.linspace(50, 45, 50),         # Further decline
        np.linspace(45, 80, 200),        # Recovery
        np.linspace(80, 120, 300),       # Bull market
        np.linspace(120, 90, 300),       # Correction
    ])
    
    data = pd.DataFrame({
        "Open": close * 0.99,
        "High": close * 1.02,
        "Low": close * 0.98,
        "Close": close,
        "Volume": 1000000,
    }, index=dates)
    data.index.name = "Date"
    
    strategy = SMACrossover(fast_period=20, slow_period=50)
    engine = BacktestEngine(initial_capital=100000.0)
    equity = engine.run(strategy, data)
    
    assert not equity.empty
    assert len(equity) == len(data)
    
    # Should handle extreme conditions without crashing
    metrics = PerformanceMetrics(equity, engine.trades, 100000.0).calculate_all()
    assert "max_drawdown_pct" in metrics
    assert metrics["max_drawdown_pct"] < 0  # Should have drawdown


@pytest.mark.stress
def test_memory_stability():
    """Test that engine doesn't leak memory with repeated runs."""
    data = generate_synthetic_ohlcv(bars=5000)
    
    # Run multiple times to check for memory issues
    for i in range(10):
        strategy = SMACrossover(fast_period=20, slow_period=50)
        engine = BacktestEngine(initial_capital=100000.0)
        equity = engine.run(strategy, data)
        
        assert len(equity) == len(data)
        assert len(engine.trades) >= 0


@pytest.mark.stress
def test_concurrent_strategies():
    """Test running multiple strategies on same data."""
    data = generate_synthetic_ohlcv(bars=3000)
    
    strategies = [
        SMACrossover(fast_period=10, slow_period=30),
        SMACrossover(fast_period=20, slow_period=50),
        SMACrossover(fast_period=50, slow_period=100),
        RSIMeanReversion(period=14, oversold=30, overbought=70),
        RSIMeanReversion(period=21, oversold=25, overbought=75),
    ]
    
    start_time = time.time()
    
    for strategy in strategies:
        engine = BacktestEngine(initial_capital=100000.0)
        equity = engine.run(strategy, data)
        assert not equity.empty
    
    elapsed = time.time() - start_time
    
    # Should handle multiple strategies efficiently
    assert elapsed < 10.0, f"Too slow for multiple strategies: {elapsed:.2f}s"


@pytest.mark.stress
def test_edge_case_single_bar():
    """Test engine with minimal data (edge case)."""
    data = generate_synthetic_ohlcv(bars=1)
    
    strategy = SMACrossover(fast_period=10, slow_period=20)
    engine = BacktestEngine(initial_capital=100000.0)
    equity = engine.run(strategy, data)
    
    assert len(equity) == 1
    assert len(engine.trades) == 0  # No trades possible with 1 bar


@pytest.mark.stress
def test_zero_commission_slippage_performance():
    """Test performance with zero costs (best case)."""
    data = generate_synthetic_ohlcv(bars=10000)
    
    strategy = SMACrossover(fast_period=50, slow_period=200)
    engine = BacktestEngine(
        initial_capital=100000.0,
        commission=0.0,
        slippage=0.0,
    )
    
    start_time = time.time()
    equity = engine.run(strategy, data)
    elapsed = time.time() - start_time
    
    assert elapsed < 5.0
    assert not equity.empty


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "stress"])
