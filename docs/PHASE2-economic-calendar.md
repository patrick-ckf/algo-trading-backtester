# Phase 2: Economic Calendar Implementation

## Overview

Phase 2 adds economic event markers (government data releases, FOMC decisions, etc.) as a **Layer 1 (L1) research/context layer**. This provides display-only event information that does not modify L0 backtest signals or metrics by default.

## Timezone Normalization Fix

### The Bug

**Original Issue:**
```
TypeError: Invalid comparison between dtype=datetime64[us] and str
File: backtester/economic_calendar.py, line ~99
mask = (self.calendar_df["Date"] >= start_date) & (self.calendar_df["Date"] <= end_date)
```

**Root Cause:**
- Economic calendar CSV files contain timezone-aware timestamps (e.g., `2018-01-03 00:00:00-05:00` US/Eastern)
- yfinance returns timezone-naive `datetime64[us]` DatetimeIndex for OHLCV data
- Pandas comparison between timezone-aware and timezone-naive datetimes raises `TypeError`
- Additional complication: DST transitions mix `-05:00` (standard) and `-04:00` (daylight) timezones

### The Fix

**Normalization Strategy:**
1. Parse all calendar dates with `pd.to_datetime(utc=True)` to handle mixed timezones
2. Convert to UTC-naive with `.dt.tz_localize(None)`
3. Normalize to midnight datetime for clean date comparison
4. All comparisons use timezone-naive datetimes on both sides

**Implementation Location:**
- `backtester/economic_calendar.py:_normalize_dates()`

**Benefits:**
- ✅ No TypeError when comparing with yfinance data.index
- ✅ Handles US/Eastern DST transitions correctly
- ✅ Preserves civil date intent (event on "2018-01-03" stays as 2018-01-03)
- ✅ Compatible with datetime64[us] and datetime64[ns] dtypes

## Module: `backtester.economic_calendar`

### Class: `EconomicCalendar`

Loads and filters economic events from CSV data.

#### Methods

**`__init__(csv_path: Optional[str], csv_data: Optional[str])`**
- Load calendar from file path or CSV string
- Automatically normalizes dates to timezone-naive

**`filter_by_date_range(start_date, end_date) -> pd.DataFrame`**
- Filter events within date range
- **FIXED:** Now handles timezone-naive OHLCV index dates without TypeError
- Accepts: datetime, date, pd.Timestamp (naive or aware)
- Returns: DataFrame with columns [Date, Event, Impact, Country]

**`filter_by_impact(impact: str) -> pd.DataFrame`**
- Filter events by impact level (e.g., "High", "Medium", "Low")

**`get_events_on_date(target_date: datetime) -> List[str]`**
- Get list of event names on a specific date
- Returns empty list if no events

**`is_event_day(target_date: datetime, impact_filter: Optional[str]) -> bool`**
- Check if a date has economic events
- Optional filter by impact level

**`get_exclusion_dates(start_date, end_date, impact: str) -> List[datetime]`**
- Get list of dates with events (for optional trade filtering)
- **L1 research filtering** - must be opt-in, does not affect L0 by default

### CSV Format

```csv
Date,Event,Impact,Country
2018-01-03,FOMC Minutes,High,US
2018-02-02,NFP Employment Report,High,US
2018-03-14,CPI Report,High,US
```

**Date formats accepted:**
- Timezone-naive: `2018-01-03` or `2018-01-03 00:00:00`
- Timezone-aware: `2018-01-03 00:00:00-05:00`
- Mixed timezones (DST): Handled automatically

**Impact levels:**
- `High` - Major market-moving events (FOMC, NFP)
- `Medium` - Moderate importance
- `Low` - Minor releases

## Test Coverage

### 17 New Tests

**Timezone Bug Reproduction:**
- `test_filter_with_naive_index_dates` - Main bug fix verification
- `test_comparison_with_datetime64_us` - Handles datetime64[us] dtype
- `test_streamlit_workflow_simulation` - Full workflow test
- `test_mixed_timezone_dst_transitions` - DST handling

**Date Type Compatibility:**
- `test_load_timezone_aware_csv` - Parse tz-aware CSV
- `test_load_naive_csv` - Parse tz-naive CSV
- `test_filter_with_python_datetime` - Standard datetime objects
- `test_filter_with_date_objects` - date objects (no time)

**Functionality:**
- `test_filter_by_impact` - Filter by impact level
- `test_get_events_on_date` - Event lookup by date
- `test_is_event_day` - Event day checking
- `test_get_exclusion_dates` - Exclusion date list
- `test_empty_calendar` - Empty calendar handling

**Phase 0 Compliance:**
- `test_phase0_boundary_compliance` - Verify L1 display only

### All Existing Tests Pass

```
78 existing tests pass (no regression)
1 skipped (Yahoo Finance cache)
```

Verified that L0 backtest engine, strategies, and metrics are unchanged.

## Phase 0 Boundary Compliance

Per [`docs/PHASE0-boundaries.md`](./PHASE0-boundaries.md):

| Requirement | Status |
|-------------|--------|
| Display only by default | ✅ Calendar provides data for visualization |
| No L0 signal modification | ✅ Does not change buy/sell signals |
| No metrics impact | ✅ CAGR, Sharpe, drawdown unchanged |
| Optional filtering only | ✅ `get_exclusion_dates()` requires opt-in |
| All L0 tests pass | ✅ 78 existing tests green |

### L0 vs L1 Separation

```
L2  Event Rules (future)      ← Phase 5; opt-in; requires control group
L1  Context Overlay (Phase 2) ← Economic calendar markers; display only
L0  Price Backtest (current)  ← SMA/RSI/engine/metrics (unchanged)
```

## Usage Example

See [`example_calendar_usage.py`](../example_calendar_usage.py):

```python
from backtester.economic_calendar import EconomicCalendar

# Load calendar (handles timezone-aware CSV automatically)
calendar = EconomicCalendar(csv_path="data/sample/economic_calendar_sample.csv")

# Get data date range from yfinance (timezone-naive)
data_start = data.index.min()  # tz-naive Timestamp
data_end = data.index.max()    # tz-naive Timestamp

# Filter calendar - NO TypeError after fix
events = calendar.filter_by_date_range(data_start, data_end)

# Use for display (future Streamlit integration)
for idx, row in events.iterrows():
    print(f"{row['Date'].date()}: {row['Event']}")
```

## Sample Data

**File:** `data/sample/economic_calendar_sample.csv`

Contains US economic events 2018-2020:
- FOMC rate decisions and minutes
- NFP (Non-Farm Payroll) employment reports
- CPI (Consumer Price Index) reports

45 high-impact events covering typical backtest date ranges.

## Future Work (Not in Phase 2)

### Streamlit UI Integration (Phase 2.1)

- [ ] Add event markers on equity curve chart
- [ ] Display event list in sidebar
- [ ] Optional "avoid event days" filter toggle (opt-in)
- [ ] Asia/Taipei timezone display option

### Data Sources (Phase 2.2)

- [ ] FRED API integration for official release dates
- [ ] Central bank calendar scraping
- [ ] Earnings calendar (Phase 4)

### Advanced Features (Phase 5)

- [ ] Event-driven strategy framework (L2)
- [ ] Pre/post-event analysis
- [ ] Control group comparison (event vs non-event periods)

## Related Documents

- [`docs/PHASE0-boundaries.md`](./PHASE0-boundaries.md) - Product boundaries and data principles
- [`README.md`](../README.md) - Project overview and roadmap

## PR

- [#6: fix: normalize economic calendar date tz for comparisons](https://github.com/patrick-ckf/algo-trading-backtester/pull/6)
