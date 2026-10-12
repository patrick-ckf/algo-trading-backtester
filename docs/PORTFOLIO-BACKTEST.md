# Multi-Asset Portfolio Backtest

## Overview

The portfolio backtest feature allows users to test a multi-asset portfolio strategy with equal weighting and monthly rebalancing. This is an **opt-in feature** that coexists with the existing single-asset backtest functionality.

## Features

### Portfolio Configuration
- Select 2-5 tickers from Yahoo Finance
- Equal-weight allocation (each asset gets 1/N of capital)
- Monthly rebalancing on the first trading day of each month
- Automatic timezone handling for different trading calendars

### Performance Metrics
- **Total Return**: Overall portfolio return percentage
- **CAGR**: Compound Annual Growth Rate
- **Sharpe Ratio**: Risk-adjusted return metric
- **Max Drawdown**: Largest peak-to-trough decline
- **Volatility**: Annualized standard deviation of returns

### Benchmark Comparison
- SPY (S&P 500 ETF) buy-and-hold benchmark
- Side-by-side comparison of portfolio vs benchmark returns

### Portfolio Analytics
- **Per-Asset Contributions**: Percentage of final equity from each asset
- **Correlation Matrix**: Correlation between asset returns
  - Shows diversification benefits
  - Color-coded heatmap for easy visualization

### Visualizations
1. **Equity Curve**: Portfolio vs SPY benchmark over time
2. **Asset Allocation**: Stacked area chart showing allocation changes

## Usage

### Via Streamlit Dashboard

1. Launch the dashboard:
   ```bash
   streamlit run streamlit_app.py
   ```

2. In the sidebar:
   - Select "Multi-Asset Portfolio" mode
   - Choose 2-5 tickers (default: SPY, QQQ)
   - Set start and end dates
   - Configure initial capital and commission rate
   - Click "Run Backtest"

3. Review results:
   - Portfolio KPIs at the top
   - Asset contributions and correlation matrix
   - Interactive Plotly charts

### Programmatic Usage

```python
from backtester.portfolio import PortfolioBacktester, calculate_benchmark

# Create portfolio
portfolio = PortfolioBacktester(
    tickers=["SPY", "QQQ", "IWM"],
    start_date="2020-01-01",
    end_date="2023-12-31",
    initial_capital=100000.0,
    commission=0.001,
)

# Load data and run backtest
portfolio.load_data()
equity_curve = portfolio.run()

# Calculate metrics
metrics = portfolio.calculate_metrics()
print(f"Portfolio Return: {metrics.total_return_pct:.2f}%")
print(f"Sharpe Ratio: {metrics.sharpe_ratio:.2f}")
print(f"Max Drawdown: {metrics.max_drawdown_pct:.2f}%")

# Access per-asset data
for ticker, contribution in metrics.asset_contributions.items():
    print(f"{ticker}: {contribution:.1f}%")

# View correlation matrix
print(metrics.correlation_matrix)

# Calculate benchmark
benchmark = calculate_benchmark(
    ticker="SPY",
    start_date="2020-01-01",
    end_date="2023-12-31",
    initial_capital=100000.0,
    aligned_dates=equity_curve.index,
)
```

## Implementation Details

### Data Alignment
- Handles tickers with different trading calendars (e.g., US vs international)
- Uses forward-fill for missing data points (standard practice)
- Normalizes all timestamps to timezone-naive for consistent comparison
- Aligns to common date range where all assets have data

### Rebalancing Logic
- Identifies first trading day of each month
- Calculates target value per asset (total equity / N)
- Rebalances all assets simultaneously
- Applies commission costs to each rebalance trade

### Timezone Handling
- Yahoo Finance returns tz-aware timestamps (US/Eastern)
- Automatically converts to tz-naive dates to avoid alignment bugs
- Prevents "Mixed timezones" pandas errors
- Works correctly with cached CSV files

### Performance Considerations
- Efficient pandas operations for large date ranges
- Vectorized calculations where possible
- Minimal network calls (uses DataLoader caching)

## Constraints and Limitations

### Current Limitations
1. **Equal weighting only**: No custom weight allocation
2. **Monthly rebalancing only**: No custom rebalance frequency
3. **Yahoo Finance only**: No CSV upload or custom data sources
4. **No short positions**: Long-only portfolio
5. **No leverage**: 100% capital allocation across assets
6. **No strategy signals**: Buy-and-hold only (no tactical allocation)

### Design Decisions
- **Single-asset features disabled**: Economic calendar, news, earnings, and Phase 5 event-driven rules are single-asset features and are hidden in portfolio mode
- **Fixed benchmark**: Always compares against SPY (S&P 500)
- **Commission applied per asset**: Each rebalance trade incurs commission cost

## Testing

The portfolio module includes comprehensive unit tests:

```bash
# Run portfolio tests
pytest tests/test_portfolio.py -v

# Tests cover:
# - Equal weighting validation
# - Monthly rebalance date calculation
# - Benchmark alignment
# - Metrics calculation
# - Different trading calendars
# - Correlation matrix properties
```

All tests pass and validate:
- 2-5 ticker constraints
- Equal weight enforcement (±1% tolerance for commission/rounding)
- Monthly rebalance dates are first trading day of month
- Benchmark aligns to portfolio dates
- Correlation matrix is symmetric with 1.0 on diagonal
- All metrics are calculated correctly

## Future Enhancements

Potential improvements for future versions:

1. **Custom weights**: Allow user-specified allocation percentages
2. **Rebalance frequency**: Daily, weekly, quarterly options
3. **Rebalance threshold**: Only rebalance if drift exceeds X%
4. **Transaction cost analysis**: Show impact of different commission rates
5. **Risk parity**: Allocate based on risk contribution, not equal weights
6. **CSV support**: Upload custom portfolio data
7. **More benchmarks**: Allow selecting different benchmark tickers
8. **Portfolio optimization**: Suggest optimal weights based on Sharpe/Sortino
9. **Drawdown periods**: Highlight and analyze major drawdown events
10. **Rolling metrics**: Show how Sharpe ratio changes over time

## Architecture Notes

### Module Structure
- `backtester/portfolio.py`: Core portfolio backtest logic
- `tests/test_portfolio.py`: Comprehensive test suite
- Integration with existing `DataLoader` for data fetching
- Separate from single-asset `BacktestEngine` (no breaking changes)

### Code Principles
- **Separation of concerns**: Portfolio logic is self-contained
- **No breaking changes**: Existing single-asset backtest unchanged
- **Opt-in**: User explicitly selects portfolio mode
- **Defensive coding**: Validates inputs, handles edge cases
- **Clear naming**: Variables and functions are self-documenting

## Example Use Cases

### Diversified Index Portfolio
```python
# "Three-fund portfolio" (US stocks, international, bonds)
portfolio = PortfolioBacktester(
    tickers=["VTI", "VXUS", "BND"],  # Vanguard ETFs
    start_date="2015-01-01",
    end_date="2024-12-31",
    initial_capital=100000.0,
)
```

### Sector Rotation
```python
# Equal weight across S&P 500 sectors
portfolio = PortfolioBacktester(
    tickers=["XLK", "XLF", "XLV", "XLE", "XLI"],  # Tech, Finance, Health, Energy, Industrial
    start_date="2020-01-01",
    end_date="2023-12-31",
)
```

### Factor Investing
```python
# Smart beta factors
portfolio = PortfolioBacktester(
    tickers=["MTUM", "QUAL", "SIZE", "VLUE"],  # Momentum, Quality, Size, Value
    start_date="2018-01-01",
    end_date="2024-12-31",
)
```

## References

- [Modern Portfolio Theory](https://en.wikipedia.org/wiki/Modern_portfolio_theory)
- [Rebalancing Strategies](https://www.investopedia.com/terms/r/rebalancing.asp)
- [Correlation in Finance](https://www.investopedia.com/terms/c/correlation.asp)
- [Sharpe Ratio](https://www.investopedia.com/terms/s/sharperatio.asp)
