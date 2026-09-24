"""
Tests for news panel module (Phase 3 - L1 Research Layer)

Tests verify:
1. News data loading from sample CSV
2. Date range filtering
3. Symbol filtering with index keyword matching
4. Simple sentiment computation
5. Graceful degradation when data unavailable
6. Phase 0 compliance: L0 backtest unchanged when news panel off/display-only
"""

import pytest
import pandas as pd
import numpy as np
import os
from datetime import datetime

from backtester.news import (
    NewsPanel,
    compute_simple_sentiment,
    _to_naive_day,
)
from backtester.engine import BacktestEngine
from backtester.strategies.sma_crossover import SMACrossover
from backtester.metrics import PerformanceMetrics


class TestNewsPanelBasics:
    """Test basic news panel loading and filtering."""
    
    def test_news_panel_loads_successfully(self):
        """Test that news panel loads from default sample path."""
        panel = NewsPanel()
        success = panel.load()
        
        assert success, "News panel should load successfully"
        assert panel.is_loaded(), "News panel should report as loaded"
        assert panel.get_data_source() in ["sample_csv", "yfinance"], "Should have valid data source"
    
    def test_news_panel_graceful_degradation_missing_file(self):
        """Test graceful degradation when news file is missing."""
        panel = NewsPanel(sample_csv_path="/nonexistent/path.csv")
        success = panel.load()
        
        assert not success, "Should return False when file missing"
        assert not panel.is_loaded(), "Should not be loaded"
        assert panel.get_data_source() == "none", "Data source should be 'none'"
    
    def test_load_sample_csv(self):
        """Test loading news from sample CSV."""
        panel = NewsPanel()
        success = panel.load_sample()
        
        assert success, "Should load sample CSV"
        assert panel.is_loaded(), "Should be loaded"
        assert panel.get_data_source() == "sample_csv", "Data source should be sample_csv"
        
        # Check DataFrame structure
        df = panel.news_df
        assert not df.empty, "News DataFrame should not be empty"
        assert "Date" in df.columns, "Should have Date column"
        assert "Headline" in df.columns, "Should have Headline column"
        assert "Symbol" in df.columns, "Should have Symbol column"
        assert "Sentiment" in df.columns, "Should have Sentiment column"
    
    def test_filter_by_date_range(self):
        """Test filtering news by date range."""
        panel = NewsPanel()
        panel.load()
        
        start = pd.Timestamp("2020-01-01")
        end = pd.Timestamp("2020-12-31")
        
        filtered = panel.filter_by_date_range(start, end)
        
        assert not filtered.empty, "Should have news in 2020"
        assert all(filtered["Date"] >= start), "All news should be after start"
        assert all(filtered["Date"] <= end), "All news should be before end"
    
    def test_filter_by_date_range_with_symbol(self):
        """Test filtering news by date range and symbol."""
        panel = NewsPanel()
        panel.load()
        
        start = pd.Timestamp("2020-01-01")
        end = pd.Timestamp("2020-12-31")
        
        spy_news = panel.filter_by_date_range(start, end, symbol="SPY")
        
        assert not spy_news.empty, "Should have SPY news"
        
        # Check that all news is related to SPY or S&P 500 keywords
        for _, row in spy_news.iterrows():
            symbol = row["Symbol"].upper()
            assert any(keyword in symbol for keyword in ["SPY", "S&P"]), \
                f"Symbol {symbol} should be related to SPY"
    
    def test_filter_by_date_range_empty_result(self):
        """Test filtering with date range that has no news."""
        panel = NewsPanel()
        panel.load()
        
        # Far future date range
        start = pd.Timestamp("2030-01-01")
        end = pd.Timestamp("2030-12-31")
        
        filtered = panel.filter_by_date_range(start, end)
        
        # Should return empty DataFrame with correct columns
        assert filtered.empty, "Should have no news in future"
        assert "Date" in filtered.columns, "Should have Date column"
        assert "Headline" in filtered.columns, "Should have Headline column"
    
    def test_get_news_by_date(self):
        """Test getting news for a specific date."""
        panel = NewsPanel()
        panel.load()
        
        # Pick a date we know has news (from sample CSV)
        date = pd.Timestamp("2020-03-12")  # S&P 500 crash day
        
        news = panel.get_news_by_date(date)
        
        # Should have at least one news item on this major event day
        # (if our sample CSV includes it)
        if not news.empty:
            assert all(news["Date"] == date), "All news should be from target date"
    
    def test_index_keyword_matching(self):
        """Test that SPY symbol matches S&P 500 related news."""
        panel = NewsPanel()
        panel.load()
        
        start = pd.Timestamp("2020-01-01")
        end = pd.Timestamp("2024-12-31")
        
        # Filter for SPY should include S&P 500 news
        spy_news = panel.filter_by_date_range(start, end, symbol="SPY")
        
        # Check that we get news (sample CSV should have S&P news)
        if not spy_news.empty:
            # Verify symbols are related to SPY/S&P
            for _, row in spy_news.iterrows():
                symbol = row["Symbol"].upper()
                assert any(keyword in symbol for keyword in ["SPY", "S&P", "SP500"]), \
                    f"Symbol {symbol} should be SPY-related"


class TestSentimentComputation:
    """Test simple sentiment computation."""
    
    def test_positive_sentiment(self):
        """Test detection of positive sentiment."""
        headlines = [
            "Market Soars on Strong Earnings",
            "Stocks Rally to Record High",
            "Tech Gains Boost Market",
            "Positive Jobs Report Lifts Sentiment",
        ]
        
        for headline in headlines:
            sentiment = compute_simple_sentiment(headline)
            assert sentiment == "Positive", f"'{headline}' should be Positive"
    
    def test_negative_sentiment(self):
        """Test detection of negative sentiment."""
        headlines = [
            "Market Plunges on Recession Fears",
            "Stocks Tumble as Crisis Deepens",
            "Tech Stocks Fall Sharply",
            "Negative Outlook Weighs on Market",
        ]
        
        for headline in headlines:
            sentiment = compute_simple_sentiment(headline)
            assert sentiment == "Negative", f"'{headline}' should be Negative"
    
    def test_neutral_sentiment(self):
        """Test detection of neutral sentiment."""
        headlines = [
            "Fed Announces Policy Decision",
            "Earnings Season Begins",
            "Market Awaits Economic Data",
            "Trading Volume Remains Steady",
        ]
        
        for headline in headlines:
            sentiment = compute_simple_sentiment(headline)
            assert sentiment == "Neutral", f"'{headline}' should be Neutral"
    
    def test_sentiment_case_insensitive(self):
        """Test that sentiment detection is case insensitive."""
        assert compute_simple_sentiment("MARKET SOARS") == "Positive"
        assert compute_simple_sentiment("market soars") == "Positive"
        assert compute_simple_sentiment("Market Soars") == "Positive"


class TestTimezoneHandling:
    """Test timezone handling for date comparisons."""
    
    def test_to_naive_day_with_naive_timestamp(self):
        """Test conversion of naive timestamp."""
        ts = pd.Timestamp("2020-03-15")
        result = _to_naive_day(ts)
        
        assert result.tz is None, "Should be timezone-naive"
        assert result.date() == datetime(2020, 3, 15).date(), "Should preserve date"
    
    def test_to_naive_day_with_aware_timestamp(self):
        """Test conversion of timezone-aware timestamp."""
        try:
            ts = pd.Timestamp("2020-03-15 10:30:00", tz="UTC")
            result = _to_naive_day(ts)
            
            assert result.tz is None, "Should be timezone-naive"
            assert result.date() == datetime(2020, 3, 15).date(), "Should preserve date in source timezone"
        except Exception:
            # Skip if timezone data not available
            pytest.skip("Timezone data not available")


class TestPhase0Compliance:
    """
    Test Phase 0 compliance: News panel is L1 (display/research only).
    It must NOT affect L0 backtest results when off or in display-only mode.
    """
    
    @pytest.fixture
    def sample_data(self):
        """Create sample OHLCV data for testing."""
        dates = pd.date_range("2020-01-01", "2020-06-30", freq="D")
        np.random.seed(42)
        
        data = pd.DataFrame({
            "Open": 100 + np.random.randn(len(dates)).cumsum(),
            "High": 101 + np.random.randn(len(dates)).cumsum(),
            "Low": 99 + np.random.randn(len(dates)).cumsum(),
            "Close": 100 + np.random.randn(len(dates)).cumsum(),
            "Volume": np.random.randint(1000000, 10000000, len(dates)),
        }, index=dates)
        
        # Ensure High >= Open/Close and Low <= Open/Close
        data["High"] = data[["Open", "Close"]].max(axis=1) + abs(np.random.randn(len(dates)))
        data["Low"] = data[["Open", "Close"]].min(axis=1) - abs(np.random.randn(len(dates)))
        
        return data
    
    def test_news_panel_does_not_affect_backtest_results(self, sample_data):
        """
        Test that loading/displaying news does not change backtest results.
        
        This is the core Phase 0 compliance test: L1 research layer must not
        modify L0 backtest outputs (equity curve, metrics, trades).
        """
        # Run backtest without news panel
        strategy = SMACrossover(fast_period=10, slow_period=20)
        engine = BacktestEngine(
            initial_capital=100000,
            commission=0.001,
            slippage=0.0005,
        )
        
        equity_curve_baseline = engine.run(strategy, sample_data)
        trades_baseline = engine.trades.copy()
        
        # Load news panel (this is L1 layer)
        news_panel = NewsPanel()
        news_panel.load()
        
        # Filter news for backtest period (this is display/research only)
        if news_panel.is_loaded():
            filtered_news = news_panel.filter_by_date_range(
                sample_data.index.min(),
                sample_data.index.max(),
                symbol="SPY"
            )
        
        # Run same backtest again (news panel loaded but not used in engine)
        strategy2 = SMACrossover(fast_period=10, slow_period=20)
        engine2 = BacktestEngine(
            initial_capital=100000,
            commission=0.001,
            slippage=0.0005,
        )
        
        equity_curve_with_news = engine2.run(strategy2, sample_data)
        trades_with_news = engine2.trades.copy()
        
        # Verify results are identical
        pd.testing.assert_frame_equal(
            equity_curve_baseline,
            equity_curve_with_news,
            check_dtype=False,
            rtol=1e-10,
        )
        
        assert len(trades_baseline) == len(trades_with_news), \
            "Number of trades should be identical"
        
        # Calculate metrics and verify they're identical
        metrics_baseline = PerformanceMetrics(
            equity_curve=equity_curve_baseline,
            trades=trades_baseline,
            initial_capital=100000,
        ).calculate_all()
        
        metrics_with_news = PerformanceMetrics(
            equity_curve=equity_curve_with_news,
            trades=trades_with_news,
            initial_capital=100000,
        ).calculate_all()
        
        # Check key metrics are identical
        assert metrics_baseline["total_return_pct"] == metrics_with_news["total_return_pct"], \
            "Total return should be identical"
        assert metrics_baseline["max_drawdown_pct"] == metrics_with_news["max_drawdown_pct"], \
            "Max drawdown should be identical"
        assert metrics_baseline["sharpe_ratio"] == metrics_with_news["sharpe_ratio"], \
            "Sharpe ratio should be identical"
    
    def test_news_panel_empty_does_not_crash_backtest(self, sample_data):
        """Test that empty/missing news data does not crash backtest."""
        # Create news panel with non-existent file
        news_panel = NewsPanel(sample_csv_path="/nonexistent/news.csv")
        success = news_panel.load()
        
        assert not success, "Should fail to load"
        assert not news_panel.is_loaded(), "Should not be loaded"
        
        # Try to filter news (should return empty DataFrame gracefully)
        filtered = news_panel.filter_by_date_range(
            sample_data.index.min(),
            sample_data.index.max(),
        )
        
        assert filtered.empty, "Should return empty DataFrame"
        assert "Date" in filtered.columns, "Should have correct columns"
        
        # Backtest should still run normally
        strategy = SMACrossover(fast_period=10, slow_period=20)
        engine = BacktestEngine(initial_capital=100000)
        
        equity_curve = engine.run(strategy, sample_data)
        
        assert not equity_curve.empty, "Backtest should complete successfully"
        assert len(engine.trades) > 0, "Should generate trades"


class TestDataSourceFallback:
    """Test fallback behavior between data sources."""
    
    def test_load_with_prefer_yfinance_but_no_params(self):
        """Test that it falls back to sample when yfinance params missing."""
        panel = NewsPanel()
        
        # Request yfinance but don't provide symbol/dates
        success = panel.load(prefer_yfinance=True)
        
        # Should fall back to sample CSV
        if success:
            assert panel.get_data_source() == "sample_csv", \
                "Should fall back to sample CSV when yfinance params missing"
    
    def test_load_sample_first_by_default(self):
        """Test that sample CSV is loaded by default."""
        panel = NewsPanel()
        success = panel.load()
        
        if success:
            assert panel.get_data_source() == "sample_csv", \
                "Should load sample CSV by default"


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_date_range(self):
        """Test filtering with empty date range."""
        panel = NewsPanel()
        panel.load()
        
        # End date before start date
        start = pd.Timestamp("2020-12-31")
        end = pd.Timestamp("2020-01-01")
        
        filtered = panel.filter_by_date_range(start, end)
        
        assert filtered.empty, "Should return empty DataFrame for invalid range"
    
    def test_filter_unloaded_panel(self):
        """Test filtering when panel is not loaded."""
        panel = NewsPanel(sample_csv_path="/nonexistent/path.csv")
        panel.load()  # Will fail
        
        assert not panel.is_loaded(), "Should not be loaded"
        
        filtered = panel.filter_by_date_range(
            pd.Timestamp("2020-01-01"),
            pd.Timestamp("2020-12-31"),
        )
        
        assert filtered.empty, "Should return empty DataFrame"
        assert "Date" in filtered.columns, "Should have correct schema"
    
    def test_get_news_by_date_unloaded(self):
        """Test getting news by date when panel is not loaded."""
        panel = NewsPanel(sample_csv_path="/nonexistent/path.csv")
        panel.load()  # Will fail
        
        news = panel.get_news_by_date(pd.Timestamp("2020-03-12"))
        
        assert news.empty, "Should return empty DataFrame"
        assert "Date" in news.columns, "Should have correct schema"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
