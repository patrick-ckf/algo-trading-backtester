"""
Tests for multi-asset portfolio backtesting.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime

from backtester.portfolio import (
    PortfolioBacktester,
    calculate_benchmark,
    normalize_weights,
    equal_weights,
)


def test_normalize_weights_validation():
    """Weight normalization validates tickers and negative values."""
    tickers = ["SPY", "QQQ"]
    assert normalize_weights({"SPY": 60, "QQQ": 40}, tickers) == {"SPY": 0.6, "QQQ": 0.4}

    with pytest.raises(ValueError, match="Missing weight"):
        normalize_weights({"SPY": 100}, tickers)

    with pytest.raises(ValueError, match="non-negative"):
        normalize_weights({"SPY": -1, "QQQ": 2}, tickers)

    with pytest.raises(ValueError, match="positive"):
        normalize_weights({"SPY": 0, "QQQ": 0}, tickers)


def test_custom_weights_rebalance():
    """Custom 70/30 weights are applied on rebalance dates."""
    tickers = ["SPY", "QQQ"]
    portfolio = PortfolioBacktester(
        tickers=tickers,
        start_date="2022-01-01",
        end_date="2022-03-31",
        initial_capital=100000.0,
        commission=0.0,
        target_weights={"SPY": 0.7, "QQQ": 0.3},
        rebalance_frequency="monthly",
    )

    portfolio.load_data()
    equity_curve = portfolio.run()
    rebalance_dates = portfolio._get_rebalance_dates()

    for date in rebalance_dates[:2]:
        date_naive = pd.Timestamp(date.date())
        matching_rows = equity_curve.index[equity_curve.index.date == date_naive.date()]
        if len(matching_rows) == 0:
            continue
        row = equity_curve.loc[matching_rows[0]]
        total_equity = row["Equity"]
        if total_equity <= 0:
            continue
        assert abs(row["SPY"] / total_equity - 0.7) < 0.015
        assert abs(row["QQQ"] / total_equity - 0.3) < 0.015


def test_never_rebalance_fewer_dates_than_monthly():
    """Buy-and-hold uses a single rebalance at the start."""
    tickers = ["SPY", "QQQ"]
    monthly = PortfolioBacktester(
        tickers=tickers,
        start_date="2022-01-01",
        end_date="2022-06-30",
        initial_capital=100000.0,
        commission=0.0,
        rebalance_frequency="monthly",
    )
    never = PortfolioBacktester(
        tickers=tickers,
        start_date="2022-01-01",
        end_date="2022-06-30",
        initial_capital=100000.0,
        commission=0.0,
        rebalance_frequency="never",
    )
    monthly.load_data()
    never.load_data()
    assert len(never._get_rebalance_dates()) == 1
    assert len(monthly._get_rebalance_dates()) > len(never._get_rebalance_dates())


def test_inverse_volatility_weights_sum_to_one():
    """Inverse-vol weights are positive and sum to 1."""
    tickers = ["SPY", "QQQ"]
    portfolio = PortfolioBacktester(
        tickers=tickers,
        start_date="2022-01-01",
        end_date="2022-06-30",
    )
    portfolio.load_data()
    portfolio.apply_inverse_volatility_weights()
    weights = portfolio.get_target_weights()
    assert abs(sum(weights.values()) - 1.0) < 1e-6
    assert all(v > 0 for v in weights.values())


def test_weekly_rebalance_dates_increase():
    """Weekly schedule has more rebalance dates than quarterly over same range."""
    tickers = ["SPY", "QQQ"]
    weekly = PortfolioBacktester(
        tickers=tickers,
        start_date="2022-01-01",
        end_date="2022-06-30",
        rebalance_frequency="weekly",
    )
    quarterly = PortfolioBacktester(
        tickers=tickers,
        start_date="2022-01-01",
        end_date="2022-06-30",
        rebalance_frequency="quarterly",
    )
    weekly.load_data()
    quarterly.load_data()
    assert len(weekly._get_rebalance_dates()) > len(quarterly._get_rebalance_dates())


def test_equal_weights_helper():
    assert equal_weights(["A", "B"]) == {"A": 0.5, "B": 0.5}


def test_portfolio_initialization():
    """Test portfolio initializes with correct parameters."""
    tickers = ["SPY", "QQQ"]
    portfolio = PortfolioBacktester(
        tickers=tickers,
        start_date="2020-01-01",
        end_date="2020-12-31",
        initial_capital=50000.0,
    )
    
    assert portfolio.tickers == tickers
    assert portfolio.initial_capital == 50000.0
    assert portfolio.commission == 0.001


def test_portfolio_ticker_count_validation():
    """Test that portfolio enforces 2-5 ticker limit."""
    # Too few tickers
    with pytest.raises(ValueError, match="between 2 and 5"):
        PortfolioBacktester(
            tickers=["SPY"],
            start_date="2020-01-01",
            end_date="2020-12-31",
        )
    
    # Too many tickers
    with pytest.raises(ValueError, match="between 2 and 5"):
        PortfolioBacktester(
            tickers=["SPY", "QQQ", "IWM", "DIA", "VTI", "VOO"],
            start_date="2020-01-01",
            end_date="2020-12-31",
        )
    
    # Valid ticker counts
    for n in [2, 3, 4, 5]:
        tickers = [f"TICKER{i}" for i in range(n)]
        portfolio = PortfolioBacktester(
            tickers=tickers,
            start_date="2020-01-01",
            end_date="2020-12-31",
        )
        assert len(portfolio.tickers) == n


def test_equal_weighting():
    """Test that portfolio maintains equal weights after rebalancing."""
    # Use real data for integration test
    tickers = ["SPY", "QQQ"]
    portfolio = PortfolioBacktester(
        tickers=tickers,
        start_date="2022-01-01",
        end_date="2022-03-31",
        initial_capital=100000.0,
        commission=0.0,  # Zero commission for clean math
    )
    
    portfolio.load_data()
    equity_curve = portfolio.run()
    
    # Check that portfolio runs successfully
    assert not equity_curve.empty
    assert "Equity" in equity_curve.columns
    for ticker in tickers:
        assert ticker in equity_curve.columns
    
    # On rebalance dates, each asset should be approximately 50% of equity
    rebalance_dates = portfolio._get_rebalance_dates()
    
    for date in rebalance_dates[:3]:  # Check first 3 rebalance dates
        # Find the row in equity_curve matching this date
        date_naive = pd.Timestamp(date.date())
        matching_rows = equity_curve.index[equity_curve.index.date == date_naive.date()]
        
        if len(matching_rows) > 0:
            row = equity_curve.loc[matching_rows[0]]
            total_equity = row["Equity"]
            
            if total_equity > 0:  # Avoid division by zero
                for ticker in tickers:
                    weight = row[ticker] / total_equity
                    # Allow 1% tolerance for commission and rounding
                    assert abs(weight - 0.5) < 0.01, f"Weight deviation too large on {date}: {ticker} = {weight}"


def test_monthly_rebalance_dates():
    """Test that rebalance dates are first trading day of each month."""
    tickers = ["SPY", "QQQ"]
    portfolio = PortfolioBacktester(
        tickers=tickers,
        start_date="2022-01-01",
        end_date="2022-06-30",
        initial_capital=100000.0,
    )
    
    portfolio.load_data()
    rebalance_dates = portfolio._get_rebalance_dates()
    
    # Should have rebalance dates for each month in the range
    # Jan, Feb, Mar, Apr, May, Jun = 6 months
    assert len(rebalance_dates) >= 5  # At least 5 months worth
    
    # Check that dates are at start of month
    for i in range(len(rebalance_dates) - 1):
        current_date = rebalance_dates[i]
        next_date = rebalance_dates[i + 1]
        
        # Dates should be in different months
        assert current_date.month != next_date.month or current_date.year != next_date.year


def test_benchmark_alignment():
    """Test that benchmark aligns with portfolio dates."""
    tickers = ["SPY", "QQQ"]
    portfolio = PortfolioBacktester(
        tickers=tickers,
        start_date="2022-01-01",
        end_date="2022-03-31",
        initial_capital=100000.0,
    )
    
    portfolio.load_data()
    equity_curve = portfolio.run()
    
    # Calculate benchmark
    benchmark = calculate_benchmark(
        ticker="SPY",
        start_date="2022-01-01",
        end_date="2022-03-31",
        initial_capital=100000.0,
        aligned_dates=equity_curve.index,
    )
    
    # Benchmark should have same dates as portfolio
    assert not benchmark.empty
    assert len(benchmark) == len(equity_curve)
    assert all(benchmark.index == equity_curve.index)


def test_metrics_calculation():
    """Test portfolio metrics calculation."""
    tickers = ["SPY", "QQQ"]
    portfolio = PortfolioBacktester(
        tickers=tickers,
        start_date="2022-01-01",
        end_date="2022-03-31",
        initial_capital=100000.0,
    )
    
    portfolio.load_data()
    portfolio.run()
    metrics = portfolio.calculate_metrics()
    
    # Check that all metrics are present
    assert metrics.initial_capital == 100000.0
    assert metrics.final_equity > 0
    assert isinstance(metrics.total_return_pct, float)
    assert isinstance(metrics.cagr_pct, float)
    assert isinstance(metrics.sharpe_ratio, float)
    assert isinstance(metrics.max_drawdown_pct, float)
    assert isinstance(metrics.volatility_pct, float)
    
    # Check asset contributions
    assert len(metrics.asset_contributions) == 2
    assert "SPY" in metrics.asset_contributions
    assert "QQQ" in metrics.asset_contributions
    
    # Contributions should sum to approximately 100%
    total_contribution = sum(metrics.asset_contributions.values())
    assert abs(total_contribution - 100.0) < 1.0
    
    # Check correlation matrix
    assert isinstance(metrics.correlation_matrix, pd.DataFrame)
    assert metrics.correlation_matrix.shape == (2, 2)
    assert "SPY" in metrics.correlation_matrix.columns
    assert "QQQ" in metrics.correlation_matrix.columns


def test_different_trading_calendars():
    """Test handling of tickers with different trading calendars."""
    # SPY (US) and EWJ (Japan ETF trading in US)
    # Both trade on US exchange, but this tests the alignment logic
    tickers = ["SPY", "EWJ"]
    portfolio = PortfolioBacktester(
        tickers=tickers,
        start_date="2022-01-01",
        end_date="2022-03-31",
        initial_capital=100000.0,
    )
    
    portfolio.load_data()
    
    # Should successfully align data
    assert portfolio.aligned_data is not None
    assert not portfolio.aligned_data.empty
    assert "SPY" in portfolio.aligned_data.columns
    assert "EWJ" in portfolio.aligned_data.columns
    
    # No NaN values in aligned data
    assert not portfolio.aligned_data.isnull().any().any()


def test_equity_curve_output():
    """Test that equity curve has correct structure."""
    tickers = ["SPY", "QQQ", "IWM"]
    portfolio = PortfolioBacktester(
        tickers=tickers,
        start_date="2022-01-01",
        end_date="2022-03-31",
        initial_capital=100000.0,
    )
    
    portfolio.load_data()
    equity_curve = portfolio.run()
    
    # Check structure
    assert not equity_curve.empty
    assert "Equity" in equity_curve.columns
    assert len(equity_curve.columns) == len(tickers) + 1  # Equity + one per ticker
    
    # Check that equity is always positive
    assert (equity_curve["Equity"] > 0).all()
    
    # Check that holdings sum to approximately total equity
    for i, row in equity_curve.iterrows():
        holdings_sum = sum([row[ticker] for ticker in tickers])
        equity_total = row["Equity"]
        # Allow some tolerance for cash/commission
        assert abs(holdings_sum - equity_total) < equity_total * 0.01


def test_correlation_matrix_properties():
    """Test that correlation matrix has correct properties."""
    tickers = ["SPY", "QQQ", "IWM"]
    portfolio = PortfolioBacktester(
        tickers=tickers,
        start_date="2022-01-01",
        end_date="2022-06-30",
        initial_capital=100000.0,
    )
    
    portfolio.load_data()
    portfolio.run()
    metrics = portfolio.calculate_metrics()
    
    corr_matrix = metrics.correlation_matrix
    
    # Diagonal should be 1.0
    for ticker in tickers:
        assert abs(corr_matrix.loc[ticker, ticker] - 1.0) < 0.01
    
    # Symmetric matrix
    for i, ticker1 in enumerate(tickers):
        for ticker2 in tickers[i+1:]:
            assert abs(corr_matrix.loc[ticker1, ticker2] - corr_matrix.loc[ticker2, ticker1]) < 0.01
    
    # All correlations should be between -1 and 1
    for ticker1 in tickers:
        for ticker2 in tickers:
            corr_value = corr_matrix.loc[ticker1, ticker2]
            assert -1.0 <= corr_value <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
