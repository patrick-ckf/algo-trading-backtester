"""
News data loading and display for research overlays.

Phase 3 (L1): Display, alignment, and research filtering only.
Does NOT modify L0 backtest engine or strategy signals by default.
"""

import os
from typing import List, Optional, Set
import pandas as pd
import numpy as np


def _to_naive_day(value) -> pd.Timestamp:
    """
    Convert a timestamp-like value to timezone-naive midnight for safe comparisons.

    Yahoo/yfinance daily bars on some environments are tz-aware (e.g. US/Eastern);
    our news CSV parses as naive datetime64[us]. Comparing the two raises TypeError.
    We keep the civil calendar date in the source timezone (or as-labeled if naive).
    """
    ts = pd.Timestamp(value)
    if getattr(ts, "tz", None) is not None:
        # Preserve the date as labeled in that timezone (do not shift via UTC).
        ts = pd.Timestamp(ts.date())
    else:
        ts = ts.normalize()
    return ts


def compute_simple_sentiment(headline: str) -> str:
    """
    Compute a simple heuristic sentiment label for a headline.
    
    This is a basic keyword-based approach for display purposes only.
    NOT used for trading signals (L1 research layer only).
    
    Args:
        headline: News headline text
        
    Returns:
        "Positive", "Negative", or "Neutral"
    """
    headline_lower = headline.lower()
    
    # Simple keyword lists (not exhaustive, for demo purposes)
    positive_keywords = [
        'soar', 'surge', 'gain', 'rally', 'rise', 'climb', 'beat', 'exceed',
        'record', 'high', 'jump', 'boost', 'strong', 'better', 'growth',
        'profit', 'upgrade', 'optimistic', 'positive', 'breakthrough', 'success',
        'expand', 'win', 'deal', 'approve', 'bull', 'recover'
    ]
    
    negative_keywords = [
        'fall', 'drop', 'plunge', 'decline', 'crash', 'sink', 'lose', 'miss',
        'low', 'tumble', 'slide', 'weak', 'worse', 'slump', 'loss',
        'downgrade', 'pessimistic', 'negative', 'concern', 'worry', 'fear',
        'fail', 'cut', 'layoff', 'lawsuit', 'bear', 'crisis', 'recession'
    ]
    
    pos_count = sum(1 for word in positive_keywords if word in headline_lower)
    neg_count = sum(1 for word in negative_keywords if word in headline_lower)
    
    if pos_count > neg_count:
        return "Positive"
    elif neg_count > pos_count:
        return "Negative"
    else:
        return "Neutral"


def try_fetch_yfinance_news(
    symbol: str,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> Optional[pd.DataFrame]:
    """
    Attempt to fetch news from yfinance for the given symbol and date range.
    
    Note: yfinance news coverage is limited and flaky. This is best-effort only.
    Falls back to sample CSV on failure.
    
    Args:
        symbol: Stock ticker symbol
        start_date: Start date for news
        end_date: End date for news
        
    Returns:
        DataFrame with columns [Date, Headline, Sentiment] or None on failure
    """
    try:
        import yfinance as yf
        
        ticker = yf.Ticker(symbol)
        news_items = ticker.news
        
        if not news_items:
            return None
        
        # Parse news items into DataFrame
        news_data = []
        for item in news_items:
            # yfinance provides unix timestamp
            timestamp = item.get('providerPublishTime')
            if timestamp:
                date = pd.Timestamp(timestamp, unit='s').normalize()
                headline = item.get('title', '')
                
                if start_date <= date <= end_date and headline:
                    sentiment = compute_simple_sentiment(headline)
                    news_data.append({
                        'Date': date,
                        'Headline': headline,
                        'Sentiment': sentiment,
                    })
        
        if not news_data:
            return None
        
        df = pd.DataFrame(news_data)
        df['Date'] = df['Date'].map(_to_naive_day)
        df = df.sort_values('Date').reset_index(drop=True)
        
        return df
        
    except Exception:
        # Graceful degradation: return None on any error
        return None


class NewsPanel:
    """
    Load and display news headlines for research purposes.
    
    This is an L1 (research/context) layer that provides display capabilities.
    It does NOT modify the L0 backtest engine or strategy signals.
    
    Data sources (in order of preference):
    1. Sample CSV file (for reproducible demos)
    2. yfinance news (best-effort, limited coverage)
    """
    
    def __init__(self, sample_csv_path: Optional[str] = None):
        """
        Initialize news panel.
        
        Args:
            sample_csv_path: Path to sample news CSV file. If None, uses default.
        """
        if sample_csv_path is None:
            # Default path relative to package root
            package_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            sample_csv_path = os.path.join(package_dir, "data", "news_sample.csv")
        
        self.sample_csv_path = sample_csv_path
        self.news_df: Optional[pd.DataFrame] = None
        self.data_source: str = "none"
    
    def load_sample(self) -> bool:
        """
        Load news from sample CSV file.
        
        Returns:
            True if loaded successfully, False otherwise (graceful degradation).
        """
        try:
            if not os.path.exists(self.sample_csv_path):
                return False
            
            self.news_df = pd.read_csv(
                self.sample_csv_path,
                parse_dates=["Date"],
            )
            
            if self.news_df.empty:
                return False
            
            # Normalize to naive calendar days for comparison with OHLCV indexes
            self.news_df["Date"] = self.news_df["Date"].map(_to_naive_day)
            
            # Ensure required columns exist
            required_cols = ["Date", "Headline", "Symbol"]
            if not all(col in self.news_df.columns for col in required_cols):
                self.news_df = None
                return False
            
            # Add sentiment if not present
            if "Sentiment" not in self.news_df.columns:
                self.news_df["Sentiment"] = self.news_df["Headline"].apply(compute_simple_sentiment)
            
            self.data_source = "sample_csv"
            return True
            
        except Exception:
            # Graceful degradation: if loading fails, continue without news
            self.news_df = None
            self.data_source = "none"
            return False
    
    def load_yfinance(
        self,
        symbol: str,
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
    ) -> bool:
        """
        Attempt to load news from yfinance.
        
        Args:
            symbol: Stock ticker symbol
            start_date: Start date for news
            end_date: End date for news
            
        Returns:
            True if loaded successfully, False otherwise (graceful degradation).
        """
        try:
            # Try to fetch from yfinance
            self.news_df = try_fetch_yfinance_news(symbol, start_date, end_date)
            
            if self.news_df is not None and not self.news_df.empty:
                self.data_source = "yfinance"
                return True
            else:
                self.news_df = None
                self.data_source = "none"
                return False
                
        except Exception:
            # Graceful degradation
            self.news_df = None
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
        Load news data, trying multiple sources.
        
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
        """Check if news data is available."""
        return self.news_df is not None and not self.news_df.empty
    
    def get_data_source(self) -> str:
        """Get the current data source: 'sample_csv', 'yfinance', or 'none'."""
        return self.data_source
    
    def filter_by_date_range(
        self,
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        symbol: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Filter news by date range and optionally by symbol.
        
        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            symbol: Optional symbol filter (e.g., "SPY")
            
        Returns:
            Filtered DataFrame with columns [Date, Headline, Sentiment, Symbol]
        """
        if not self.is_loaded():
            return pd.DataFrame(columns=["Date", "Headline", "Sentiment", "Symbol"])
        
        # Normalize dates
        start_date = _to_naive_day(start_date)
        end_date = _to_naive_day(end_date)
        
        # Filter by date
        mask = (self.news_df["Date"] >= start_date) & (self.news_df["Date"] <= end_date)
        filtered = self.news_df[mask].copy()
        
        # Filter by symbol if provided and Symbol column exists
        if symbol and "Symbol" in filtered.columns:
            # Handle index-related keywords (e.g., SPY -> S&P 500)
            symbol_upper = symbol.upper()
            
            # Define common index mappings
            index_keywords = {
                "SPY": ["SPY", "S&P", "S&P 500", "SP500"],
                "QQQ": ["QQQ", "NASDAQ", "NASDAQ 100", "NASDAQ-100"],
                "DIA": ["DIA", "DOW", "DOW JONES", "DJIA"],
                "IWM": ["IWM", "RUSSELL", "RUSSELL 2000"],
            }
            
            # Get matching keywords for this symbol
            keywords = index_keywords.get(symbol_upper, [symbol_upper])
            
            # Filter by symbol or related keywords
            symbol_mask = filtered["Symbol"].str.upper().isin([k.upper() for k in keywords])
            filtered = filtered[symbol_mask]
        
        return filtered.sort_values("Date").reset_index(drop=True)
    
    def get_news_by_date(self, date: pd.Timestamp) -> pd.DataFrame:
        """
        Get all news items for a specific date.
        
        Args:
            date: Target date
            
        Returns:
            DataFrame with news for that date
        """
        if not self.is_loaded():
            return pd.DataFrame(columns=["Date", "Headline", "Sentiment", "Symbol"])
        
        date = _to_naive_day(date)
        filtered = self.news_df[self.news_df["Date"] == date].copy()
        
        return filtered.reset_index(drop=True)
