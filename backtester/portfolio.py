"""
Multi-asset portfolio backtesting with equal weighting and monthly rebalancing.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import pandas as pd
import numpy as np
from datetime import datetime

from backtester.data import DataLoader


@dataclass
class PortfolioMetrics:
    """Portfolio performance metrics."""
    initial_capital: float
    final_equity: float
    total_return_pct: float
    cagr_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    volatility_pct: float
    asset_contributions: Dict[str, float]
    correlation_matrix: pd.DataFrame


class PortfolioBacktester:
    """
    Multi-asset portfolio backtester with equal weighting and monthly rebalancing.
    
    Handles multiple tickers with different trading calendars and missing data.
    Rebalances to equal weights on the first trading day of each month.
    """
    
    def __init__(
        self,
        tickers: List[str],
        start_date: str,
        end_date: str,
        initial_capital: float = 100000.0,
        commission: float = 0.001,
    ):
        """
        Args:
            tickers: List of 2-5 ticker symbols
            start_date: Start date in 'YYYY-MM-DD' format
            end_date: End date in 'YYYY-MM-DD' format
            initial_capital: Starting capital
            commission: Commission rate as decimal (0.001 = 0.1%)
        """
        if not (2 <= len(tickers) <= 5):
            raise ValueError("Portfolio must have between 2 and 5 tickers")
        
        self.tickers = tickers
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.commission = commission
        
        self.data: Dict[str, pd.DataFrame] = {}
        self.aligned_data: Optional[pd.DataFrame] = None
        self.equity_curve: Optional[pd.DataFrame] = None
        self.holdings: Dict[str, List[float]] = {ticker: [] for ticker in tickers}
        
    def load_data(self) -> None:
        """
        Load data for all tickers and align to common trading days.
        
        Handles different trading calendars by using the union of all trading days
        and forward-filling missing data (common practice for multi-asset portfolios).
        """
        loader = DataLoader()
        
        # Load data for each ticker
        for ticker in self.tickers:
            try:
                df = loader.fetch_yahoo(
                    symbol=ticker,
                    start_date=self.start_date,
                    end_date=self.end_date,
                )
                # Normalize timezone-aware index to naive UTC dates to avoid alignment bugs
                # yfinance returns tz-aware timestamps, but we only care about the date
                if isinstance(df.index, pd.DatetimeIndex) and df.index.tz is not None:
                    df.index = df.index.tz_localize(None)
                
                self.data[ticker] = df
                print(f"Loaded {len(df)} bars for {ticker}")
            except Exception as e:
                raise ValueError(f"Failed to load data for {ticker}: {str(e)}")
        
        # Align data to common date index (union of all dates)
        # This handles different trading calendars (e.g., US vs international markets)
        # All dates are now tz-naive, safe to sort
        all_dates = pd.DatetimeIndex(sorted(set().union(*[set(df.index) for df in self.data.values()])))
        
        # Create aligned dataframe with Close prices for all tickers
        aligned_closes = {}
        for ticker in self.tickers:
            # Reindex to all dates and forward-fill missing values
            # This is standard practice for multi-asset portfolios
            ticker_closes = self.data[ticker]["Close"].reindex(all_dates)
            
            # Forward fill missing data (common for holidays/different calendars)
            ticker_closes = ticker_closes.ffill()
            
            # Drop any leading NaN values (before data starts)
            first_valid = ticker_closes.first_valid_index()
            if first_valid is not None:
                ticker_closes = ticker_closes.loc[first_valid:]
            
            aligned_closes[ticker] = ticker_closes
        
        # Find common date range where all tickers have data
        # Use the latest start date and earliest end date among all tickers
        valid_start = max([df.first_valid_index() for df in aligned_closes.values()])
        valid_end = min([df.last_valid_index() for df in aligned_closes.values()])
        
        # Create final aligned dataframe
        self.aligned_data = pd.DataFrame(aligned_closes)
        self.aligned_data = self.aligned_data.loc[valid_start:valid_end]
        
        # Drop any rows with remaining NaN values
        initial_len = len(self.aligned_data)
        self.aligned_data = self.aligned_data.dropna()
        final_len = len(self.aligned_data)
        
        if final_len < initial_len:
            print(f"Dropped {initial_len - final_len} rows with missing data")
        
        if self.aligned_data.empty:
            raise ValueError("No overlapping data found for all tickers")
        
        print(f"Aligned data: {len(self.aligned_data)} common trading days")
        print(f"Date range: {self.aligned_data.index[0]} to {self.aligned_data.index[-1]}")
    
    def _get_rebalance_dates(self) -> List[pd.Timestamp]:
        """
        Get monthly rebalance dates (first trading day of each month).
        
        Converts timezone-aware dates to naive dates for comparison to avoid
        timezone-related bugs.
        """
        if self.aligned_data is None:
            return []
        
        # Convert index to naive dates for consistent comparison
        dates = pd.DatetimeIndex([pd.Timestamp(d.date()) for d in self.aligned_data.index])
        
        # Group by year-month and take first trading day of each month
        rebalance_dates = []
        year_month_groups = dates.to_series().groupby([dates.year.values, dates.month.values])
        for year_month, group in year_month_groups:
            first_day = group.min()
            rebalance_dates.append(first_day)
        
        return rebalance_dates
    
    def run(self) -> pd.DataFrame:
        """
        Execute portfolio backtest with equal weighting and monthly rebalancing.
        
        Returns:
            DataFrame with columns: Date, Equity, and one column per ticker for holdings
        """
        if self.aligned_data is None:
            raise ValueError("Must call load_data() before run()")
        
        n_assets = len(self.tickers)
        target_weight = 1.0 / n_assets
        
        rebalance_dates = self._get_rebalance_dates()
        print(f"Rebalancing on {len(rebalance_dates)} monthly dates")
        
        # Initialize holdings
        cash = self.initial_capital
        shares = {ticker: 0.0 for ticker in self.tickers}
        
        equity_history = []
        holdings_history = {ticker: [] for ticker in self.tickers}
        
        for i, (date, row) in enumerate(self.aligned_data.iterrows()):
            # Normalize date to naive for comparison
            date_naive = pd.Timestamp(date.date())
            
            # Check if this is a rebalance date
            if date_naive in rebalance_dates:
                # Calculate current portfolio value
                current_value = cash
                for ticker in self.tickers:
                    current_value += shares[ticker] * row[ticker]
                
                # Rebalance to equal weights
                target_value_per_asset = current_value * target_weight
                
                total_commission = 0.0
                for ticker in self.tickers:
                    current_ticker_value = shares[ticker] * row[ticker]
                    target_ticker_value = target_value_per_asset
                    
                    # Calculate rebalance trade
                    trade_value = abs(target_ticker_value - current_ticker_value)
                    commission_cost = trade_value * self.commission
                    total_commission += commission_cost
                    
                    # Update shares to target allocation
                    new_shares = target_ticker_value / row[ticker]
                    shares[ticker] = new_shares
                
                # Deduct total commission from cash
                # After rebalancing, cash should be near zero (fully invested)
                cash = -total_commission
            
            # Calculate current equity
            equity = cash
            for ticker in self.tickers:
                ticker_value = shares[ticker] * row[ticker]
                equity += ticker_value
                holdings_history[ticker].append(ticker_value)
            
            equity_history.append(equity)
        
        # Create equity curve dataframe
        self.equity_curve = pd.DataFrame({
            "Equity": equity_history,
            **holdings_history,
        }, index=self.aligned_data.index)
        
        return self.equity_curve
    
    def calculate_metrics(
        self,
        benchmark_data: Optional[pd.DataFrame] = None,
        risk_free_rate: float = 0.0,
    ) -> PortfolioMetrics:
        """
        Calculate portfolio performance metrics.
        
        Args:
            benchmark_data: Optional DataFrame with benchmark equity curve
            risk_free_rate: Annual risk-free rate for Sharpe calculation
            
        Returns:
            PortfolioMetrics with all performance statistics
        """
        if self.equity_curve is None:
            raise ValueError("Must call run() before calculate_metrics()")
        
        equity = self.equity_curve["Equity"]
        
        # Basic metrics
        final_equity = equity.iloc[-1]
        total_return_pct = ((final_equity / self.initial_capital) - 1) * 100
        
        # CAGR
        years = len(equity) / 252.0
        if years > 0:
            cagr_pct = (((final_equity / self.initial_capital) ** (1 / years)) - 1) * 100
        else:
            cagr_pct = 0.0
        
        # Volatility (annualized)
        daily_returns = equity.pct_change().dropna()
        volatility_pct = daily_returns.std() * np.sqrt(252) * 100
        
        # Sharpe ratio
        if len(daily_returns) > 1 and daily_returns.std() != 0:
            excess_return = daily_returns.mean() - (risk_free_rate / 252)
            sharpe_ratio = (excess_return / daily_returns.std()) * np.sqrt(252)
        else:
            sharpe_ratio = 0.0
        
        # Max drawdown
        running_max = equity.expanding().max()
        drawdown = (equity - running_max) / running_max * 100
        max_drawdown_pct = drawdown.min()
        
        # Asset contributions (percentage of final equity)
        asset_contributions = {}
        for ticker in self.tickers:
            final_ticker_value = self.equity_curve[ticker].iloc[-1]
            contribution_pct = (final_ticker_value / final_equity) * 100
            asset_contributions[ticker] = contribution_pct
        
        # Correlation matrix
        returns_data = {}
        for ticker in self.tickers:
            ticker_returns = self.aligned_data[ticker].pct_change().dropna()
            returns_data[ticker] = ticker_returns
        
        returns_df = pd.DataFrame(returns_data)
        correlation_matrix = returns_df.corr()
        
        return PortfolioMetrics(
            initial_capital=self.initial_capital,
            final_equity=final_equity,
            total_return_pct=total_return_pct,
            cagr_pct=cagr_pct,
            sharpe_ratio=sharpe_ratio,
            max_drawdown_pct=max_drawdown_pct,
            volatility_pct=volatility_pct,
            asset_contributions=asset_contributions,
            correlation_matrix=correlation_matrix,
        )


def calculate_benchmark(
    ticker: str,
    start_date: str,
    end_date: str,
    initial_capital: float,
    aligned_dates: pd.DatetimeIndex,
    commission: float = 0.0,
) -> pd.DataFrame:
    """
    Calculate buy-and-hold benchmark for a single ticker.
    
    Aligns the benchmark to the same dates as the portfolio for fair comparison.
    
    Args:
        ticker: Benchmark ticker (e.g., 'SPY')
        start_date: Start date
        end_date: End date
        initial_capital: Starting capital
        aligned_dates: DatetimeIndex to align benchmark to (from portfolio)
        commission: Commission rate
        
    Returns:
        DataFrame with BenchmarkEquity column
    """
    loader = DataLoader()
    
    try:
        data = loader.fetch_yahoo(
            symbol=ticker,
            start_date=start_date,
            end_date=end_date,
        )
        
        # Normalize timezone-aware index to naive
        if isinstance(data.index, pd.DatetimeIndex) and data.index.tz is not None:
            data.index = data.index.tz_localize(None)
            
    except Exception as e:
        print(f"Warning: Could not load benchmark {ticker}: {str(e)}")
        return pd.DataFrame()
    
    # Align benchmark to portfolio dates
    benchmark_closes = data["Close"].reindex(aligned_dates)
    benchmark_closes = benchmark_closes.ffill().dropna()
    
    if benchmark_closes.empty:
        return pd.DataFrame()
    
    # Buy and hold from first available date
    first_close = benchmark_closes.iloc[0]
    shares = (initial_capital * (1 - commission)) / first_close
    
    equity_series = shares * benchmark_closes
    
    return pd.DataFrame({
        "BenchmarkEquity": equity_series
    }, index=benchmark_closes.index)
