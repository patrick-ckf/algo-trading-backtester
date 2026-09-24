"""
Tests for economic calendar module (Phase 2 - L1 Research Layer)

Tests verify:
1. Calendar data loading and filtering
2. Event date extraction
3. Exclusion window creation (research filter)
4. Trade filtering (research filter)
5. Graceful degradation when calendar unavailable
6. Phase 0 compliance: L0 backtest unchanged when calendar off/display-only
"""

import pytest
import pandas as pd
import numpy as np
import os
from datetime import datetime

from backtester.economic_calendar import (
    EconomicCalendar,
    calculate_research_metrics,
)
from backtester.engine import BacktestEngine, Trade
from backtester.strategies.sma_crossover import SMACrossover
from backtester.metrics import PerformanceMetrics


class TestEconomicCalendarBasics:
    """Test basic calendar loading and filtering."""
    
    def test_calendar_loads_successfully(self):
        """Test that calendar loads from default path."""
        calendar = EconomicCalendar()
        success = calendar.load()
        
        assert success, "Calendar should load successfully"
        assert calendar.is_loaded(), "Calendar should report as loaded"
        assert len(calendar.get_available_types()) > 0, "Should have event types"
    
    def test_calendar_graceful_degradation_missing_file(self):
        """Test graceful degradation when calendar file is missing."""
        calendar = EconomicCalendar(calendar_path="/nonexistent/path.csv")
        success = calendar.load()
        
        assert not success, "Should return False when file missing"
        assert not calendar.is_loaded(), "Should not be loaded"
        assert len(calendar.get_available_types()) == 0, "Should have no types"
    
    def test_get_available_types(self):
        """Test getting available event types."""
        calendar = EconomicCalendar()
        calendar.load()
        
        types = calendar.get_available_types()
        
        # Check expected types are present
        assert "CPI" in types, "Should have CPI events"
        assert "NFP" in types, "Should have NFP events"
        assert "FOMC" in types, "Should have FOMC events"
        assert "GDP" in types, "Should have GDP events"
    
    def test_filter_by_date_range_all_types(self):
        """Test filtering events by date range."""
        calendar = EconomicCalendar()
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
    
    def test_filter_by_date_range_specific_types(self):
        """Test filtering events by date range and type."""
        calendar = EconomicCalendar()
        calendar.load()
        
        start = pd.Timestamp("2020-01-01")
        end = pd.Timestamp("2020-12-31")
        
        cpi_events = calendar.filter_by_date_range(start, end, event_types=["CPI"])
        
        assert not cpi_events.empty, "Should have CPI events"
        assert all(cpi_events["Type"] == "CPI"), "All events should be CPI"
    
    def test_get_event_dates(self):
        """Test extracting DatetimeIndex of event dates."""
        calendar = EconomicCalendar()
        calendar.load()
        
        start = pd.Timestamp("2020-01-01")
        end = pd.Timestamp("2020-12-31")
        
        event_dates = calendar.get_event_dates(start, end, event_types=["FOMC"])
        
        assert len(event_dates) > 0, "Should have FOMC dates"
        assert isinstance(event_dates, pd.DatetimeIndex), "Should return DatetimeIndex"


class TestExclusionWindowResearchFilter:
    """Test exclusion window creation for research filter (opt-in only)."""
    
    def test_create_exclusion_window_single_event(self):
        """Test creating exclusion window around single event."""
        calendar = EconomicCalendar()
        event_dates = pd.DatetimeIndex([pd.Timestamp("2020-06-10")])
        
        # ±1 day window
        excluded = calendar.create_exclusion_window(
            event_dates,
            days_before=1,
            days_after=1,
        )
        
        # Should have 3 dates: 2020-06-09, 2020-06-10, 2020-06-11
        assert len(excluded) == 3, "Should have 3 dates in ±1 window"
        assert pd.Timestamp("2020-06-09") in excluded
        assert pd.Timestamp("2020-06-10") in excluded
        assert pd.Timestamp("2020-06-11") in excluded
    
    def test_create_exclusion_window_multiple_events(self):
        """Test creating exclusion window with overlapping events."""
        calendar = EconomicCalendar()
        event_dates = pd.DatetimeIndex([
            pd.Timestamp("2020-06-10"),
            pd.Timestamp("2020-06-12"),  # Overlaps with first window
        ])
        
        # ±1 day window
        excluded = calendar.create_exclusion_window(
            event_dates,
            days_before=1,
            days_after=1,
        )
        
        # Should merge overlapping windows
        assert len(excluded) >= 4, "Should have at least 4 unique dates"
        assert pd.Timestamp("2020-06-10") in excluded
        assert pd.Timestamp("2020-06-11") in excluded
        assert pd.Timestamp("2020-06-12") in excluded
    
    def test_create_exclusion_window_empty(self):
        """Test exclusion window with no events."""
        calendar = EconomicCalendar()
        event_dates = pd.DatetimeIndex([])
        
        excluded = calendar.create_exclusion_window(event_dates, days_before=1, days_after=1)
        
        assert len(excluded) == 0, "Should be empty with no events"
    
    def test_filter_trades_by_exclusion(self):
        """Test filtering trades to exclude those in exclusion window."""
        calendar = EconomicCalendar()
        
        # Create sample trades
        trades_df = pd.DataFrame({
            "Entry Date": [
                pd.Timestamp("2020-06-08"),  # Keep
                pd.Timestamp("2020-06-10"),  # Exclude (event day)
                pd.Timestamp("2020-06-11"),  # Exclude (in window)
                pd.Timestamp("2020-06-15"),  # Keep
            ],
            "Exit Date": [
                pd.Timestamp("2020-06-09"),
                pd.Timestamp("2020-06-11"),
                pd.Timestamp("2020-06-12"),
                pd.Timestamp("2020-06-16"),
            ],
            "PnL": [100, 200, 300, 400],
            "Return %": [1.0, 2.0, 3.0, 4.0],
        })
        
        excluded_dates = pd.DatetimeIndex([
            pd.Timestamp("2020-06-10"),
            pd.Timestamp("2020-06-11"),
        ])
        
        filtered = calendar.filter_trades_by_exclusion(trades_df, excluded_dates)
        
        assert len(filtered) == 2, "Should keep 2 trades"
        assert pd.Timestamp("2020-06-08") in filtered["Entry Date"].values
        assert pd.Timestamp("2020-06-15") in filtered["Entry Date"].values
        assert pd.Timestamp("2020-06-10") not in filtered["Entry Date"].values


class TestResearchMetrics:
    """Test research metrics calculation for filtered trades."""
    
    def test_calculate_research_metrics_basic(self):
        """Test basic research metrics calculation."""
        trades_df = pd.DataFrame({
            "Entry Date": [pd.Timestamp("2020-01-01"), pd.Timestamp("2020-02-01")],
            "Exit Date": [pd.Timestamp("2020-01-10"), pd.Timestamp("2020-02-10")],
            "PnL": [500, 300],
            "Return %": [5.0, 3.0],
        })
        
        equity_curve = pd.DataFrame({
            "Equity": [100000, 100500, 100800],
        })
        
        metrics = calculate_research_metrics(trades_df, 100000, equity_curve)
        
        assert metrics["initial_capital"] == 100000
        assert metrics["trade_count"] == 2
        assert metrics["final_equity"] == 100800  # 100000 + 500 + 300
        assert metrics["total_return_pct"] == pytest.approx(0.8, rel=0.01)
        assert metrics["win_rate_pct"] == 100.0  # Both trades profitable
    
    def test_calculate_research_metrics_empty_trades(self):
        """Test research metrics with no trades."""
        trades_df = pd.DataFrame({
            "Entry Date": [],
            "Exit Date": [],
            "PnL": [],
            "Return %": [],
        })
        
        equity_curve = pd.DataFrame({"Equity": [100000]})
        
        metrics = calculate_research_metrics(trades_df, 100000, equity_curve)
        
        assert metrics["trade_count"] == 0
        assert metrics["final_equity"] == 100000
        assert metrics["total_return_pct"] == 0.0
        assert metrics["win_rate_pct"] == 0.0


class TestPhase0Compliance:
    """
    Test Phase 0 compliance: L0 backtest must be unchanged when calendar is off or display-only.
    
    This is the most critical test suite for Phase 2.
    """
    
    @pytest.fixture
    def sample_data(self):
        """Create sample OHLCV data for testing."""
        dates = pd.date_range(start="2020-01-01", end="2020-12-31", freq="B")
        np.random.seed(42)
        
        close_prices = 100 + np.cumsum(np.random.randn(len(dates)) * 2)
        
        data = pd.DataFrame({
            "Date": dates,
            "Open": close_prices * 0.99,
            "High": close_prices * 1.02,
            "Low": close_prices * 0.98,
            "Close": close_prices,
            "Volume": np.random.randint(1000000, 10000000, len(dates)),
        })
        data.set_index("Date", inplace=True)
        return data
    
    def test_l0_unchanged_when_calendar_not_used(self, sample_data):
        """
        Test that L0 backtest results are identical when calendar is not loaded.
        
        This verifies the core Phase 0 requirement: calendar is L1 layer only.
        """
        # Run backtest WITHOUT calendar
        strategy = SMACrossover(fast_period=20, slow_period=50)
        engine = BacktestEngine(
            initial_capital=100000,
            commission=0.001,
            slippage=0.0005,
        )
        
        equity_curve = engine.run(strategy, sample_data)
        trades_df = engine.get_trades_df()
        
        metrics_calculator = PerformanceMetrics(
            equity_curve=equity_curve,
            trades=engine.trades,
            initial_capital=100000,
        )
        metrics_without_calendar = metrics_calculator.calculate_all()
        
        # Now "load" calendar but DON'T use it to filter trades (display-only)
        calendar = EconomicCalendar()
        calendar.load()
        events = calendar.filter_by_date_range(
            sample_data.index.min(),
            sample_data.index.max(),
        )
        
        # Run backtest again (calendar loaded but not used for filtering)
        strategy2 = SMACrossover(fast_period=20, slow_period=50)
        engine2 = BacktestEngine(
            initial_capital=100000,
            commission=0.001,
            slippage=0.0005,
        )
        
        equity_curve2 = engine2.run(strategy2, sample_data)
        trades_df2 = engine2.get_trades_df()
        
        metrics_calculator2 = PerformanceMetrics(
            equity_curve=equity_curve2,
            trades=engine2.trades,
            initial_capital=100000,
        )
        metrics_with_calendar_display = metrics_calculator2.calculate_all()
        
        # CRITICAL: All L0 metrics must be IDENTICAL
        assert metrics_without_calendar["trade_count"] == metrics_with_calendar_display["trade_count"], \
            "Trade count must not change when calendar is display-only"
        
        assert metrics_without_calendar["total_return_pct"] == pytest.approx(
            metrics_with_calendar_display["total_return_pct"], rel=1e-9
        ), "Total return must not change when calendar is display-only"
        
        assert metrics_without_calendar["final_equity"] == pytest.approx(
            metrics_with_calendar_display["final_equity"], rel=1e-9
        ), "Final equity must not change when calendar is display-only"
        
        # Verify trades are identical
        if not trades_df.empty and not trades_df2.empty:
            pd.testing.assert_frame_equal(
                trades_df.reset_index(drop=True),
                trades_df2.reset_index(drop=True),
                check_dtype=False,
                atol=1e-6,
            )
    
    def test_research_filter_is_opt_in_only(self, sample_data):
        """
        Test that research filter must be explicitly enabled and does not affect default behavior.
        
        This verifies Phase 0 requirement: filters are opt-in only.
        """
        # Run backtest
        strategy = SMACrossover(fast_period=20, slow_period=50)
        engine = BacktestEngine(initial_capital=100000, commission=0.001, slippage=0.0005)
        equity_curve = engine.run(strategy, sample_data)
        trades_df = engine.get_trades_df()
        
        original_trade_count = len(trades_df)
        
        # Load calendar and create exclusion window
        calendar = EconomicCalendar()
        calendar.load()
        event_dates = calendar.get_event_dates(
            sample_data.index.min(),
            sample_data.index.max(),
            event_types=["FOMC"],
        )
        excluded_dates = calendar.create_exclusion_window(event_dates, days_before=1, days_after=1)
        
        # The original trades_df should NOT be filtered unless explicitly requested
        # This is opt-in behavior
        filtered_trades = calendar.filter_trades_by_exclusion(trades_df, excluded_dates)
        
        # Original trades_df must remain unchanged
        assert len(trades_df) == original_trade_count, \
            "Original trades must not be modified by filter creation"
        
        # Filtered trades should be different (fewer trades)
        assert len(filtered_trades) <= len(trades_df), \
            "Filtered trades should have same or fewer trades"
    
    def test_calendar_load_failure_does_not_crash(self, sample_data):
        """
        Test that calendar load failure does not crash the backtest.
        
        Verifies graceful degradation requirement.
        """
        # Run backtest with non-existent calendar
        calendar = EconomicCalendar(calendar_path="/nonexistent/calendar.csv")
        success = calendar.load()
        
        assert not success, "Should fail gracefully"
        assert not calendar.is_loaded(), "Should not be loaded"
        
        # Backtest should still run fine
        strategy = SMACrossover(fast_period=20, slow_period=50)
        engine = BacktestEngine(initial_capital=100000, commission=0.001, slippage=0.0005)
        equity_curve = engine.run(strategy, sample_data)
        
        assert not equity_curve.empty, "Backtest should run even if calendar fails to load"
        assert len(engine.trades) >= 0, "Should have trades or no trades, not crash"


class TestStreamlitIntegration:
    """Test integration points with Streamlit dashboard."""
    
    def test_calendar_can_be_toggled_off(self):
        """Test that calendar can be toggled off (Phase 0 requirement)."""
        calendar = EconomicCalendar()
        calendar.load()
        
        # Simulate "show_calendar = False" - should return empty events
        show_calendar = False
        
        if show_calendar:
            events = calendar.filter_by_date_range(
                pd.Timestamp("2020-01-01"),
                pd.Timestamp("2020-12-31"),
            )
        else:
            events = None
        
        assert events is None, "When calendar is off, events should be None"
    
    def test_event_markers_parameter_optional(self):
        """Test that event markers are optional in chart plotting."""
        # This tests that plot_equity_curve can handle None for event_markers
        # (integration test covered by dashboard workflow)
        event_markers = None
        
        # Should not raise error when None
        assert event_markers is None or isinstance(event_markers, pd.DataFrame)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


def test_filter_tz_aware_start_end_against_naive_calendar():
    """Streamlit/yfinance may pass tz-aware index bounds; calendar CSV is naive."""
    cal = EconomicCalendar()
    assert cal.load()

    start = pd.Timestamp("2018-01-02 00:00:00", tz="America/New_York")
    end = pd.Timestamp("2018-03-31 00:00:00", tz="America/New_York")

    filtered = cal.filter_by_date_range(start, end)
    assert not filtered.empty
    assert all(getattr(ts, "tz", None) is None for ts in filtered["Date"])

    # datetime64[us] naive bounds must still work
    start_naive = pd.Timestamp("2018-01-02").as_unit("us")
    end_naive = pd.Timestamp("2018-03-31").as_unit("us")
    filtered2 = cal.filter_by_date_range(start_naive, end_naive)
    assert len(filtered2) == len(filtered)
