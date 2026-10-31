"""
Multi-asset portfolio backtesting with configurable weights and rebalance frequency.

Default behavior: equal weighting, monthly rebalancing on the first trading day of each month.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Literal
import pandas as pd
import numpy as np

from backtester.data import DataLoader

RebalanceFrequency = Literal["monthly", "weekly", "quarterly", "never"]

REBALANCE_FREQUENCIES: tuple[str, ...] = ("monthly", "weekly", "quarterly", "never")


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


def equal_weights(tickers: List[str]) -> Dict[str, float]:
    """Return equal target weights that sum to 1.0."""
    n = len(tickers)
    if n == 0:
        raise ValueError("At least one ticker required for weights")
    w = 1.0 / n
    return {ticker: w for ticker in tickers}


def normalize_weights(
    weights: Dict[str, float],
    tickers: List[str],
    *,
    require_all_tickers: bool = True,
) -> Dict[str, float]:
    """
    Normalize user weights to sum to 1.0.

    Raises ValueError with a clear message when validation fails.
    """
    if not tickers:
        raise ValueError("Portfolio must have between 2 and 5 tickers")

    missing = [t for t in tickers if t not in weights]
    if require_all_tickers and missing:
        raise ValueError(
            f"Missing weight for ticker(s): {', '.join(missing)}"
        )

    extra = [t for t in weights if t not in tickers]
    if extra:
        raise ValueError(
            f"Unexpected weight for ticker(s) not in portfolio: {', '.join(extra)}"
        )

    raw = {t: float(weights[t]) for t in tickers}
    if any(v < 0 for v in raw.values()):
        raise ValueError("Weights must be non-negative")

    total = sum(raw.values())
    if total <= 0:
        raise ValueError("Weights must sum to a positive value")

    return {t: v / total for t, v in raw.items()}


def compute_inverse_volatility_weights(
    price_data: pd.DataFrame,
    tickers: List[str],
    lookback_days: int = 252,
) -> Dict[str, float]:
    """
    Inverse-volatility weights from trailing daily returns (OHLCV close only).

    Uses the last `lookback_days` of aligned closes; falls back to all rows if shorter.
    """
    if price_data is None or price_data.empty:
        raise ValueError("Price data required to compute inverse-volatility weights")

    returns = price_data[tickers].pct_change().dropna()
    if returns.empty:
        return equal_weights(tickers)

    window = returns.tail(min(lookback_days, len(returns)))
    vols = window.std()
    vols = vols.replace(0, np.nan)

    if vols.isna().all():
        return equal_weights(tickers)

    inv = 1.0 / vols
    inv = inv.fillna(0.0)
    if inv.sum() <= 0:
        return equal_weights(tickers)

    normalized = (inv / inv.sum()).to_dict()
    return {t: float(normalized[t]) for t in tickers}


class PortfolioBacktester:
    """
    Multi-asset portfolio backtester.

    Handles multiple tickers with different trading calendars and missing data.
    Rebalances to target weights on schedule (default: equal weights, monthly).
    """

    def __init__(
        self,
        tickers: List[str],
        start_date: str,
        end_date: str,
        initial_capital: float = 100000.0,
        commission: float = 0.001,
        target_weights: Optional[Dict[str, float]] = None,
        rebalance_frequency: RebalanceFrequency = "monthly",
    ):
        """
        Args:
            tickers: List of 2-5 ticker symbols
            start_date: Start date in 'YYYY-MM-DD' format
            end_date: End date in 'YYYY-MM-DD' format
            initial_capital: Starting capital
            commission: Commission rate as decimal (0.001 = 0.1%)
            target_weights: Optional target weights per ticker (normalized to sum to 1).
                None means equal weight.
            rebalance_frequency: monthly, weekly, quarterly, or never (buy-and-hold after initial).
        """
        if not (2 <= len(tickers) <= 5):
            raise ValueError("Portfolio must have between 2 and 5 tickers")

        if rebalance_frequency not in REBALANCE_FREQUENCIES:
            raise ValueError(
                f"rebalance_frequency must be one of {REBALANCE_FREQUENCIES}, "
                f"got {rebalance_frequency!r}"
            )

        self.tickers = tickers
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.commission = commission
        self.rebalance_frequency: RebalanceFrequency = rebalance_frequency

        self._target_weights: Optional[Dict[str, float]] = None
        if target_weights is not None:
            self.set_target_weights(target_weights)

        self.data: Dict[str, pd.DataFrame] = {}
        self.aligned_data: Optional[pd.DataFrame] = None
        self.equity_curve: Optional[pd.DataFrame] = None
        self.holdings: Dict[str, List[float]] = {ticker: [] for ticker in tickers}

    def set_target_weights(self, weights: Dict[str, float]) -> None:
        """Validate and store normalized target weights."""
        self._target_weights = normalize_weights(weights, self.tickers)

    def apply_inverse_volatility_weights(self, lookback_days: int = 252) -> None:
        """Set target weights from inverse trailing volatility (requires load_data first)."""
        if self.aligned_data is None:
            raise ValueError("Must call load_data() before apply_inverse_volatility_weights()")
        self._target_weights = compute_inverse_volatility_weights(
            self.aligned_data, self.tickers, lookback_days=lookback_days
        )

    def get_target_weights(self) -> Dict[str, float]:
        """Effective target weights (equal weight if none configured)."""
        if self._target_weights is not None:
            return dict(self._target_weights)
        return equal_weights(self.tickers)

    def load_data(self) -> None:
        """
        Load data for all tickers and align to common trading days.

        Handles different trading calendars by using the union of all trading days
        and forward-filling missing data (common practice for multi-asset portfolios).
        """
        loader = DataLoader()

        for ticker in self.tickers:
            try:
                df = loader.fetch_yahoo(
                    symbol=ticker,
                    start_date=self.start_date,
                    end_date=self.end_date,
                )
                if isinstance(df.index, pd.DatetimeIndex) and df.index.tz is not None:
                    df.index = df.index.tz_localize(None)

                self.data[ticker] = df
                print(f"Loaded {len(df)} bars for {ticker}")
            except Exception as e:
                raise ValueError(f"Failed to load data for {ticker}: {str(e)}")

        all_dates = pd.DatetimeIndex(
            sorted(set().union(*[set(df.index) for df in self.data.values()]))
        )

        aligned_closes = {}
        for ticker in self.tickers:
            ticker_closes = self.data[ticker]["Close"].reindex(all_dates)
            ticker_closes = ticker_closes.ffill()

            first_valid = ticker_closes.first_valid_index()
            if first_valid is not None:
                ticker_closes = ticker_closes.loc[first_valid:]

            aligned_closes[ticker] = ticker_closes

        valid_start = max([df.first_valid_index() for df in aligned_closes.values()])
        valid_end = min([df.last_valid_index() for df in aligned_closes.values()])

        self.aligned_data = pd.DataFrame(aligned_closes)
        self.aligned_data = self.aligned_data.loc[valid_start:valid_end]

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
        Rebalance dates based on ``rebalance_frequency``.

        Uses the first trading day in each period present in the aligned index
        (same convention as monthly rebalance before Phase 6d).
        """
        if self.aligned_data is None:
            return []

        dates = pd.DatetimeIndex([pd.Timestamp(d.date()) for d in self.aligned_data.index])
        freq = self.rebalance_frequency

        if freq == "never":
            return [dates[0]]

        rebalance_dates: List[pd.Timestamp] = []
        series = dates.to_series()

        if freq == "monthly":
            groups = series.groupby([dates.year, dates.month])
        elif freq == "weekly":
            iso = dates.isocalendar()
            groups = series.groupby([iso.year, iso.week])
        elif freq == "quarterly":
            groups = series.groupby([dates.year, dates.quarter])
        else:
            raise ValueError(f"Unsupported rebalance frequency: {freq}")

        for _, group in groups:
            rebalance_dates.append(group.min())

        return rebalance_dates

    def run(self) -> pd.DataFrame:
        """
        Execute portfolio backtest with target weights and rebalance schedule.

        Returns:
            DataFrame with columns: Equity, and one column per ticker for holdings value
        """
        if self.aligned_data is None:
            raise ValueError("Must call load_data() before run()")

        target_weights = self.get_target_weights()

        rebalance_dates = self._get_rebalance_dates()
        print(
            f"Rebalancing ({self.rebalance_frequency}) on {len(rebalance_dates)} dates; "
            f"weights: {', '.join(f'{t}:{target_weights[t]*100:.1f}%' for t in self.tickers)}"
        )

        cash = self.initial_capital
        shares = {ticker: 0.0 for ticker in self.tickers}

        equity_history = []
        holdings_history = {ticker: [] for ticker in self.tickers}

        for _, (date, row) in enumerate(self.aligned_data.iterrows()):
            date_naive = pd.Timestamp(date.date())

            if date_naive in rebalance_dates:
                current_value = cash
                for ticker in self.tickers:
                    current_value += shares[ticker] * row[ticker]

                total_commission = 0.0
                for ticker in self.tickers:
                    current_ticker_value = shares[ticker] * row[ticker]
                    target_ticker_value = current_value * target_weights[ticker]

                    trade_value = abs(target_ticker_value - current_ticker_value)
                    commission_cost = trade_value * self.commission
                    total_commission += commission_cost

                    shares[ticker] = target_ticker_value / row[ticker]

                cash = -total_commission

            equity = cash
            for ticker in self.tickers:
                ticker_value = shares[ticker] * row[ticker]
                equity += ticker_value
                holdings_history[ticker].append(ticker_value)

            equity_history.append(equity)

        self.equity_curve = pd.DataFrame(
            {
                "Equity": equity_history,
                **holdings_history,
            },
            index=self.aligned_data.index,
        )

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

        final_equity = equity.iloc[-1]
        total_return_pct = ((final_equity / self.initial_capital) - 1) * 100

        years = len(equity) / 252.0
        if years > 0:
            cagr_pct = (((final_equity / self.initial_capital) ** (1 / years)) - 1) * 100
        else:
            cagr_pct = 0.0

        daily_returns = equity.pct_change().dropna()
        volatility_pct = daily_returns.std() * np.sqrt(252) * 100

        if len(daily_returns) > 1 and daily_returns.std() != 0:
            excess_return = daily_returns.mean() - (risk_free_rate / 252)
            sharpe_ratio = (excess_return / daily_returns.std()) * np.sqrt(252)
        else:
            sharpe_ratio = 0.0

        running_max = equity.expanding().max()
        drawdown = (equity - running_max) / running_max * 100
        max_drawdown_pct = drawdown.min()

        asset_contributions = {}
        for ticker in self.tickers:
            final_ticker_value = self.equity_curve[ticker].iloc[-1]
            contribution_pct = (final_ticker_value / final_equity) * 100
            asset_contributions[ticker] = contribution_pct

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
    """
    loader = DataLoader()

    try:
        data = loader.fetch_yahoo(
            symbol=ticker,
            start_date=start_date,
            end_date=end_date,
        )

        if isinstance(data.index, pd.DatetimeIndex) and data.index.tz is not None:
            data.index = data.index.tz_localize(None)

    except Exception as e:
        print(f"Warning: Could not load benchmark {ticker}: {str(e)}")
        return pd.DataFrame()

    benchmark_closes = data["Close"].reindex(aligned_dates)
    benchmark_closes = benchmark_closes.ffill().dropna()

    if benchmark_closes.empty:
        return pd.DataFrame()

    first_close = benchmark_closes.iloc[0]
    shares = (initial_capital * (1 - commission)) / first_close

    equity_series = shares * benchmark_closes

    return pd.DataFrame(
        {
            "BenchmarkEquity": equity_series
        },
        index=benchmark_closes.index,
    )
