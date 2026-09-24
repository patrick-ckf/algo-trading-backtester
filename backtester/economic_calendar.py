"""
Economic calendar data loading and filtering for research overlays.

Phase 2 (L1): Display, alignment, and optional research filter only.
Does NOT modify L0 backtest engine or strategy signals by default.
"""

import os
from typing import List, Optional, Set
import pandas as pd
import numpy as np


class EconomicCalendar:
    """
    Load and filter US economic release dates for research purposes.
    
    This is an L1 (research/context) layer that provides display and
    optional filtering capabilities. It does NOT modify the L0 backtest
    engine or strategy signals unless explicitly opted-in by the user.
    """
    
    def __init__(self, calendar_path: Optional[str] = None):
        """
        Initialize economic calendar.
        
        Args:
            calendar_path: Path to calendar CSV file. If None, uses default.
        """
        if calendar_path is None:
            # Default path relative to package root
            package_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            calendar_path = os.path.join(package_dir, "data", "economic_calendar.csv")
        
        self.calendar_path = calendar_path
        self.calendar_df: Optional[pd.DataFrame] = None
        self.available_types: Set[str] = set()
    
    def load(self) -> bool:
        """
        Load calendar data from CSV.
        
        Returns:
            True if loaded successfully, False otherwise (graceful degradation).
        """
        try:
            if not os.path.exists(self.calendar_path):
                return False
            
            # Read CSV without parsing dates first (to handle tz-aware strings)
            df_raw = pd.read_csv(self.calendar_path)
            
            if df_raw.empty:
                return False
            
            # Parse dates with utc=True to handle mixed timezones (DST transitions)
            # This converts all timestamps to UTC, avoiding "Mixed timezones detected" error
            df_raw["Date"] = pd.to_datetime(df_raw["Date"], utc=True)
            
            # Normalize dates to timezone-naive for compatibility with yfinance
            # yfinance returns tz-naive datetime64[us] DatetimeIndex
            # Convert UTC to naive for consistent comparison
            df_raw["Date"] = df_raw["Date"].dt.tz_localize(None)
            
            # Normalize to midnight for clean date comparison
            df_raw["Date"] = pd.to_datetime(df_raw["Date"].dt.date)
            
            self.calendar_df = df_raw
            
            # Extract available event types
            if "Type" in self.calendar_df.columns:
                self.available_types = set(self.calendar_df["Type"].unique())
            
            return True
            
        except Exception:
            # Graceful degradation: if loading fails, continue without calendar
            self.calendar_df = None
            self.available_types = set()
            return False
    
    def is_loaded(self) -> bool:
        """Check if calendar data is available."""
        return self.calendar_df is not None and not self.calendar_df.empty
    
    def get_available_types(self) -> List[str]:
        """Get list of available event types, sorted alphabetically."""
        return sorted(list(self.available_types))
    
    def filter_by_date_range(
        self,
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        event_types: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Filter calendar events by date range and optional event types.
        
        Args:
            start_date: Start of date range (tz-naive or aware)
            end_date: End of date range (tz-naive or aware)
            event_types: List of event types to include. If None, includes all.
        
        Returns:
            Filtered DataFrame with Date, Event, Type, Country columns.
        """
        if not self.is_loaded():
            return pd.DataFrame(columns=["Date", "Event", "Type", "Country"])
        
        # Normalize input dates to tz-naive for comparison
        # (calendar dates are already normalized to tz-naive in load())
        start_naive = pd.to_datetime(start_date)
        end_naive = pd.to_datetime(end_date)
        
        if start_naive.tz is not None:
            start_naive = start_naive.tz_convert("UTC").tz_localize(None)
        if end_naive.tz is not None:
            end_naive = end_naive.tz_convert("UTC").tz_localize(None)
        
        # Normalize to date-only for comparison
        start_naive = pd.to_datetime(start_naive.date())
        end_naive = pd.to_datetime(end_naive.date())
        
        # Filter by date range
        mask = (self.calendar_df["Date"] >= start_naive) & (self.calendar_df["Date"] <= end_naive)
        filtered = self.calendar_df[mask].copy()
        
        # Filter by event types if specified
        if event_types:
            filtered = filtered[filtered["Type"].isin(event_types)]
        
        return filtered.sort_values("Date").reset_index(drop=True)
    
    def get_event_dates(
        self,
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        event_types: Optional[List[str]] = None,
    ) -> pd.DatetimeIndex:
        """
        Get DatetimeIndex of event dates for marking on charts.
        
        Args:
            start_date: Start of date range
            end_date: End of date range
            event_types: List of event types to include. If None, includes all.
        
        Returns:
            DatetimeIndex of event dates.
        """
        filtered = self.filter_by_date_range(start_date, end_date, event_types)
        if filtered.empty:
            return pd.DatetimeIndex([])
        return pd.DatetimeIndex(filtered["Date"])
    
    def create_exclusion_window(
        self,
        event_dates: pd.DatetimeIndex,
        days_before: int = 0,
        days_after: int = 0,
    ) -> pd.DatetimeIndex:
        """
        Create exclusion window around event dates (for research filter).
        
        This is a RESEARCH FILTER utility. It should only be used when
        explicitly opted-in by the user and labeled as research-only.
        
        Args:
            event_dates: DatetimeIndex of event dates
            days_before: Number of days before event to exclude
            days_after: Number of days after event to exclude
        
        Returns:
            DatetimeIndex of all dates within exclusion windows.
        """
        if len(event_dates) == 0:
            return pd.DatetimeIndex([])
        
        excluded_dates = set()
        for event_date in event_dates:
            # Add dates in window
            for offset in range(-days_before, days_after + 1):
                excluded_dates.add(event_date + pd.Timedelta(days=offset))
        
        return pd.DatetimeIndex(sorted(excluded_dates))
    
    def filter_trades_by_exclusion(
        self,
        trades_df: pd.DataFrame,
        excluded_dates: pd.DatetimeIndex,
        entry_column: str = "Entry Date",
    ) -> pd.DataFrame:
        """
        Filter trades to exclude those with entries in exclusion window.
        
        This is a RESEARCH FILTER. Use only when user explicitly opts-in.
        
        Args:
            trades_df: DataFrame of trades from engine.get_trades_df()
            excluded_dates: DatetimeIndex of dates to exclude
            entry_column: Name of entry date column
        
        Returns:
            Filtered trades DataFrame.
        """
        if trades_df.empty or len(excluded_dates) == 0:
            return trades_df
        
        # Normalize entry dates to date only (remove time component)
        entry_dates = pd.to_datetime(trades_df[entry_column]).dt.normalize()
        excluded_dates_normalized = pd.to_datetime(excluded_dates).normalize()
        
        # Keep trades whose entry date is NOT in exclusion window
        mask = ~entry_dates.isin(excluded_dates_normalized)
        return trades_df[mask].copy()


def calculate_research_metrics(
    trades_df: pd.DataFrame,
    initial_capital: float,
    equity_curve: pd.DataFrame,
) -> dict:
    """
    Calculate performance metrics for filtered trades (research filter).
    
    This mirrors the core metrics calculation but for a subset of trades.
    Used only when research filter is enabled.
    
    Args:
        trades_df: Filtered trades DataFrame
        initial_capital: Initial capital
        equity_curve: Full equity curve (for calculating returns)
    
    Returns:
        Dictionary of metrics (similar to PerformanceMetrics.calculate_all)
    """
    metrics = {
        "initial_capital": initial_capital,
        "trade_count": len(trades_df),
    }
    
    if trades_df.empty:
        metrics["final_equity"] = initial_capital
        metrics["total_return_pct"] = 0.0
        metrics["win_rate_pct"] = 0.0
        metrics["avg_trade_return_pct"] = 0.0
        return metrics
    
    # Calculate from trade PnLs
    total_pnl = trades_df["PnL"].sum()
    final_equity = initial_capital + total_pnl
    
    metrics["final_equity"] = final_equity
    metrics["total_return_pct"] = ((final_equity / initial_capital) - 1) * 100
    
    # Win rate
    winning_trades = trades_df[trades_df["PnL"] > 0]
    metrics["win_rate_pct"] = (len(winning_trades) / len(trades_df)) * 100 if len(trades_df) > 0 else 0.0
    
    # Average trade return
    metrics["avg_trade_return_pct"] = trades_df["Return %"].mean() if len(trades_df) > 0 else 0.0
    
    return metrics
