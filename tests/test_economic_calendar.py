"""
Tests for Economic Calendar (Phase 2, L1)

Tests timezone normalization to prevent TypeError when comparing
timezone-aware calendar dates with timezone-naive OHLCV index dates.
"""

import pytest
import pandas as pd
from datetime import datetime, date
from backtester.economic_calendar import EconomicCalendar


@pytest.fixture
def sample_calendar_csv():
    """Sample CSV with US Eastern timezone-aware dates (simulating real-world data)."""
    return """Date,Event,Impact,Country
2018-01-03 00:00:00-05:00,FOMC Minutes,High,US
2018-02-02 00:00:00-05:00,NFP Employment Report,High,US
2018-03-14 00:00:00-04:00,CPI Report,High,US
2018-06-01 00:00:00-04:00,NFP Employment Report,High,US
2018-12-19 00:00:00-05:00,FOMC Rate Decision,High,US
2019-03-20 00:00:00-04:00,FOMC Rate Decision,High,US
"""


@pytest.fixture
def sample_calendar_naive():
    """Sample CSV with timezone-naive dates."""
    return """Date,Event,Impact,Country
2018-01-03,FOMC Minutes,High,US
2018-02-02,NFP Employment Report,High,US
2018-03-14,CPI Report,High,US
2018-06-01,NFP Employment Report,High,US
2018-12-19,FOMC Rate Decision,High,US
2019-03-20,FOMC Rate Decision,High,US
"""


@pytest.fixture
def yfinance_like_index():
    """
    Simulate yfinance data.index: timezone-naive datetime64[us] DatetimeIndex.
    
    This is what causes the bug - comparing tz-aware calendar dates
    with tz-naive OHLCV index dates.
    """
    dates = pd.date_range(start="2018-01-01", end="2019-12-31", freq="B")
    # Ensure it's timezone-naive datetime64[ns] (yfinance behavior)
    return dates.tz_localize(None)


class TestEconomicCalendarTimezoneHandling:
    """Test suite focused on timezone-aware vs timezone-naive comparison bug."""
    
    def test_load_timezone_aware_csv(self, sample_calendar_csv):
        """Test loading CSV with timezone-aware dates."""
        calendar = EconomicCalendar(csv_data=sample_calendar_csv)
        
        assert calendar.calendar_df is not None
        assert len(calendar.calendar_df) == 6
        
        # After normalization, dates should be timezone-naive
        assert calendar.calendar_df["Date"].dt.tz is None
        
        # Dates should be at midnight
        first_date = calendar.calendar_df.iloc[0]["Date"]
        assert first_date.hour == 0
        assert first_date.minute == 0
    
    def test_load_naive_csv(self, sample_calendar_naive):
        """Test loading CSV with timezone-naive dates."""
        calendar = EconomicCalendar(csv_data=sample_calendar_naive)
        
        assert calendar.calendar_df is not None
        assert len(calendar.calendar_df) == 6
        assert calendar.calendar_df["Date"].dt.tz is None
    
    def test_filter_with_naive_index_dates(self, sample_calendar_csv, yfinance_like_index):
        """
        MAIN BUG REPRODUCTION TEST
        
        This reproduces the TypeError from the bug report:
        "TypeError: Invalid comparison between dtype=datetime64[us] and str"
        
        When calendar has tz-aware dates and we filter using tz-naive
        data.index.min()/max() from yfinance.
        """
        calendar = EconomicCalendar(csv_data=sample_calendar_csv)
        
        # Simulate streamlit_app.py calling filter_by_date_range with
        # start_date/end_date from data.index.min()/max()
        start_date = yfinance_like_index.min()  # tz-naive Timestamp
        end_date = yfinance_like_index.max()    # tz-naive Timestamp
        
        # This should NOT raise TypeError after our fix
        filtered = calendar.filter_by_date_range(start_date, end_date)
        
        # Should return events within range
        assert len(filtered) > 0
        assert all(start_date.date() <= d.date() <= end_date.date() for d in filtered["Date"])
    
    def test_filter_with_python_datetime(self, sample_calendar_naive):
        """Test filtering with plain Python datetime objects."""
        calendar = EconomicCalendar(csv_data=sample_calendar_naive)
        
        start = datetime(2018, 1, 1)
        end = datetime(2018, 12, 31)
        
        filtered = calendar.filter_by_date_range(start, end)
        
        assert len(filtered) == 5  # Events in 2018
        assert all("2018" in str(d) for d in filtered["Date"])
    
    def test_filter_with_date_objects(self, sample_calendar_naive):
        """Test filtering with date objects (no time component)."""
        calendar = EconomicCalendar(csv_data=sample_calendar_naive)
        
        start = date(2018, 1, 1)
        end = date(2018, 12, 31)
        
        filtered = calendar.filter_by_date_range(start, end)
        
        assert len(filtered) == 5
    
    def test_filter_empty_result(self, sample_calendar_naive):
        """Test filtering with no matching events."""
        calendar = EconomicCalendar(csv_data=sample_calendar_naive)
        
        # Date range with no events
        start = datetime(2017, 1, 1)
        end = datetime(2017, 12, 31)
        
        filtered = calendar.filter_by_date_range(start, end)
        
        assert len(filtered) == 0
        assert list(filtered.columns) == ["Date", "Event", "Impact", "Country"]
    
    def test_filter_by_impact(self, sample_calendar_naive):
        """Test filtering by impact level."""
        calendar = EconomicCalendar(csv_data=sample_calendar_naive)
        
        high_impact = calendar.filter_by_impact("High")
        
        assert len(high_impact) == 6
        assert all(impact == "High" for impact in high_impact["Impact"])


class TestEconomicCalendarFunctionality:
    """Test economic calendar core functionality."""
    
    def test_load_from_file(self):
        """Test loading from file path."""
        calendar = EconomicCalendar(csv_path="data/sample/economic_calendar_sample.csv")
        
        assert calendar.calendar_df is not None
        assert len(calendar.calendar_df) > 0
        assert "Event" in calendar.calendar_df.columns
    
    def test_get_events_on_date(self, sample_calendar_naive, yfinance_like_index):
        """Test getting events on specific date."""
        calendar = EconomicCalendar(csv_data=sample_calendar_naive)
        
        # Date with event
        events = calendar.get_events_on_date(datetime(2018, 1, 3))
        assert len(events) == 1
        assert "FOMC" in events[0]
        
        # Date with no event
        events = calendar.get_events_on_date(datetime(2018, 1, 5))
        assert len(events) == 0
        
        # Test with yfinance-like timestamp
        target_date = pd.Timestamp("2018-02-02")
        events = calendar.get_events_on_date(target_date)
        assert len(events) == 1
        assert "NFP" in events[0]
    
    def test_is_event_day(self, sample_calendar_naive):
        """Test checking if date has events."""
        calendar = EconomicCalendar(csv_data=sample_calendar_naive)
        
        # Date with event
        assert calendar.is_event_day(datetime(2018, 1, 3))
        
        # Date without event
        assert not calendar.is_event_day(datetime(2018, 1, 5))
    
    def test_is_event_day_with_impact_filter(self, sample_calendar_naive):
        """Test event day check with impact filter."""
        calendar = EconomicCalendar(csv_data=sample_calendar_naive)
        
        # Has high impact event
        assert calendar.is_event_day(datetime(2018, 1, 3), impact_filter="High")
        
        # No medium impact event on this date
        assert not calendar.is_event_day(datetime(2018, 1, 3), impact_filter="Medium")
    
    def test_get_exclusion_dates(self, sample_calendar_naive):
        """Test getting exclusion dates for optional filtering."""
        calendar = EconomicCalendar(csv_data=sample_calendar_naive)
        
        start = datetime(2018, 1, 1)
        end = datetime(2018, 12, 31)
        
        exclusion_dates = calendar.get_exclusion_dates(start, end, impact="High")
        
        assert len(exclusion_dates) == 5  # 5 High impact events in 2018
        assert all(isinstance(d, pd.Timestamp) for d in exclusion_dates)
    
    def test_empty_calendar(self):
        """Test operations on empty calendar."""
        calendar = EconomicCalendar()
        
        assert calendar.calendar_df is None
        
        # Should return empty results, not crash
        filtered = calendar.filter_by_date_range(datetime(2018, 1, 1), datetime(2018, 12, 31))
        assert len(filtered) == 0
        
        events = calendar.get_events_on_date(datetime(2018, 1, 3))
        assert len(events) == 0
        
        assert not calendar.is_event_day(datetime(2018, 1, 3))


class TestRegressionCoverage:
    """Test edge cases and regression scenarios from production bug report."""
    
    def test_mixed_timezone_dst_transitions(self):
        """
        Test dates around DST transitions (US Eastern: -05:00 vs -04:00).
        
        This ensures we handle the civil date correctly regardless of DST.
        """
        csv_data = """Date,Event,Impact,Country
2018-03-11 00:00:00-04:00,After DST Start,High,US
2018-11-04 00:00:00-05:00,After DST End,High,US
"""
        calendar = EconomicCalendar(csv_data=csv_data)
        
        # Both should be normalized to correct civil dates
        dates = calendar.calendar_df["Date"].tolist()
        assert pd.Timestamp("2018-03-11").date() == dates[0].date()
        assert pd.Timestamp("2018-11-04").date() == dates[1].date()
    
    def test_comparison_with_datetime64_us(self, sample_calendar_csv):
        """
        Test comparison with datetime64[us] dtype (mentioned in bug report).
        
        yfinance can return datetime64[us] instead of datetime64[ns].
        """
        calendar = EconomicCalendar(csv_data=sample_calendar_csv)
        
        # Create datetime64[us] index like yfinance might return
        dates = pd.date_range(start="2018-01-01", end="2019-12-31", freq="B")
        us_dtype_index = dates.astype("datetime64[us]")
        
        start_date = us_dtype_index.min()
        end_date = us_dtype_index.max()
        
        # Should not raise TypeError
        filtered = calendar.filter_by_date_range(start_date, end_date)
        assert len(filtered) > 0
    
    def test_streamlit_workflow_simulation(self, yfinance_like_index):
        """
        Simulate the exact workflow from streamlit_app.py that was failing.
        
        1. Load calendar (possibly with tz-aware dates)
        2. Get OHLCV data with tz-naive index
        3. Filter calendar using data.index.min()/max()
        4. Should not raise TypeError
        """
        # Simulate loading calendar from CSV with tz-aware dates
        calendar_csv = """Date,Event,Impact,Country
2018-01-03 00:00:00-05:00,FOMC Minutes,High,US
2018-06-13 00:00:00-04:00,FOMC Rate Decision,High,US
2018-12-19 00:00:00-05:00,FOMC Rate Decision,High,US
"""
        calendar = EconomicCalendar(csv_data=calendar_csv)
        
        # Simulate yfinance data
        # In streamlit_app.py: data.index.min() and data.index.max()
        data_start = yfinance_like_index.min()  # tz-naive Timestamp
        data_end = yfinance_like_index.max()    # tz-naive Timestamp
        
        # This is the line that was failing in production
        # calendar.filter_by_date_range(data_start, data_end)
        # TypeError: Invalid comparison between dtype=datetime64[us] and str
        
        # After fix, should work without error
        filtered = calendar.filter_by_date_range(data_start, data_end)
        
        assert len(filtered) == 3
        assert all(isinstance(d, pd.Timestamp) for d in filtered["Date"])
        assert all(d.tz is None for d in filtered["Date"])  # All naive


def test_phase0_boundary_compliance():
    """
    Verify Phase 0 boundaries: calendar is L1 display only, does not affect L0.
    
    This test documents that economic calendar is research/context layer
    and does not modify backtest signals or metrics by default.
    """
    # Economic calendar provides data for:
    # 1. Display/visualization (markers on charts)
    # 2. Optional user-controlled filtering (opt-in)
    # 3. Research alignment
    
    # It does NOT:
    # 1. Modify strategy signals
    # 2. Change position sizing
    # 3. Affect L0 metrics (return, Sharpe, drawdown, etc.)
    
    calendar = EconomicCalendar(csv_path="data/sample/economic_calendar_sample.csv")
    
    # Calendar provides data only
    assert hasattr(calendar, "filter_by_date_range")
    assert hasattr(calendar, "get_events_on_date")
    assert hasattr(calendar, "get_exclusion_dates")  # Optional filtering
    
    # Calendar does NOT provide strategy modification methods
    assert not hasattr(calendar, "modify_signals")
    assert not hasattr(calendar, "adjust_positions")
    assert not hasattr(calendar, "override_strategy")
