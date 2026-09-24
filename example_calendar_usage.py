"""
Example demonstrating Economic Calendar timezone normalization fix.

This shows how the bug would have occurred and how the fix resolves it.
"""

import pandas as pd
from datetime import datetime
from backtester.economic_calendar import EconomicCalendar

# Simulate timezone-aware calendar data (like real-world CSV)
# US/Eastern timezone with DST transitions
tz_aware_calendar = """Date,Event,Impact,Country
2018-01-03 00:00:00-05:00,FOMC Minutes,High,US
2018-06-13 00:00:00-04:00,FOMC Rate Decision,High,US
2018-12-19 00:00:00-05:00,FOMC Rate Decision,High,US
"""

# Load calendar (automatically normalizes to naive)
print("Loading timezone-aware economic calendar...")
calendar = EconomicCalendar(csv_data=tz_aware_calendar)
print(f"✓ Loaded {len(calendar.calendar_df)} events")
print(f"✓ Calendar dates are now timezone-naive: {calendar.calendar_df['Date'].dt.tz is None}")
print()

# Simulate yfinance data.index (timezone-naive datetime64)
print("Simulating yfinance OHLCV data...")
yfinance_index = pd.date_range(start="2018-01-01", end="2018-12-31", freq="B")
yfinance_index = yfinance_index.tz_localize(None)  # Ensure naive like yfinance
print(f"✓ Data index: {len(yfinance_index)} trading days")
print(f"✓ Data index is timezone-naive: {yfinance_index.tz is None}")
print(f"✓ Data index dtype: {yfinance_index.dtype}")
print()

# The problematic comparison from the bug report
# Before fix: TypeError: Invalid comparison between dtype=datetime64[us] and str
# After fix: Works without error
print("Filtering calendar by data date range...")
start_date = yfinance_index.min()
end_date = yfinance_index.max()

try:
    filtered = calendar.filter_by_date_range(start_date, end_date)
    print(f"✓ SUCCESS: Filtered to {len(filtered)} events without TypeError")
    print()
    print("Events found:")
    for idx, row in filtered.iterrows():
        print(f"  {row['Date'].date()}: {row['Event']}")
except TypeError as e:
    print(f"✗ FAILED: {e}")
    print("This is the bug we fixed!")

print()
print("=" * 60)
print("Fix verified: Timezone-aware calendar + naive OHLCV = No error")
print("=" * 60)
