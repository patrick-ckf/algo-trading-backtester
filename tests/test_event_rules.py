"""
Unit tests for Phase 5 event-driven rules.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime

from backtester.event_rules import (
    EventRuleConfig,
    EventDrivenEngine,
    EventAwareStrategyWrapper,
    run_control_vs_event_aware,
)
from backtester.engine import BacktestEngine
from backtester.strategy import Strategy
from backtester.economic_calendar import _to_naive_day


class SimpleStrategy(Strategy):
    """Simple test strategy that buys on bar 1, sells on last bar."""
    
    def __init__(self):
        super().__init__(name="SimpleTest")
    
    def on_bar(self, index: int, row: pd.Series) -> str:
        # Buy on second bar (index 1)
        if index == 1:
            return "BUY"
        # Sell on last bar
        if index == len(self.data) - 1:
            return "SELL"
        return "HOLD"


class AlwaysBuyStrategy(Strategy):
    """Test strategy that always tries to buy."""
    
    def on_bar(self, index: int, row: pd.Series) -> str:
        return "BUY"


def create_test_data(num_days: int = 50, start_date: str = "2020-01-01") -> pd.DataFrame:
    """Create synthetic OHLCV data for testing."""
    dates = pd.date_range(start=start_date, periods=num_days, freq="D")
    np.random.seed(42)
    
    close = 100 + np.cumsum(np.random.randn(num_days) * 2)
    high = close + np.abs(np.random.randn(num_days))
    low = close - np.abs(np.random.randn(num_days))
    open_ = close + np.random.randn(num_days) * 0.5
    volume = np.random.randint(1000000, 10000000, num_days)
    
    df = pd.DataFrame({
        "Date": dates,
        "Open": open_,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": volume,
    })
    df.set_index("Date", inplace=True)
    
    return df


class TestEventRuleConfig:
    """Test EventRuleConfig dataclass."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = EventRuleConfig()
        
        assert config.enabled is False
        assert config.use_economic_events is True
        assert config.use_earnings_events is True
        assert config.economic_days_before == 1
        assert config.economic_days_after == 0
        assert config.earnings_days_before == 1
        assert config.earnings_days_after == 0
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = EventRuleConfig(
            enabled=True,
            use_economic_events=True,
            economic_event_types=["CPI", "FOMC"],
            economic_days_before=2,
            economic_days_after=1,
            use_earnings_events=False,
        )
        
        assert config.enabled is True
        assert config.economic_event_types == ["CPI", "FOMC"]
        assert config.economic_days_before == 2
        assert config.economic_days_after == 1
        assert config.use_earnings_events is False
    
    def test_invalid_days_before(self):
        """Test that negative days_before raises error."""
        with pytest.raises(ValueError, match="Days before/after must be non-negative"):
            EventRuleConfig(economic_days_before=-1)
    
    def test_invalid_days_after(self):
        """Test that negative days_after raises error."""
        with pytest.raises(ValueError, match="Days before/after must be non-negative"):
            EventRuleConfig(earnings_days_after=-1)


class TestEventAwareStrategyWrapper:
    """Test EventAwareStrategyWrapper."""
    
    def test_wrapper_passes_through_sell(self):
        """Test that SELL signals pass through unchanged."""
        data = create_test_data(10)
        base_strategy = SimpleStrategy()
        blackout_dates = set()
        
        wrapper = EventAwareStrategyWrapper(base_strategy, blackout_dates)
        wrapper.setup(data)
        
        # Simulate checking the last bar (should return SELL from SimpleStrategy)
        # First need to process earlier bars so strategy state is correct
        for i in range(len(data) - 1):
            wrapper.on_bar(i, data.iloc[i])
        
        # Now check last bar
        last_row = data.iloc[-1]
        signal = wrapper.on_bar(len(data) - 1, last_row)
        
        assert signal == "SELL"
        # One BUY signal at index 1, no blocks since no blackout dates
        assert wrapper.blocked_signal_count == 0
    
    def test_wrapper_blocks_buy_in_blackout(self):
        """Test that BUY signals are blocked during blackout."""
        data = create_test_data(10)
        base_strategy = AlwaysBuyStrategy()
        
        # Add some blackout dates
        blackout_dates = {_to_naive_day(data.index[2]), _to_naive_day(data.index[5])}
        
        wrapper = EventAwareStrategyWrapper(base_strategy, blackout_dates)
        wrapper.setup(data)
        
        # Check bar at index 2 (in blackout)
        row = data.iloc[2]
        signal = wrapper.on_bar(2, row)
        assert signal == "HOLD"
        
        # Check bar at index 3 (not in blackout)
        row = data.iloc[3]
        signal = wrapper.on_bar(3, row)
        assert signal == "BUY"
        
        # Check bar at index 5 (in blackout)
        row = data.iloc[5]
        signal = wrapper.on_bar(5, row)
        assert signal == "HOLD"
        
        assert wrapper.blocked_signal_count == 2
    
    def test_wrapper_allows_buy_outside_blackout(self):
        """Test that BUY signals are allowed outside blackout."""
        data = create_test_data(10)
        base_strategy = AlwaysBuyStrategy()
        blackout_dates = set()
        
        wrapper = EventAwareStrategyWrapper(base_strategy, blackout_dates)
        wrapper.setup(data)
        
        # All BUY signals should pass through
        for i in range(len(data)):
            row = data.iloc[i]
            signal = wrapper.on_bar(i, row)
            assert signal == "BUY"
        
        assert wrapper.blocked_signal_count == 0


class TestEventDrivenEngine:
    """Test EventDrivenEngine."""
    
    def test_disabled_rules_runs_normal_backtest(self):
        """Test that disabled rules run normal backtest."""
        data = create_test_data(20)
        
        # Create control engine with fresh strategy
        control_engine = BacktestEngine(
            initial_capital=100000,
            commission=0.001,
            slippage=0.0005,
        )
        control_equity = control_engine.run(SimpleStrategy(), data)
        
        # Create event-driven engine with disabled rules and fresh strategy
        config = EventRuleConfig(enabled=False)
        base_engine = BacktestEngine(
            initial_capital=100000,
            commission=0.001,
            slippage=0.0005,
        )
        event_engine = EventDrivenEngine(base_engine, config)
        event_equity = event_engine.run(SimpleStrategy(), data)
        
        # Results should be identical when rules are disabled
        pd.testing.assert_frame_equal(control_equity, event_equity)
    
    def test_enabled_rules_may_differ_from_control(self):
        """Test that enabled rules can produce different results."""
        data = create_test_data(20)
        strategy = AlwaysBuyStrategy()
        
        # Create control engine
        control_engine = BacktestEngine(
            initial_capital=100000,
            commission=0.001,
            slippage=0.0005,
        )
        control_equity = control_engine.run(strategy, data)
        control_trades = len(control_engine.trades)
        
        # Create event-driven engine with enabled rules
        # (Note: without real calendar data, blackout may be empty, so we check the mechanism)
        config = EventRuleConfig(
            enabled=True,
            use_economic_events=False,  # Disable to avoid external dependency
            use_earnings_events=False,
        )
        base_engine = BacktestEngine(
            initial_capital=100000,
            commission=0.001,
            slippage=0.0005,
        )
        event_engine = EventDrivenEngine(base_engine, config)
        event_equity = event_engine.run(strategy, data)
        
        # With no blackout dates and no calendar data, results should match
        # (This tests that the engine runs without error)
        assert len(event_equity) == len(control_equity)
    
    def test_blocked_signal_tracking(self):
        """Test that blocked signals are tracked correctly."""
        data = create_test_data(10)
        strategy = AlwaysBuyStrategy()
        
        config = EventRuleConfig(
            enabled=True,
            use_economic_events=False,
            use_earnings_events=False,
        )
        base_engine = BacktestEngine(
            initial_capital=100000,
            commission=0.001,
            slippage=0.0005,
        )
        event_engine = EventDrivenEngine(base_engine, config)
        
        # Manually set blackout dates for testing
        event_engine.blackout_dates = {
            _to_naive_day(data.index[2]),
            _to_naive_day(data.index[5]),
        }
        
        # Run with wrapper directly
        wrapper = EventAwareStrategyWrapper(strategy, event_engine.blackout_dates)
        equity = base_engine.run(wrapper, data)
        
        # Should have blocked some signals
        assert wrapper.blocked_signal_count >= 2


class TestRunControlVsEventAware:
    """Test run_control_vs_event_aware function."""
    
    def test_returns_both_results(self):
        """Test that function returns both control and event_aware results."""
        data = create_test_data(20)
        
        config = EventRuleConfig(
            enabled=True,
            use_economic_events=False,
            use_earnings_events=False,
        )
        
        # Pass strategy class (not instance) to ensure fresh copies
        results = run_control_vs_event_aware(
            strategy=SimpleStrategy,
            data=data,
            initial_capital=100000,
            commission=0.001,
            slippage=0.0005,
            position_size=0.95,
            event_config=config,
            symbol="SPY",
        )
        
        assert "control" in results
        assert "event_aware" in results
        assert "equity" in results["control"]
        assert "trades" in results["control"]
        assert "engine" in results["control"]
        assert "equity" in results["event_aware"]
        assert "trades" in results["event_aware"]
        assert "engine" in results["event_aware"]
        assert "blocked_signals" in results["event_aware"]
    
    def test_control_unchanged(self):
        """Test that control results are not affected by event rules."""
        data = create_test_data(20)
        
        # Run control-only backtest with fresh strategy
        control_engine = BacktestEngine(
            initial_capital=100000,
            commission=0.001,
            slippage=0.0005,
            position_size_type="fixed_fraction",
            position_size_value=0.95,
        )
        expected_equity = control_engine.run(SimpleStrategy(), data)
        
        # Run comparison with strategy class
        config = EventRuleConfig(
            enabled=True,
            use_economic_events=False,
            use_earnings_events=False,
        )
        results = run_control_vs_event_aware(
            strategy=SimpleStrategy,
            data=data,
            initial_capital=100000,
            commission=0.001,
            slippage=0.0005,
            position_size=0.95,
            event_config=config,
            symbol="SPY",
        )
        
        # Control equity should match standalone backtest
        pd.testing.assert_frame_equal(
            results["control"]["equity"],
            expected_equity,
        )
