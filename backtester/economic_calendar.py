"""
Economic Calendar - Government Data Release Timeline (Phase 2, L1)

Provides economic event markers for research and optional trade filtering.
Follows Phase 0 boundaries: display-only by default, does not modify L0 signals.
"""

import pandas as pd
from typing import Optional, List
from datetime import datetime, date
import io


class EconomicCalendar:
    """
    Loads and filters economic events for visualization and optional trade exclusion.
    
    All date comparisons are normalized to timezone-naive calendar dates to ensure
    compatibility with yfinance OHLCV data (which uses timezone-naive datetime64[us]).
    """
    
    def __init__(self, csv_path: Optional[str] = None, csv_data: Optional[str] = None):
        """
        Initialize economic calendar from CSV file or string data.
        
        Args:
            csv_path: Path to CSV file with columns: Date, Event, Impact, Country
            csv_data: CSV string data (alternative to file path)
        
        Expected CSV format:
            Date,Event,Impact,Country
            2018-01-03,FOMC Minutes,High,US
            2018-02-02,NFP Employment Report,High,US
        """
        self.calendar_df: Optional[pd.DataFrame] = None
        
        if csv_path:
            self._load_from_file(csv_path)
        elif csv_data:
            self._load_from_string(csv_data)
    
    def _load_from_file(self, path: str) -> None:
        """Load calendar from CSV file."""
        df = pd.read_csv(path)
        self._normalize_dates(df)
        self.calendar_df = df
    
    def _load_from_string(self, csv_string: str) -> None:
        """Load calendar from CSV string."""
        df = pd.read_csv(io.StringIO(csv_string))
        self._normalize_dates(df)
        self.calendar_df = df
    
    def _normalize_dates(self, df: pd.DataFrame) -> None:
        """
        Normalize Date column to timezone-naive calendar dates.
        
        Economic events are civil dates (e.g., "FOMC on 2018-01-03").
        If the CSV contains timezone-aware timestamps (e.g., "2018-01-03 00:00:00-05:00"),
        we extract the civil date in that timezone, then convert to naive for comparison.
        
        This ensures compatibility with yfinance data.index which is timezone-naive datetime64[us].
        """
        # Parse dates with utc=True to handle mixed timezones (e.g., DST transitions)
        # This converts all timestamps to UTC first
        df["Date"] = pd.to_datetime(df["Date"], utc=True)
        
        # Now we have consistent UTC timestamps, localize to None to make naive
        df["Date"] = df["Date"].dt.tz_localize(None)
        
        # Normalize all to midnight naive datetime for consistent comparison
        df["Date"] = pd.to_datetime(df["Date"].dt.date)
    
    def filter_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> pd.DataFrame:
        """
        Filter events within date range.
        
        Args:
            start_date: Start date (timezone-naive, typically from data.index.min())
            end_date: End date (timezone-naive, typically from data.index.max())
        
        Returns:
            DataFrame of events within range, sorted by date
        
        Raises:
            TypeError: If calendar dates and range dates have incompatible types
        """
        if self.calendar_df is None or self.calendar_df.empty:
            return pd.DataFrame(columns=["Date", "Event", "Impact", "Country"])
        
        # Normalize input dates to naive calendar dates (strip time component)
        # This handles the case where start_date/end_date come from yfinance data.index
        start_naive = pd.to_datetime(start_date).tz_localize(None) if hasattr(start_date, 'tz') and start_date.tz else start_date
        end_naive = pd.to_datetime(end_date).tz_localize(None) if hasattr(end_date, 'tz') and end_date.tz else end_date
        
        # Convert to date-only for comparison (ignores time component)
        if isinstance(start_naive, pd.Timestamp):
            start_naive = start_naive.date()
        if isinstance(end_naive, pd.Timestamp):
            end_naive = end_naive.date()
        
        start_naive = pd.to_datetime(start_naive)
        end_naive = pd.to_datetime(end_naive)
        
        # Filter: both sides are now timezone-naive datetime64[ns] at midnight
        mask = (self.calendar_df["Date"] >= start_naive) & (self.calendar_df["Date"] <= end_naive)
        filtered = self.calendar_df[mask].copy()
        
        return filtered.sort_values("Date").reset_index(drop=True)
    
    def filter_by_impact(self, impact: str) -> pd.DataFrame:
        """
        Filter events by impact level.
        
        Args:
            impact: Impact level (e.g., "High", "Medium", "Low")
        
        Returns:
            DataFrame of events matching impact level
        """
        if self.calendar_df is None or self.calendar_df.empty:
            return pd.DataFrame(columns=["Date", "Event", "Impact", "Country"])
        
        return self.calendar_df[self.calendar_df["Impact"] == impact].copy()
    
    def get_events_on_date(self, target_date: datetime) -> List[str]:
        """
        Get list of events on a specific date.
        
        Args:
            target_date: Target date (timezone-naive or aware)
        
        Returns:
            List of event names on that date
        """
        if self.calendar_df is None or self.calendar_df.empty:
            return []
        
        # Normalize target date
        target_naive = pd.to_datetime(target_date).tz_localize(None) if hasattr(target_date, 'tz') and target_date.tz else target_date
        if isinstance(target_naive, pd.Timestamp):
            target_naive = target_naive.date()
        target_naive = pd.to_datetime(target_naive)
        
        events = self.calendar_df[self.calendar_df["Date"] == target_naive]["Event"].tolist()
        return events
    
    def is_event_day(self, target_date: datetime, impact_filter: Optional[str] = None) -> bool:
        """
        Check if a date has economic events.
        
        Args:
            target_date: Date to check
            impact_filter: Optional impact level filter (e.g., "High")
        
        Returns:
            True if date has matching events
        """
        if self.calendar_df is None or self.calendar_df.empty:
            return False
        
        # Normalize target date
        target_naive = pd.to_datetime(target_date).tz_localize(None) if hasattr(target_date, 'tz') and target_date.tz else target_date
        if isinstance(target_naive, pd.Timestamp):
            target_naive = target_naive.date()
        target_naive = pd.to_datetime(target_naive)
        
        df = self.calendar_df[self.calendar_df["Date"] == target_naive]
        
        if impact_filter:
            df = df[df["Impact"] == impact_filter]
        
        return len(df) > 0
    
    def get_exclusion_dates(
        self,
        start_date: datetime,
        end_date: datetime,
        impact: str = "High",
    ) -> List[datetime]:
        """
        Get list of dates to potentially exclude from trading (optional filter).
        
        This is L1 research filtering - must be opt-in, does not affect L0 by default.
        
        Args:
            start_date: Start date of range
            end_date: End date of range
            impact: Minimum impact level to include (default: "High")
        
        Returns:
            List of timezone-naive dates with economic events
        """
        filtered = self.filter_by_date_range(start_date, end_date)
        
        if impact:
            filtered = filtered[filtered["Impact"] == impact]
        
        return filtered["Date"].tolist()
