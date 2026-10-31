# Phase 6c — Cost / friction sensitivity scan

**Opt-in research layer** for single-asset backtests. Sweeps commission and/or slippage while holding strategy parameters and OHLCV data fixed.

## Behavior

- **Disabled by default**: the main L0 backtest uses sidebar commission and slippage only.
- **When enabled**: after a successful single-asset run, the app re-runs the same strategy under each cost assumption via `BacktestEngine` (same math as the CLI and main dashboard).
- **Not optimization**: results show how sensitive metrics are to friction assumptions — not a recommendation to minimize costs or maximize a metric.

Portfolio mode, Phase 5 event rules, and L1 overlays are unchanged and do not drive the sweep.

## Grid limit

Each scan is capped at **`MAX_COST_COMBINATIONS = 100`** (same limit as parameter scan). Narrow ranges or increase step size if the preview warns.

## Sweep modes

| Mode | Grid | Chart |
|------|------|--------|
| Commission × Slippage | 2D product | Heatmap |
| Commission only | 1D (slippage = sidebar value) | Line |
| Slippage only | 1D (commission = sidebar value) | Line |

Rates are entered as **percent per trade** in the UI (e.g. `0.10` = 0.10%), matching the sidebar commission/slippage fields.

## Metrics shown

- Total return (%)
- Sharpe ratio
- Max drawdown (%)

## Verification (Streamlit)

1. Single-asset SPY backtest with cost scan **off** — unchanged behavior.
2. Enable **成本敏感度 / Cost Sensitivity**, default grids, run — table and heatmap (or line) appear below main results.
3. Toggle light/dark theme — charts remain readable.
4. Confirm caption states sensitivity tooling, not optimization advice.
