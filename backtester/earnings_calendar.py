"""
Earnings and business event calendar for research overlays.

Phase 4 (L1): Display, alignment, and optional research filter only.
Does NOT modify L0 backtest engine or strategy signals by default.
"""

import os
from typing import List, Optional, Set, Dict
import pandas as pd
import numpy as np


def _to_naive_day(value) -> pd.Timestamp:
    """
    Convert a timestamp-like value to timezone-naive midnight for safe comparisons.

    Yahoo/yfinance daily bars on some environments are tz-aware (e.g. US/Eastern);
    our calendar CSV parses as naive datetime64[us]. Comparing the two raises TypeError.
    We keep the civil calendar date in the source timezone (or as-labeled if naive).
    """
    ts = pd.Timestamp(value)
    if getattr(ts, "tz", None) is not None:
        # Preserve the date as labeled in that timezone (do not shift via UTC).
        ts = pd.Timestamp(ts.date())
    else:
        ts = ts.normalize()
    return ts


def is_index_or_etf(symbol: str) -> bool:
    """
    Heuristic to detect if a symbol is an index/ETF vs individual stock.
    
    Args:
        symbol: Stock ticker symbol
        
    Returns:
        True if likely an index/ETF, False if likely individual stock
    """
    symbol_upper = symbol.upper()
    
    # Common index ETFs
    index_etfs = {
        "SPY", "QQQ", "DIA", "IWM", "VTI", "VOO", "IVV",
        "EFA", "EEM", "VWO", "TLT", "AGG", "GLD", "SLV",
    }
    
    if symbol_upper in index_etfs:
        return True
    
    # Hong Kong stocks often end with .HK
    if ".HK" in symbol_upper:
        # Check if it's a Hang Seng Index ETF (e.g., 2800.HK)
        base = symbol_upper.split(".")[0]
        if base.isdigit() and int(base) < 5000:
            # Single or double digit could be index funds
            return int(base) < 10000
    
    # Common patterns for ETFs (3-letter tickers often ETFs, but not always)
    # Default to treating as individual stock unless matched above
    return False


def try_fetch_yfinance_earnings(
    symbol: str,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> Optional[pd.DataFrame]:
    """
    Attempt to fetch earnings dates from yfinance for the given symbol.
    
    Note: yfinance earnings calendar coverage varies. This is best-effort only.
    Falls back to sample CSV on failure.
    
    Args:
        symbol: Stock ticker symbol
        start_date: Start date for earnings
        end_date: End date for earnings
        
    Returns:
        DataFrame with columns [Date, Event, Type, Symbol] or None on failure
    """
    try:
        import yfinance as yf
        
        ticker = yf.Ticker(symbol)
        
        # Try to get earnings dates
        earnings_dates = ticker.earnings_dates
        
        if earnings_dates is None or earnings_dates.empty:
            return None
        
        # earnings_dates is a DataFrame with DatetimeIndex
        # Filter by date range
        mask = (earnings_dates.index >= start_date) & (earnings_dates.index <= end_date)
        filtered = earnings_dates[mask]
        
        if filtered.empty:
            return None
        
        # Convert to our format
        events_data = []
        for date in filtered.index:
            normalized_date = _to_naive_day(date)
            
            # Check if it's a known earnings release (has EPS Estimate)
            event_type = "Earnings"
            event_name = f"{symbol} Earnings Release"
            
            events_data.append({
                'Date': normalized_date,
                'Event': event_name,
                'Type': event_type,
                'Symbol': symbol,
            })
        
        if not events_data:
            return None
        
        df = pd.DataFrame(events_data)
        df = df.drop_duplicates(subset=['Date']).sort_values('Date').reset_index(drop=True)
        
        return df
        
    except Exception:
        # Graceful degradation: return None on any error
        return None


class EarningsCalendar:
    """
    Load and display earnings/business event dates for research purposes.
    
    This is an L1 (research/context) layer that provides display and
    optional filtering capabilities. It does NOT modify the L0 backtest
    engine or strategy signals unless explicitly opted-in by the user.
    
    Data sources (in order of preference):
    1. Sample CSV file (for reproducible demos)
    2. yfinance earnings calendar (best-effort, limited coverage)
    
    Symbol behavior:
    - Single-stock tickers (e.g., AAPL, MSFT): show earnings dates
    - Index/ETF symbols (SPY, QQQ, etc.): graceful degradation with explanation
    """
    
    def __init__(self, sample_csv_path: Optional[str] = None):
        """
        Initialize earnings calendar.
        
        Args:
            sample_csv_path: Path to sample earnings CSV file. If None, uses default.
        """
        if sample_csv_path is None:
            # Default path relative to package root
            package_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            sample_csv_path = os.path.join(package_dir, "data", "earnings_calendar.csv")
        
        self.sample_csv_path = sample_csv_path
        self.earnings_df: Optional[pd.DataFrame] = None
        self.available_symbols: Set[str] = set()
        self.available_types: Set[str] = set()
        self.data_source: str = "none"
    
    def load_sample(self) -> bool:
        """
        Load earnings from sample CSV file.
        
        Returns:
            True if loaded successfully, False otherwise (graceful degradation).
        """
        try:
            if not os.path.exists(self.sample_csv_path):
                return False
            
            self.earnings_df = pd.read_csv(
                self.sample_csv_path,
                parse_dates=["Date"],
            )
            
            if self.earnings_df.empty:
                return False
            
            # Normalize to naive calendar days for comparison with OHLCV indexes
            self.earnings_df["Date"] = self.earnings_df["Date"].map(_to_naive_day)
            
            # Ensure required columns exist
            required_cols = ["Date", "Event", "Type", "Symbol"]
            if not all(col in self.earnings_df.columns for col in required_cols):
                self.earnings_df = None
                return False
            
            # Extract available symbols and types
            self.available_symbols = set(self.earnings_df["Symbol"].unique())
            self.available_types = set(self.earnings_df["Type"].unique())
            
            self.data_source = "sample_csv"
            return True
            
        except Exception:
            # Graceful degradation: if loading fails, continue without earnings
            self.earnings_df = None
            self.available_symbols = set()
            self.available_types = set()
            self.data_source = "none"
            return False
    
    def load_yfinance(
        self,
        symbol: str,
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
    ) -> bool:
        """
        Attempt to load earnings from yfinance.
        
        Args:
            symbol: Stock ticker symbol
            start_date: Start date for earnings
            end_date: End date for earnings
            
        Returns:
            True if loaded successfully, False otherwise (graceful degradation).
        """
        try:
            # Check if it's an index/ETF
            if is_index_or_etf(symbol):
                # For indexes, don't try to fetch (will fail or be incomplete)
                self.earnings_df = None
                self.data_source = "index_not_supported"
                return False
            
            # Try to fetch from yfinance
            self.earnings_df = try_fetch_yfinance_earnings(symbol, start_date, end_date)
            
            if self.earnings_df is not None and not self.earnings_df.empty:
                self.available_symbols = set(self.earnings_df["Symbol"].unique())
                self.available_types = set(self.earnings_df["Type"].unique())
                self.data_source = "yfinance"
                return True
            else:
                self.earnings_df = None
                self.available_symbols = set()
                self.available_types = set()
                self.data_source = "none"
                return False
                
        except Exception:
            # Graceful degradation
            self.earnings_df = None
            self.available_symbols = set()
            self.available_types = set()
            self.data_source = "none"
            return False
    
    def load(
        self,
        symbol: Optional[str] = None,
        start_date: Optional[pd.Timestamp] = None,
        end_date: Optional[pd.Timestamp] = None,
        prefer_yfinance: bool = False,
    ) -> bool:
        """
        Load earnings data, trying multiple sources.
        
        Strategy:
        - If prefer_yfinance and symbol/dates provided: try yfinance first
        - Always fall back to sample CSV if available
        - Gracefully degrade to empty if all sources fail
        
        Args:
            symbol: Stock ticker symbol (for yfinance)
            start_date: Start date (for yfinance)
            end_date: End date (for yfinance)
            prefer_yfinance: Whether to try yfinance first
            
        Returns:
            True if any source loaded successfully, False otherwise
        """
        # Try yfinance if requested and params provided
        if prefer_yfinance and symbol and start_date and end_date:
            if self.load_yfinance(symbol, start_date, end_date):
                return True
        
        # Fall back to sample CSV
        if self.load_sample():
            return True
        
        # No data available
        self.data_source = "none"
        return False
    
    def is_loaded(self) -> bool:
        """Check if earnings data is available."""
        return self.earnings_df is not None and not self.earnings_df.empty
    
    def get_data_source(self) -> str:
        """Get the current data source: 'sample_csv', 'yfinance', 'index_not_supported', or 'none'."""
        return self.data_source
    
    def get_available_symbols(self) -> List[str]:
        """Get list of available symbols, sorted alphabetically."""
        return sorted(list(self.available_symbols))
    
    def get_available_types(self) -> List[str]:
        """Get list of available event types, sorted alphabetically."""
        return sorted(list(self.available_types))
    
    def filter_by_date_range(
        self,
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        symbol: Optional[str] = None,
        event_types: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Filter earnings events by date range and optionally by symbol/types.
        
        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            symbol: Optional symbol filter (e.g., "AAPL")
            event_types: List of event types to include. If None, includes all.
            
        Returns:
            Filtered DataFrame with columns [Date, Event, Type, Symbol]
        """
        if not self.is_loaded():
            return pd.DataFrame(columns=["Date", "Event", "Type", "Symbol"])
        
        # Normalize dates
        start_date = _to_naive_day(start_date)
        end_date = _to_naive_day(end_date)
        
        # Filter by date
        mask = (self.earnings_df["Date"] >= start_date) & (self.earnings_df["Date"] <= end_date)
        filtered = self.earnings_df[mask].copy()
        
        # Filter by symbol if provided
        if symbol:
            filtered = filtered[filtered["Symbol"].str.upper() == symbol.upper()]
        
        # Filter by event types if specified
        if event_types:
            filtered = filtered[filtered["Type"].isin(event_types)]
        
        return filtered.sort_values("Date").reset_index(drop=True)
    
    def get_event_dates(
        self,
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        symbol: Optional[str] = None,
        event_types: Optional[List[str]] = None,
    ) -> pd.DatetimeIndex:
        """
        Get DatetimeIndex of event dates for marking on charts.
        
        Args:
            start_date: Start of date range
            end_date: End of date range
            symbol: Optional symbol filter
            event_types: List of event types to include. If None, includes all.
        
        Returns:
            DatetimeIndex of event dates.
        """
        filtered = self.filter_by_date_range(start_date, end_date, symbol, event_types)
        if filtered.empty:
            return pd.DatetimeIndex([])
        return pd.DatetimeIndex(filtered["Date"].unique())
    
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
            base = _to_naive_day(event_date)
            # Add dates in window
            for offset in range(-days_before, days_after + 1):
                excluded_dates.add(base + pd.Timedelta(days=offset))
        
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
        
        # Normalize entry dates to naive calendar days (handles tz-aware indexes)
        entry_dates = pd.to_datetime(trades_df[entry_column]).map(_to_naive_day)
        excluded_dates_normalized = pd.DatetimeIndex(
            [_to_naive_day(d) for d in excluded_dates]
        )
        
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
