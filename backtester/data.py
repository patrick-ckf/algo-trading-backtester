"""
Data loader and management for backtesting.
Supports CSV loading and yfinance data fetching with caching.
"""

import os
from pathlib import Path
from typing import Optional
import pandas as pd
import yfinance as yf


class DataLoader:
    """Handles OHLCV data loading from CSV or yfinance."""
    
    def __init__(self, cache_dir: str = "data/cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def load_csv(self, filepath: str) -> pd.DataFrame:
        """
        Load OHLCV data from CSV file.
        Expected columns: Date, Open, High, Low, Close, Volume
        """
        df = pd.read_csv(filepath, parse_dates=["Date"], index_col="Date")
        df = df.sort_index()
        self._validate_ohlcv(df)
        return df
    
    def fetch_yahoo(
        self,
        symbol: str,
        start_date: str,
        end_date: Optional[str] = None,
        use_cache: bool = True
    ) -> pd.DataFrame:
        """
        Fetch historical data from Yahoo Finance via yfinance.
        Caches downloaded data locally.
        
        Args:
            symbol: Ticker symbol (e.g., 'SPY', 'AAPL', 'BTC-USD')
            start_date: Start date in 'YYYY-MM-DD' format
            end_date: End date in 'YYYY-MM-DD' format (defaults to today)
            use_cache: Whether to use cached data if available
        """
        cache_file = self.cache_dir / f"{symbol}_{start_date}_{end_date or 'latest'}.csv"
        
        if use_cache and cache_file.exists():
            print(f"Loading cached data for {symbol}")
            return self.load_csv(str(cache_file))
        
        print(f"Fetching data for {symbol} from Yahoo Finance...")
        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start_date, end=end_date)
        
        if df.empty:
            raise ValueError(f"No data returned for {symbol}")
        
        df.index.name = "Date"
        df = df[["Open", "High", "Low", "Close", "Volume"]]
        
        df.to_csv(cache_file)
        print(f"Data cached to {cache_file}")
        
        return df
    
    def _validate_ohlcv(self, df: pd.DataFrame) -> None:
        """Validate that DataFrame has required OHLCV columns."""
        required_cols = ["Open", "High", "Low", "Close", "Volume"]
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
