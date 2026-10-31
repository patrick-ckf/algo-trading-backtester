# Phase 6e — Monte Carlo / bootstrap uncertainty

**Opt-in post-hoc research layer** for single-asset backtests. Resamples **observed** daily equity returns or per-trade returns from an already-completed L0 run to explore how summary metrics might vary under resampling. This is **descriptive uncertainty tooling**, not a formal statistical test, significance claim, or proof of strategy edge.

## Behavior

- **Disabled by default**: the standard L0 backtest path is unchanged when the Monte Carlo checkbox is off.
- **When enabled**: after a successful single-asset run, the app runs bootstrap simulations on returns from that run (no change to signals or fills).
- **User controls**: number of simulations (default 500, max 2000), random seed, confidence level (two-sided interval, e.g. 90% → 5th–95th percentiles), resampling source (daily equity returns vs. trade returns), optional block size for block bootstrap.
- **Outputs**: percentile table (actual backtest vs. bootstrap interval), histograms for total return / max drawdown / Sharpe, and an equity fan chart (calendar dates for daily bootstrap; trade index for trade bootstrap).

Portfolio mode, Phase 5, parameter scan, and L1 overlays are unaffected.

## L0 / L1 compliance

- **L0**: Backtest math remains OHLCV-only; bootstrap never re-runs the strategy or modifies trades.
- **L1**: Charts and tables are display-only research aids.

## Interpretation (important)

Bootstrap intervals describe **how much the reported metrics could move if you re-drew the same kind of return sample from this single historical path**. They do **not**:

- Predict future performance
- Replace out-of-sample or walk-forward validation
- Establish statistical significance or “proof” of alpha

Always compare against buy-and-hold and treat results as educational.

## Verification (Streamlit)

1. Run default SPY single-asset backtest with Monte Carlo **off** — behavior unchanged vs. prior releases.
2. Enable **Phase 6e / Monte Carlo**, keep defaults, re-run — percentile table and charts appear below main results.
3. Change seed and confirm bands shift; restore seed and confirm reproducibility.
4. Toggle light/dark theme — Plotly backgrounds and text remain readable.
5. Trade-return bootstrap with zero trades shows an error hint; daily bootstrap still works.

## Module

Logic lives in `backtester/monte_carlo.py` (`run_bootstrap`, plotting helpers). Unit tests: `tests/test_monte_carlo.py` (fixed seeds).
