# Walk-forward / out-of-sample validation (Phase 6b)

**Opt-in research layer** for rolling train/test folds on the same OHLCV series as the main single-asset backtest.

## Behavior

- **Disabled by default**: the standard L0 backtest path is unchanged when the walk-forward checkbox is off.
- **When enabled**: after a successful single-asset run, the app splits history into folds, evaluates **held-out test windows** with the existing L0 engine, and aggregates descriptive OOS metrics.
- **Fixed-params mode (default)**: each fold uses the current sidebar strategy parameters on the test window only (train window is unused except for fold alignment in rolling/anchored layouts).
- **In-sample optimize mode**: on each fold, runs the same parameter grid machinery as [PARAMETER-SCAN.md](PARAMETER-SCAN.md) on the **train** window, picks the best row by Sharpe / total return / max drawdown, then backtests those parameters on the **test** window. Reuses the parameter-scan grid when that section is enabled; otherwise a compact default grid is used.

Portfolio mode, Phase 5, research overlays, and the main equity chart are unaffected.

## Limits (Streamlit Cloud)

- **`MAX_WALK_FORWARD_FOLDS = 24`** — increase step size or shorten windows if validation refuses to run.
- **Per-fold grid** still capped at **`MAX_GRID_COMBINATIONS = 100`** when optimize mode is on.

## Window settings

| Control | Meaning |
|---------|---------|
| Train / Test / Step | Length in **months** (~21 trading days each) or **bar count** |
| Rolling | Fixed-length train window slides forward |
| Anchored | Train window grows from the start; test window rolls forward |
| Stitched OOS equity | Test-window equity segments chained with compounding capital (visual only) |

## Supported strategies

Same L0 strategy types as parameter scan: SMA, RSI, Donchian, MACD (Phase 6a), and Bollinger (Phase 6a). Optimize mode uses the parameter-scan grid when enabled, or compact defaults per strategy.

## Interpretation

This tool is for **robustness checks**, not statistical significance. OOS metrics can still overfit if the grid or strategy family is too flexible.

## Verification

1. Run default SPY single-asset backtest with walk-forward **off** — behavior unchanged.
2. Enable **步進樣本外 / Walk-Forward**, keep **fixed params**, run — per-fold table and OOS charts appear below main results.
3. Switch to **optimize** mode with parameter scan enabled — confirm fold table shows varying parameters.
4. Toggle light/dark theme — Plotly titles and backgrounds stay readable.
