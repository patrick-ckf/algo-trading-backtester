# Parameter scan / grid optimization

**Opt-in research layer** for sweeping strategy parameters on the same OHLCV series as the main single-asset backtest.

## Behavior

- **Disabled by default**: the standard L0 backtest path is unchanged when the scan checkbox is off.
- **When enabled**: after a successful single-asset run, the app runs additional independent backtests over a user-defined grid, ranks by Sharpe, total return, or max drawdown, and shows a heatmap (2D) or bar chart (1D).
- **Apply to sidebar**: pick a row to copy parameters into the sidebar (switches template to **Custom / 自訂**) and re-run the main backtest.

Portfolio mode, Phase 5, research overlays, and strategy templates are unaffected.

## Grid size limit (Streamlit Cloud)

To avoid timeouts and memory pressure, each scan is capped at **`MAX_GRID_COMBINATIONS = 100`** (see `backtester/parameter_scan.py`). If the grid is too large, narrow the range or increase the step before running.

## Supported sweeps

| Strategy | Swept parameters | Notes |
|----------|------------------|--------|
| SMA Crossover | `fast_period` × `slow_period` | Only combinations with fast &lt; slow |
| RSI Mean Reversion | `rsi_period` × `rsi_oversold` | `rsi_overbought` fixed from sidebar value |
| Donchian Breakout | `channel_period` | 1D bar chart |

## Verification (Streamlit Cloud / mobile)

1. Open the deployed app; confirm **Single Asset** mode and default SPY backtest still works with scan **off**.
2. Enable **參數掃描 / Parameter Scan**, use default SMA ranges, run backtest — heatmap and ranked table appear below main results.
3. Select a row and **Apply to sidebar**; confirm sidebar numbers update and a second run reflects new params.
4. Toggle **light/dark** theme; heatmap text and backgrounds remain readable.
5. On a narrow viewport, sidebar scrolls and scan section remains usable.
