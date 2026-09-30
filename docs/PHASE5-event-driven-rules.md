# Phase 5：事件驅動策略規則 / Event-Driven Strategy Rules

**Phase 5 (L2 layer)**: Opt-in event-aware strategy execution with control vs. event-aware comparison.

---

## 1. 概覽 / Overview

Phase 5 introduces **optional** event-driven rules that modify strategy behavior around known economic and earnings events. Unlike Phases 2-4 (L1 research overlays), Phase 5 operates at the **L2 layer** and **actively changes trading signals** when enabled.

### Key Principles

1. **Opt-in only**: Phase 5 is **disabled by default**. Users must explicitly enable it in the UI.
2. **L0 unchanged**: The control backtest (L0) remains unmodified and is always shown.
3. **Comparison-first**: Phase 5 runs **both** control and event-aware backtests side-by-side for transparent comparison.
4. **Blackout windows**: Event-aware rules block BUY signals during configurable windows around known events.

### Phase 0 Compliance

✅ **Control backtest (L0)** remains the default and is **always** shown first  
✅ Event-driven rules are **opt-in** and clearly labeled as L2 layer  
✅ Users see **side-by-side comparison** to evaluate the impact of event rules  
✅ No silent modifications to default strategy behavior

---

## 2. 事件驅動規則 / Event-Driven Rules

### 2.1 Blackout Windows

When Phase 5 is enabled, the system creates **blackout windows** around known events:

- **Economic events**: CPI, NFP, FOMC, GDP, etc. (from economic calendar)
- **Earnings events**: Quarterly earnings releases (from earnings calendar)

During blackout windows:
- **BUY signals are blocked** (converted to HOLD)
- **SELL signals pass through** (positions can be closed during blackout)
- **Existing positions are maintained** (no forced exit)

### 2.2 Configuration

Users can configure:

1. **Economic event blackout**:
   - Enable/disable economic events
   - Select event types (CPI, FOMC, NFP, etc.)
   - Days before event (0-5)
   - Days after event (0-5)

2. **Earnings event blackout**:
   - Enable/disable earnings events
   - Days before earnings (0-5)
   - Days after earnings (0-5)

### 2.3 Default Settings

When Phase 5 is first enabled, the default configuration is:
- Economic events: **Enabled**, all types, 1 day before, 0 days after
- Earnings events: **Enabled**, 1 day before, 0 days after

---

## 3. 技術實現 / Technical Implementation

### 3.1 Architecture

```
┌─────────────────────────────────────────┐
│  Phase 5: Event-Driven Rules (L2)       │
│  ┌───────────────┐  ┌────────────────┐  │
│  │   Control     │  │  Event-Aware   │  │
│  │   (L0)        │  │  (L2 Rules)    │  │
│  │   Unchanged   │  │  + Blackout    │  │
│  └───────────────┘  └────────────────┘  │
└─────────────────────────────────────────┘
          ▲                    ▲
          │                    │
    ┌─────┴──────┐      ┌─────┴────────┐
    │  Strategy  │      │  Strategy     │
    │  Instance  │      │  + Wrapper    │
    └────────────┘      └───────────────┘
```

### 3.2 Core Components

1. **`EventRuleConfig`**: Configuration dataclass for event-driven rules
2. **`EventDrivenEngine`**: Wrapper around `BacktestEngine` that applies blackout rules
3. **`EventAwareStrategyWrapper`**: Strategy wrapper that intercepts and blocks BUY signals during blackout
4. **`run_control_vs_event_aware()`**: High-level function that runs both control and event-aware backtests

### 3.3 Implementation Details

- **Blackout date calculation**: Uses existing `EconomicCalendar` and `EarningsCalendar` utilities
- **Date normalization**: All dates converted to timezone-naive midnight for consistent comparison
- **Strategy independence**: Each backtest uses a fresh strategy instance to avoid state pollution
- **Signal blocking**: Only BUY signals are blocked; SELL signals always pass through

---

## 4. 使用指南 / Usage Guide

### 4.1 Enabling Phase 5

1. Open the Streamlit dashboard
2. In the sidebar, scroll to **"🎯 Phase 5：事件驅動規則 / Event-Driven Rules"**
3. Check **"啟用 Phase 5 對比 / Enable Phase 5 Comparison"**
4. Configure economic and/or earnings blackout windows
5. Click **"運行回測 / Run Backtest"**

### 4.2 Interpreting Results

The Phase 5 comparison section shows:

**Control (L0 default):**
- Your strategy running normally
- No modifications to trading logic
- This is the baseline for comparison

**Event-Aware (L2 rules):**
- Same strategy with blackout rules applied
- BUY signals blocked during blackout windows
- Shows number of blocked signals

**Side-by-side metrics:**
- Trade count (with delta showing blocked trades)
- Total return (with delta vs. control)
- Sharpe ratio (with delta vs. control)
- Max drawdown (with delta vs. control)
- Win rate (with delta vs. control)

**Equity curve overlay:**
- Both curves plotted on the same chart
- Control: solid blue line
- Event-aware: dashed green line

### 4.3 Example Interpretation

```
Control:     100 trades, +15.2% return, Sharpe 0.85, 12.3% max DD
Event-Aware:  82 trades, +18.7% return, Sharpe 1.05, 10.1% max DD
Blocked:     23 signals blocked

Interpretation:
- Avoiding entries around known events reduced trade count by 18%
- But improved total return by +3.5%
- Sharpe ratio improved from 0.85 to 1.05 (better risk-adjusted returns)
- Max drawdown reduced by 2.2%
- This suggests the strategy may benefit from event-aware rules
```

---

## 5. 測試與驗證 / Testing & Verification

### 5.1 Unit Tests

Phase 5 includes comprehensive unit tests (`tests/test_event_rules.py`):

- Configuration validation
- Strategy wrapper behavior (blocking BUY, passing SELL)
- Blackout window creation
- Control vs. event-aware comparison
- State independence (fresh strategy instances)

Run tests:
```bash
pytest tests/test_event_rules.py -v
```

### 5.2 Integration Tests

The existing test suite remains green with Phase 5:
```bash
pytest tests/ -v --ignore=tests/test_stress.py
```

### 5.3 Manual Verification

To verify Phase 5 works correctly:

1. **Disable Phase 5**: Run backtest, note metrics
2. **Enable Phase 5**: Run same backtest with default settings
3. **Check control matches**: Control results should match step 1 exactly
4. **Check event-aware differs**: Event-aware results should show fewer trades
5. **Check blocked signals**: UI should show number of blocked signals > 0

---

## 6. 限制與注意事項 / Limitations & Considerations

### 6.1 Current Limitations

1. **Blackout only**: Phase 5 only blocks entries, does not force exits
2. **BUY signals only**: Only blocks BUY signals, SELL signals always pass through
3. **No position sizing adjustment**: Position sizes remain unchanged during blackout
4. **Single ticker earnings**: Earnings calendar works best for individual stocks (index/ETF support is limited)

### 6.2 Data Dependencies

Phase 5 requires:
- **Economic calendar CSV** (`data/economic_calendar.csv`) for economic events
- **Earnings data** (sample CSV or yfinance) for earnings events

If data is unavailable, Phase 5 gracefully degrades:
- Blackout windows may be empty (no events found)
- Control and event-aware results will be identical
- No errors or warnings (silent graceful degradation)

### 6.3 Performance Considerations

- **Runtime**: Phase 5 runs two backtests instead of one (~2x time)
- **Memory**: Two equity curves and trade lists stored in memory
- For large datasets (>10k bars), expect 2-10 second execution time

---

## 7. 未來擴展 / Future Enhancements

Potential Phase 5.x improvements:

1. **Phase 5.1**: Dynamic position sizing (reduce exposure during blackout instead of blocking)
2. **Phase 5.2**: Event type filtering (block only high-impact events)
3. **Phase 5.3**: Force-flat option (exit all positions before events)
4. **Phase 5.4**: Multi-strategy comparison (compare 3+ rule variants)
5. **Phase 5.5**: Backtesting on event-only windows (trade only around events)

---

## 8. 技術參考 / Technical Reference

### 8.1 API

**EventRuleConfig:**
```python
config = EventRuleConfig(
    enabled=True,
    use_economic_events=True,
    economic_event_types=["CPI", "FOMC"],
    economic_days_before=1,
    economic_days_after=0,
    use_earnings_events=True,
    earnings_days_before=1,
    earnings_days_after=0,
)
```

**Run comparison:**
```python
from backtester.event_rules import run_control_vs_event_aware

results = run_control_vs_event_aware(
    strategy=SMACrossover,  # Pass class, not instance
    data=data,
    initial_capital=100000,
    commission=0.001,
    slippage=0.0005,
    position_size=0.95,
    event_config=config,
    symbol="SPY",
)

control_equity = results["control"]["equity"]
event_aware_equity = results["event_aware"]["equity"]
blocked_signals = results["event_aware"]["blocked_signals"]
```

### 8.2 Files Added/Modified

**New files:**
- `backtester/event_rules.py` - Event-driven rule engine
- `tests/test_event_rules.py` - Unit tests for Phase 5
- `docs/PHASE5-event-driven-rules.md` - This documentation

**Modified files:**
- `streamlit_app.py` - Added Phase 5 UI panel and comparison display

**No changes to:**
- `backtester/engine.py` - L0 backtest engine unchanged
- `backtester/strategy.py` - Base strategy class unchanged
- Existing strategies (`sma_crossover.py`, `rsi_mean_reversion.py`)

---

## 9. Phase 0 合規檢查清單 / Phase 0 Compliance Checklist

- [x] Phase 5 is **disabled by default**
- [x] Control backtest (L0) **always runs** and is shown first
- [x] Event-driven rules are **opt-in** via explicit checkbox
- [x] User sees **clear warning** that Phase 5 modifies signals
- [x] Side-by-side comparison shows **both** control and event-aware results
- [x] Documentation states Phase 5 is **L2 layer**, not L0 default
- [x] Existing tests remain green (no L0 behavior changes)
- [x] Unit tests verify disabled rules produce identical results to control

---

## 10. 總結 / Summary

Phase 5 provides a **transparent, opt-in framework** for evaluating event-driven strategy rules. By running control and event-aware backtests side-by-side, users can objectively assess whether avoiding entries around known events improves their strategy's risk-adjusted returns.

Key takeaway: **Phase 5 does not change your default strategy**. It provides a research tool to explore "what if" scenarios with event-aware rules. Users must explicitly enable it and can always see the control (L0) results for comparison.

---

**Next steps:**
1. Review Phase 5 documentation
2. Test Phase 5 with your strategy on historical data
3. Compare control vs. event-aware metrics
4. Decide whether to integrate event rules into your strategy
5. Validate on out-of-sample data before production use

For questions or issues, see `README.md` or open a GitHub issue.
