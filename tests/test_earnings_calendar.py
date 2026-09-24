"""
Tests for earnings calendar module (Phase 4 - L1 Research Layer)

Tests verify:
1. Calendar data loading and filtering
2. Event date extraction
3. Exclusion window creation (research filter)
4. Trade filtering (research filter)
5. Graceful degradation when calendar unavailable
6. Index/ETF detection and handling
7. Phase 0 compliance: L0 backtest unchanged when calendar off/display-only
"""

import pytest
import pandas as pd
import numpy as np
import os
from datetime import datetime

from backtester.earnings_calendar import (
    EarningsCalendar,
    calculate_research_metrics,
    is_index_or_etf,
    try_fetch_yfinance_earnings,
)
from backtester.engine import BacktestEngine, Trade
from backtester.strategies.sma_crossover import SMACrossover
from backtester.metrics import PerformanceMetrics


class TestEarningsCalendarBasics:
    """Test basic calendar loading and filtering."""
    
    def test_calendar_loads_successfully(self):
        """Test that earnings calendar loads from default path."""
        calendar = EarningsCalendar()
        success = calendar.load()
        
        assert success, "Calendar should load successfully"
        assert calendar.is_loaded(), "Calendar should report as loaded"
        assert len(calendar.get_available_symbols()) > 0, "Should have symbols"
        assert len(calendar.get_available_types()) > 0, "Should have event types"
    
    def test_calendar_graceful_degradation_missing_file(self):
        """Test graceful degradation when calendar file is missing."""
        calendar = EarningsCalendar(sample_csv_path="/nonexistent/path.csv")
        success = calendar.load()
        
        assert not success, "Should return False when file missing"
        assert not calendar.is_loaded(), "Should not be loaded"
        assert len(calendar.get_available_symbols()) == 0, "Should have no symbols"
    
    def test_get_available_symbols(self):
        """Test getting available symbols."""
        calendar = EarningsCalendar()
        calendar.load()
        
        symbols = calendar.get_available_symbols()
        
        # Check expected symbols are present (based on our sample CSV)
        assert "AAPL" in symbols, "Should have AAPL events"
        assert "MSFT" in symbols, "Should have MSFT events"
        assert "GOOGL" in symbols, "Should have GOOGL events"
    
    def test_get_available_types(self):
        """Test getting available event types."""
        calendar = EarningsCalendar()
        calendar.load()
        
        types = calendar.get_available_types()
        
        # Check that we have earnings type
        assert "Earnings" in types, "Should have Earnings type"
    
    def test_filter_by_date_range_all_symbols(self):
        """Test filtering events by date range."""
        calendar = EarningsCalendar()
        calendar.load()
        
        start = pd.Timestamp("2020-01-01")
        end = pd.Timestamp("2020-12-31")
        
        events = calendar.filter_by_date_range(start, end)
        
        assert not events.empty, "Should have events in 2020"
        assert all(events["Date"] >= start), "All events should be after start"
        assert all(events["Date"] <= end), "All events should be before end"
        assert "Date" in events.columns, "Should have Date column"
        assert "Event" in events.columns, "Should have Event column"
        assert "Type" in events.columns, "Should have Type column"
        assert "Symbol" in events.columns, "Should have Symbol column"
    
    def test_filter_by_date_range_specific_symbol(self):
        """Test filtering events by date range and symbol."""
        calendar = EarningsCalendar()
        calendar.load()
        
        start = pd.Timestamp("2020-01-01")
        end = pd.Timestamp("2020-12-31")
        
        events = calendar.filter_by_date_range(start, end, symbol="AAPL")
        
        assert not events.empty, "Should have AAPL events in 2020"
        assert all(events["Symbol"] == "AAPL"), "All events should be for AAPL"
    
    def test_filter_by_date_range_specific_type(self):
        """Test filtering events by date range and type."""
        calendar = EarningsCalendar()
        calendar.load()
        
        start = pd.Timestamp("2020-01-01")
        end = pd.Timestamp("2020-12-31")
        
        events = calendar.filter_by_date_range(start, end, event_types=["Earnings"])
        
        assert not events.empty, "Should have Earnings events"
        assert all(events["Type"] == "Earnings"), "All events should be Earnings"
    
    def test_empty_result_for_no_match(self):
        """Test that empty DataFrame is returned when no events match."""
        calendar = EarningsCalendar()
        calendar.load()
        
        # Date range with no events
        start = pd.Timestamp("1990-01-01")
        end = pd.Timestamp("1990-12-31")
        
        events = calendar.filter_by_date_range(start, end)
        
        assert events.empty, "Should return empty DataFrame"
        assert "Date" in events.columns, "Should have Date column even when empty"
    
    def test_get_event_dates(self):
        """Test getting DatetimeIndex of event dates."""
        calendar = EarningsCalendar()
        calendar.load()
        
        start = pd.Timestamp("2020-01-01")
        end = pd.Timestamp("2020-12-31")
        
        event_dates = calendar.get_event_dates(start, end, symbol="AAPL")
        
        assert isinstance(event_dates, pd.DatetimeIndex), "Should return DatetimeIndex"
        assert len(event_dates) > 0, "Should have event dates"
        assert all(event_dates >= start), "All dates should be after start"
        assert all(event_dates <= end), "All dates should be before end"


class TestIndexETFDetection:
    """Test index/ETF detection logic."""
    
    def test_common_index_etfs_detected(self):
        """Test that common index ETFs are detected."""
        assert is_index_or_etf("SPY"), "SPY should be detected as index/ETF"
        assert is_index_or_etf("QQQ"), "QQQ should be detected as index/ETF"
        assert is_index_or_etf("DIA"), "DIA should be detected as index/ETF"
        assert is_index_or_etf("IWM"), "IWM should be detected as index/ETF"
        assert is_index_or_etf("VTI"), "VTI should be detected as index/ETF"
    
    def test_individual_stocks_not_detected_as_index(self):
        """Test that individual stocks are not detected as index/ETF."""
        assert not is_index_or_etf("AAPL"), "AAPL should not be index/ETF"
        assert not is_index_or_etf("MSFT"), "MSFT should not be index/ETF"
        assert not is_index_or_etf("GOOGL"), "GOOGL should not be index/ETF"
    
    def test_case_insensitive(self):
        """Test that detection is case-insensitive."""
        assert is_index_or_etf("spy"), "spy (lowercase) should be detected"
        assert is_index_or_etf("Spy"), "Spy (mixed case) should be detected"


class TestExclusionWindow:
    """Test exclusion window creation and trade filtering."""
    
    def test_create_exclusion_window_single_date(self):
        """Test creating exclusion window for a single date."""
        calendar = EarningsCalendar()
        calendar.load()
        
        event_dates = pd.DatetimeIndex([pd.Timestamp("2020-01-15")])
        
        # No buffer
        excluded = calendar.create_exclusion_window(event_dates, days_before=0, days_after=0)
        assert len(excluded) == 1, "Should have 1 date"
        assert pd.Timestamp("2020-01-15") in excluded, "Should include event date"
        
        # With buffer
        excluded = calendar.create_exclusion_window(event_dates, days_before=1, days_after=1)
        assert len(excluded) == 3, "Should have 3 dates (±1 day)"
        assert pd.Timestamp("2020-01-14") in excluded, "Should include day before"
        assert pd.Timestamp("2020-01-15") in excluded, "Should include event date"
        assert pd.Timestamp("2020-01-16") in excluded, "Should include day after"
    
    def test_create_exclusion_window_multiple_dates(self):
        """Test creating exclusion window for multiple dates."""
        calendar = EarningsCalendar()
        calendar.load()
        
        event_dates = pd.DatetimeIndex([
            pd.Timestamp("2020-01-15"),
            pd.Timestamp("2020-01-20"),
        ])
        
        excluded = calendar.create_exclusion_window(event_dates, days_before=1, days_after=0)
        
        # Should have dates: 2020-01-14, 2020-01-15, 2020-01-19, 2020-01-20
        assert len(excluded) >= 4, "Should have at least 4 dates"
        assert pd.Timestamp("2020-01-14") in excluded
        assert pd.Timestamp("2020-01-15") in excluded
        assert pd.Timestamp("2020-01-19") in excluded
        assert pd.Timestamp("2020-01-20") in excluded
    
    def test_create_exclusion_window_empty_input(self):
        """Test creating exclusion window with empty input."""
        calendar = EarningsCalendar()
        calendar.load()
        
        event_dates = pd.DatetimeIndex([])
        excluded = calendar.create_exclusion_window(event_dates, days_before=1, days_after=1)
        
        assert len(excluded) == 0, "Should return empty DatetimeIndex"
    
    def test_filter_trades_by_exclusion(self):
        """Test filtering trades by exclusion window."""
        calendar = EarningsCalendar()
        calendar.load()
        
        # Create sample trades
        trades_data = {
            "Entry Date": [
                pd.Timestamp("2020-01-10"),
                pd.Timestamp("2020-01-15"),  # Should be excluded
                pd.Timestamp("2020-01-20"),
            ],
            "Exit Date": [
                pd.Timestamp("2020-01-12"),
                pd.Timestamp("2020-01-17"),
                pd.Timestamp("2020-01-22"),
            ],
            "PnL": [100, 200, -50],
            "Return %": [1.0, 2.0, -0.5],
        }
        trades_df = pd.DataFrame(trades_data)
        
        # Exclusion window: 2020-01-15 only
        excluded_dates = pd.DatetimeIndex([pd.Timestamp("2020-01-15")])
        
        filtered = calendar.filter_trades_by_exclusion(trades_df, excluded_dates)
        
        assert len(filtered) == 2, "Should have 2 trades after filtering"
        assert pd.Timestamp("2020-01-15") not in filtered["Entry Date"].values, "Excluded date should not be in filtered trades"
    
    def test_filter_trades_empty_exclusion(self):
        """Test filtering trades with empty exclusion window."""
        calendar = EarningsCalendar()
        calendar.load()
        
        trades_data = {
            "Entry Date": [pd.Timestamp("2020-01-10"), pd.Timestamp("2020-01-15")],
            "Exit Date": [pd.Timestamp("2020-01-12"), pd.Timestamp("2020-01-17")],
            "PnL": [100, 200],
            "Return %": [1.0, 2.0],
        }
        trades_df = pd.DataFrame(trades_data)
        
        excluded_dates = pd.DatetimeIndex([])
        filtered = calendar.filter_trades_by_exclusion(trades_df, excluded_dates)
        
        assert len(filtered) == len(trades_df), "Should keep all trades"


class TestResearchMetrics:
    """Test research metrics calculation."""
    
    def test_calculate_research_metrics_with_trades(self):
        """Test calculating metrics for filtered trades."""
        trades_data = {
            "Entry Date": [pd.Timestamp("2020-01-10"), pd.Timestamp("2020-01-15")],
            "Exit Date": [pd.Timestamp("2020-01-12"), pd.Timestamp("2020-01-17")],
            "PnL": [1000, 500],
            "Return %": [1.0, 0.5],
        }
        trades_df = pd.DataFrame(trades_data)
        
        initial_capital = 100000
        equity_curve = pd.DataFrame({"Equity": [100000, 101000, 101500]})
        
        metrics = calculate_research_metrics(trades_df, initial_capital, equity_curve)
        
        assert metrics["trade_count"] == 2, "Should have 2 trades"
        assert metrics["initial_capital"] == initial_capital
        assert metrics["final_equity"] == 101500, "Should calculate correct final equity"
        assert abs(metrics["total_return_pct"] - 1.5) < 0.0001, "Should calculate correct return"
        assert metrics["win_rate_pct"] == 100.0, "Both trades are profitable"
    
    def test_calculate_research_metrics_empty_trades(self):
        """Test calculating metrics with no trades."""
        trades_df = pd.DataFrame(columns=["Entry Date", "Exit Date", "PnL", "Return %"])
        
        initial_capital = 100000
        equity_curve = pd.DataFrame({"Equity": [100000]})
        
        metrics = calculate_research_metrics(trades_df, initial_capital, equity_curve)
        
        assert metrics["trade_count"] == 0, "Should have 0 trades"
        assert metrics["final_equity"] == initial_capital, "Should return initial capital"
        assert metrics["total_return_pct"] == 0.0, "Should have 0% return"
        assert metrics["win_rate_pct"] == 0.0, "Should have 0% win rate"


class TestDataSource:
    """Test data source tracking and loading strategies."""
    
    def test_data_source_tracking_sample_csv(self):
        """Test that data source is tracked when loading from sample CSV."""
        calendar = EarningsCalendar()
        success = calendar.load_sample()
        
        if success:
            assert calendar.get_data_source() == "sample_csv", "Should track sample_csv source"
    
    def test_data_source_tracking_none(self):
        """Test that data source is 'none' when no data loaded."""
        calendar = EarningsCalendar(sample_csv_path="/nonexistent/path.csv")
        calendar.load()
        
        assert calendar.get_data_source() == "none", "Should be 'none' when no data"
    
    def test_load_prefers_sample_csv_by_default(self):
        """Test that load() prefers sample CSV by default."""
        calendar = EarningsCalendar()
        success = calendar.load(symbol="AAPL", start_date=pd.Timestamp("2020-01-01"), end_date=pd.Timestamp("2020-12-31"))
        
        if success:
            # Should load from sample CSV (not yfinance) when prefer_yfinance=False (default)
            assert calendar.get_data_source() == "sample_csv"


class TestPhase0Compliance:
    """Test Phase 0 compliance: L1 earnings calendar does not affect L0 backtest."""
    
    @pytest.fixture
    def sample_data(self):
        """Create sample OHLCV data for testing."""
        dates = pd.date_range("2020-01-01", "2020-06-30", freq="B")
        np.random.seed(42)
        
        data = pd.DataFrame({
            "Open": 100 + np.cumsum(np.random.randn(len(dates))),
            "High": 102 + np.cumsum(np.random.randn(len(dates))),
            "Low": 98 + np.cumsum(np.random.randn(len(dates))),
            "Close": 100 + np.cumsum(np.random.randn(len(dates))),
            "Volume": np.random.randint(1000000, 10000000, len(dates)),
        }, index=dates)
        
        # Ensure OHLC relationships
        data["High"] = data[["Open", "High", "Close"]].max(axis=1)
        data["Low"] = data[["Open", "Low", "Close"]].min(axis=1)
        
        return data
    
    def test_l0_unchanged_when_calendar_not_used(self, sample_data):
        """Verify L0 results unchanged when earnings calendar not used."""
        strategy = SMACrossover(fast_period=20, slow_period=50)
        
        # Run backtest without calendar
        engine1 = BacktestEngine(
            initial_capital=100000,
            commission=0.001,
            slippage=0.0005,
        )
        equity1 = engine1.run(strategy, sample_data)
        metrics1 = PerformanceMetrics(
            equity_curve=equity1,
            trades=engine1.trades,
            initial_capital=100000,
        ).calculate_all()
        
        # Run backtest with calendar loaded but not used
        calendar = EarningsCalendar()
        calendar.load()  # Load calendar but don't apply filters
        
        engine2 = BacktestEngine(
            initial_capital=100000,
            commission=0.001,
            slippage=0.0005,
        )
        equity2 = engine2.run(strategy, sample_data)
        metrics2 = PerformanceMetrics(
            equity_curve=equity2,
            trades=engine2.trades,
            initial_capital=100000,
        ).calculate_all()
        
        # Verify all L0 metrics are identical
        assert metrics1["trade_count"] == metrics2["trade_count"], "Trade count should be identical"
        assert abs(metrics1["total_return_pct"] - metrics2["total_return_pct"]) < 0.0001, "Total return should be identical"
        assert abs(metrics1["final_equity"] - metrics2["final_equity"]) < 0.01, "Final equity should be identical"
    
    def test_research_filter_is_opt_in_only(self, sample_data):
        """Verify research filter does not apply unless explicitly used."""
        strategy = SMACrossover(fast_period=20, slow_period=50)
        
        engine = BacktestEngine(
            initial_capital=100000,
            commission=0.001,
            slippage=0.0005,
        )
        equity = engine.run(strategy, sample_data)
        trades_df = engine.get_trades_df()
        
        # Load calendar and create exclusion window
        calendar = EarningsCalendar()
        calendar.load()
        event_dates = calendar.get_event_dates(
            sample_data.index.min(),
            sample_data.index.max(),
        )
        
        if len(event_dates) > 0:
            excluded_dates = calendar.create_exclusion_window(
                event_dates,
                days_before=1,
                days_after=0,
            )
            
            # Verify that creating exclusion window does NOT modify original trades
            original_trade_count = len(trades_df)
            
            # Filter is only applied when explicitly called
            filtered_trades = calendar.filter_trades_by_exclusion(trades_df, excluded_dates)
            
            # Original trades_df should be unchanged
            assert len(trades_df) == original_trade_count, "Original trades should not be modified"
            
            # Filtered trades may be different (this is the research filter)
            # But it's a separate result, not modifying the main backtest
    
    def test_calendar_load_failure_does_not_crash(self, sample_data):
        """Verify backtest continues when calendar load fails."""
        strategy = SMACrossover(fast_period=20, slow_period=50)
        
        # Try to load calendar from nonexistent path
        calendar = EarningsCalendar(sample_csv_path="/nonexistent/path.csv")
        success = calendar.load()
        
        assert not success, "Calendar load should fail gracefully"
        assert not calendar.is_loaded(), "Calendar should not be loaded"
        
        # Backtest should still work
        engine = BacktestEngine(
            initial_capital=100000,
            commission=0.001,
            slippage=0.0005,
        )
        equity = engine.run(strategy, sample_data)
        
        assert not equity.empty, "Backtest should complete even with failed calendar load"
        assert len(engine.trades) > 0, "Trades should be generated"


class TestIndexGracefulDegradation:
    """Test graceful degradation for index/ETF symbols."""
    
    def test_index_symbol_returns_not_supported_status(self):
        """Test that index symbols return appropriate status."""
        calendar = EarningsCalendar()
        
        # Try to load for SPY (index ETF)
        success = calendar.load_yfinance(
            symbol="SPY",
            start_date=pd.Timestamp("2020-01-01"),
            end_date=pd.Timestamp("2020-12-31"),
        )
        
        # Should not succeed (or gracefully degrade)
        if not success:
            assert calendar.get_data_source() in ["none", "index_not_supported"], "Should indicate index not supported"
    
    def test_individual_stock_can_load(self):
        """Test that individual stocks can attempt to load."""
        calendar = EarningsCalendar()
        
        # AAPL is an individual stock - should at least try
        # (may still fail if yfinance unavailable, but shouldn't be rejected as index)
        # Just verify it doesn't immediately return "index_not_supported"
        calendar.load_yfinance(
            symbol="AAPL",
            start_date=pd.Timestamp("2020-01-01"),
            end_date=pd.Timestamp("2020-12-31"),
        )
        
        # If it didn't load, it should be "none", not "index_not_supported"
        if not calendar.is_loaded():
            assert calendar.get_data_source() != "index_not_supported", "Individual stock should not be rejected as index"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
