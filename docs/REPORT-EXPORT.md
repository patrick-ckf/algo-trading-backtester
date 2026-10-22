# Report export (Streamlit)

After a successful backtest, the dashboard shows **Report Export** download buttons:

1. **Trades CSV** — completed round-trips (single-asset mode; empty header row set in portfolio mode).
2. **Equity CSV** — `Date`, `Equity`, and benchmark column when available (`BuyHold` for single-asset, `SPY_Benchmark` for portfolio).
3. **Summary PDF** — one page with ticker(s), date range, strategy/parameters, KPI table, and an equity-curve chart image.

Implementation lives in `backtester/report_export.py`. Exports are read-only over existing results; L0 backtest math is unchanged.

## Dependencies

- `matplotlib` — chart PNG for the PDF (Agg backend; no display server).
- `reportlab` — PDF layout.

If chart rendering fails, the PDF is still produced (KPI table only) and Streamlit shows a warning. CSV downloads always work.

## CJK / bilingual PDF labels

When a CJK font is available on the host (e.g. Noto on many Linux images), PDF section titles use bilingual Chinese/English strings. Otherwise labels fall back to English only.

## Verification (Streamlit Cloud / mobile)

1. Run a single-asset backtest (default SPY + SMA template).
2. Open **Report Export** and download all three files; open the PDF on desktop and on a phone browser.
3. Switch to portfolio mode (2–5 tickers), run backtest, download equity CSV and PDF; confirm SPY benchmark column and KPI vs SPY.
4. Run `pytest tests/test_report_export.py -q` locally or in CI.
