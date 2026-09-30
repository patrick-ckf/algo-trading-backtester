"""
Event-driven strategy rules for Phase 5 (L2 layer).

This module provides opt-in event-aware strategy execution that modifies
the default L0 backtest by blocking trades during blackout windows around
known economic and earnings events.

Phase 5 (L2): Event-driven strategy rules, explicitly opted-in by user,
with control vs. event-aware comparison.
"""

from dataclasses import dataclass
from typing import List, Optional, Set
import pandas as pd
import numpy as np

from backtester.engine import BacktestEngine
from backtester.strategy import Strategy
from backtester.economic_calendar import EconomicCalendar, _to_naive_day
from backtester.earnings_calendar import EarningsCalendar


@dataclass
class EventRuleConfig:
    """Configuration for event-driven rules."""
    
    enabled: bool = False
    
    # Economic calendar settings
    use_economic_events: bool = True
    economic_event_types: Optional[List[str]] = None
    economic_days_before: int = 1
    economic_days_after: int = 0
    
    # Earnings calendar settings
    use_earnings_events: bool = True
    earnings_days_before: int = 1
    earnings_days_after: int = 0
    
    def __post_init__(self):
        """Validate configuration."""
        if self.economic_days_before < 0 or self.economic_days_after < 0:
            raise ValueError("Days before/after must be non-negative")
        if self.earnings_days_before < 0 or self.earnings_days_after < 0:
            raise ValueError("Days before/after must be non-negative")


class EventDrivenEngine:
    """
    Wrapper around BacktestEngine that applies event-driven rules.
    
    This engine runs the same strategy as the control but blocks BUY signals
    during blackout windows around known events (economic releases, earnings).
    
    The control backtest (L0) remains unchanged. This engine creates a variant
    for comparison purposes (L2 layer).
    """
    
    def __init__(
        self,
        base_engine: BacktestEngine,
        rule_config: EventRuleConfig,
    ):
        """
        Initialize event-driven engine.
        
        Args:
            base_engine: The base backtest engine to wrap
            rule_config: Event-driven rule configuration
        """
        self.base_engine = base_engine
        self.config = rule_config
        self.blackout_dates: Set[pd.Timestamp] = set()
        self.blocked_signal_count: int = 0
    
    def _build_blackout_windows(
        self,
        data: pd.DataFrame,
        symbol: Optional[str] = None,
    ) -> None:
        """
        Build blackout date windows from economic and earnings calendars.
        
        Args:
            data: OHLCV DataFrame with DatetimeIndex
            symbol: Ticker symbol (for earnings calendar)
        """
        blackout_dates_set = set()
        
        # Economic calendar blackout dates
        if self.config.use_economic_events:
            economic_calendar = EconomicCalendar()
            if economic_calendar.load():
                event_dates = economic_calendar.get_event_dates(
                    start_date=data.index.min(),
                    end_date=data.index.max(),
                    event_types=self.config.economic_event_types,
                )
                excluded_dates = economic_calendar.create_exclusion_window(
                    event_dates,
                    days_before=self.config.economic_days_before,
                    days_after=self.config.economic_days_after,
                )
                blackout_dates_set.update(_to_naive_day(d) for d in excluded_dates)
        
        # Earnings calendar blackout dates
        if self.config.use_earnings_events and symbol:
            earnings_calendar = EarningsCalendar()
            if earnings_calendar.load(
                symbol=symbol,
                start_date=data.index.min(),
                end_date=data.index.max(),
                prefer_yfinance=False,
            ):
                earnings_dates = earnings_calendar.get_event_dates(
                    start_date=data.index.min(),
                    end_date=data.index.max(),
                    symbol=symbol,
                )
                excluded_dates = earnings_calendar.create_exclusion_window(
                    earnings_dates,
                    days_before=self.config.earnings_days_before,
                    days_after=self.config.earnings_days_after,
                )
                blackout_dates_set.update(_to_naive_day(d) for d in excluded_dates)
        
        self.blackout_dates = blackout_dates_set
    
    def run(
        self,
        strategy: Strategy,
        data: pd.DataFrame,
        symbol: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Execute the event-aware backtest.
        
        This wraps the strategy to block BUY signals during blackout windows.
        
        Args:
            strategy: Strategy instance to test
            data: OHLCV DataFrame with DatetimeIndex
            symbol: Ticker symbol (for earnings calendar)
        
        Returns:
            DataFrame with equity curve
        """
        if not self.config.enabled:
            # If rules are disabled, run normal backtest
            return self.base_engine.run(strategy, data)
        
        # Build blackout windows
        self._build_blackout_windows(data, symbol)
        
        # Wrap strategy with event-aware logic
        event_aware_strategy = EventAwareStrategyWrapper(
            strategy=strategy,
            blackout_dates=self.blackout_dates,
        )
        
        # Run backtest with wrapped strategy
        equity_curve = self.base_engine.run(event_aware_strategy, data)
        
        # Track blocked signals
        self.blocked_signal_count = event_aware_strategy.blocked_signal_count
        
        return equity_curve
    
    def get_trades_df(self) -> pd.DataFrame:
        """Return trades DataFrame from base engine."""
        return self.base_engine.get_trades_df()
    
    @property
    def trades(self) -> List:
        """Return trades list from base engine."""
        return self.base_engine.trades


class EventAwareStrategyWrapper(Strategy):
    """
    Wrapper around a base strategy that blocks BUY signals during blackout windows.
    
    This wrapper intercepts signals from the base strategy and converts BUY signals
    to HOLD during blackout periods. SELL signals are allowed to pass through
    (positions can be closed during blackout windows).
    """
    
    def __init__(
        self,
        strategy: Strategy,
        blackout_dates: Set[pd.Timestamp],
    ):
        """
        Initialize strategy wrapper.
        
        Args:
            strategy: Base strategy to wrap
            blackout_dates: Set of blackout dates (timezone-naive)
        """
        super().__init__(name=f"EventAware_{strategy.name}")
        self.base_strategy = strategy
        self.blackout_dates = blackout_dates
        self.blocked_signal_count = 0
    
    def setup(self, data: pd.DataFrame) -> None:
        """Setup base strategy."""
        self.data = data.copy()
        self.base_strategy.setup(data)
    
    def on_bar(self, index: int, row: pd.Series) -> str:
        """
        Generate trading signal with event-aware filtering.
        
        Args:
            index: Current bar index
            row: Current bar data
        
        Returns:
            Signal: "BUY", "SELL", or "HOLD"
        """
        # Get signal from base strategy
        base_signal = self.base_strategy.on_bar(index, row)
        
        # If signal is not BUY, pass through unchanged
        if base_signal != "BUY":
            return base_signal
        
        # Check if current date is in blackout window
        current_date = _to_naive_day(row.name)
        
        if current_date in self.blackout_dates:
            # Block BUY signal during blackout
            self.blocked_signal_count += 1
            return "HOLD"
        
        # Allow BUY signal
        return base_signal
    
    def teardown(self) -> None:
        """Teardown base strategy."""
        self.base_strategy.teardown()


def run_control_vs_event_aware(
    strategy: Strategy,
    data: pd.DataFrame,
    initial_capital: float,
    commission: float,
    slippage: float,
    position_size: float,
    event_config: EventRuleConfig,
    symbol: Optional[str] = None,
) -> dict:
    """
    Run both control and event-aware backtests for comparison.
    
    Args:
        strategy: Strategy CLASS (not instance) to test - will be instantiated twice
        data: OHLCV DataFrame
        initial_capital: Starting capital
        commission: Commission rate
        slippage: Slippage rate
        position_size: Position size fraction
        event_config: Event-driven rule configuration
        symbol: Ticker symbol (for earnings calendar)
    
    Returns:
        Dictionary with control and event_aware results
    
    Note:
        The strategy parameter should be a Strategy class or a callable that returns
        a fresh strategy instance, to ensure independent state between runs.
        If you pass a strategy instance, it will be reused (with potentially shared state).
    """
    # Run control backtest (L0 - unchanged)
    control_engine = BacktestEngine(
        initial_capital=initial_capital,
        commission=commission,
        slippage=slippage,
        position_size_type="fixed_fraction",
        position_size_value=position_size,
    )
    
    # If strategy is a class, instantiate it; if it's an instance, use it directly
    if isinstance(strategy, type):
        control_strategy = strategy()
    else:
        control_strategy = strategy
    
    control_equity = control_engine.run(control_strategy, data)
    control_trades = control_engine.get_trades_df()
    
    # Run event-aware backtest (L2 - with rules)
    event_engine_base = BacktestEngine(
        initial_capital=initial_capital,
        commission=commission,
        slippage=slippage,
        position_size_type="fixed_fraction",
        position_size_value=position_size,
    )
    event_engine = EventDrivenEngine(
        base_engine=event_engine_base,
        rule_config=event_config,
    )
    
    # If strategy is a class, instantiate a fresh copy; if instance, reuse
    if isinstance(strategy, type):
        event_strategy = strategy()
    else:
        event_strategy = strategy
    
    event_equity = event_engine.run(event_strategy, data, symbol=symbol)
    event_trades = event_engine.get_trades_df()
    
    return {
        "control": {
            "equity": control_equity,
            "trades": control_trades,
            "engine": control_engine,
        },
        "event_aware": {
            "equity": event_equity,
            "trades": event_trades,
            "engine": event_engine,
            "blocked_signals": event_engine.blocked_signal_count,
        },
    }
