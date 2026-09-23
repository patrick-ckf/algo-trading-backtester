# Phase 0 Boundaries

## Purpose
This document defines the immutable core (Phase 0) of the backtesting system that must remain unchanged to ensure regression-free evolution.

## Core Invariants

### 1. Backtest Engine
- **Path**: `backtester/engine.py`
- **Contract**: Given identical OHLCV data and strategy parameters, the engine must produce:
  - Same trade entries and exits (dates, prices, shares)
  - Same final equity curve
  - Same commission and slippage calculations

### 2. Strategy Logic
- **Path**: `backtester/strategy.py`, `backtester/strategies/`
- **Contract**: Strategy signal generation (`on_bar()`) must be deterministic:
  - Same input → same signal (BUY/SELL/HOLD)
  - No random elements in signal logic
  - SMA and RSI calculations unchanged

### 3. Metrics Formulas
- **Path**: `backtester/metrics.py`
- **Contract**: Performance metrics calculations must be stable:
  - Total Return, CAGR, Max Drawdown, Sharpe Ratio formulas
  - Win Rate, average trade return
  - Buy-and-hold benchmark calculation

### 4. Data Loading
- **Path**: `backtester/data.py`
- **Contract**: OHLCV data structure and cleaning:
  - Column names: Date, Open, High, Low, Close, Volume
  - Date parsing and sorting behavior
  - NaN handling and cleaning rules

## Allowed Changes (Non-Breaking)

### UI/UX Improvements
- Streamlit dashboard enhancements (colors, layout, language)
- Input controls (e.g., Phase 1 symbol shortcuts)
- Chart styling and descriptions
- Default parameter values (as long as they don't change computation)

### Output Formatting
- Display precision, units, language
- Export formats (CSV, JSON)
- Report templates

### New Optional Features
- Additional data sources (as long as they produce same OHLCV format)
- New optional parameters (must not affect existing defaults)
- Educational notes, tooltips, help text

## Testing Requirements

### Phase 0 Regression Suite
- All existing tests in `tests/` must pass
- Key regression tests:
  - `test_engine.py`: Core engine behavior
  - `test_strategies.py`: Signal generation determinism
  - `test_metrics.py`: Performance calculation accuracy
  - `test_e2e.py`: End-to-end workflow stability

### New Feature Tests
- Must include test for Phase 0 compliance
- Must not weaken existing assertions
- Must demonstrate that same inputs produce same outputs

## Phase 1 Example (Symbol Shortcuts)

✅ **Allowed**: Quick-select UI for common symbols (SPY, QQQ, etc.)
- Only populates the symbol input field
- Does not change data fetching logic
- Does not alter backtest computation
- Manual input still works exactly as before

❌ **Not Allowed** (for Phase 1):
- Changing how Yahoo Finance data is fetched
- Modifying OHLCV data structure
- Adding new columns to data (e.g., news sentiment)
- Changing default strategy parameters

## Version History

- **Phase 0**: Initial stable core (engine, strategies, metrics, data loading)
- **Phase 1**: Symbol selection UX improvements (shortcuts, descriptions)
