"""Unit tests for backtest report export (CSV + PDF)."""

import pandas as pd
import pytest

from backtester.data import DataLoader
from backtester.engine import BacktestEngine
from backtester.metrics import PerformanceMetrics, calculate_buy_and_hold
from backtester.report_export import (
    PDF_MAGIC,
    ReportMetadata,
    build_backtest_report_pdf,
    build_summary_pdf_bytes,
    equity_curve_to_csv_bytes,
    kpi_rows_from_metrics,
    render_equity_chart_png,
    trades_to_csv_bytes,
)
from backtester.strategies.sma_crossover import SMACrossover


@pytest.fixture
def sample_backtest():
    loader = DataLoader()
    data = loader.load_csv("data/sample/SPY_sample.csv")
    engine = BacktestEngine(initial_capital=10000.0, commission=0.001, slippage=0.0005)
    equity = engine.run(SMACrossover(fast_period=10, slow_period=20), data)
    buy_hold = calculate_buy_and_hold(data, 10000.0, commission=0.001)
    metrics = PerformanceMetrics(
        equity_curve=equity,
        trades=engine.trades,
        initial_capital=10000.0,
        buy_hold_curve=buy_hold,
    ).calculate_all()
    return engine, equity, buy_hold, metrics, data


def test_trades_csv_nonempty_header(sample_backtest):
    engine, *_ = sample_backtest
    raw = trades_to_csv_bytes(engine.get_trades_df())
    text = raw.decode("utf-8")
    assert "Entry Date" in text.splitlines()[0]
    assert len(raw) > 0


def test_equity_csv_includes_benchmark(sample_backtest):
    _, equity, buy_hold, _, _ = sample_backtest
    raw = equity_curve_to_csv_bytes(
        equity,
        benchmark_curve=buy_hold,
        benchmark_column="BuyHoldEquity",
        benchmark_csv_name="BuyHold",
    )
    text = raw.decode("utf-8")
    header = text.splitlines()[0]
    assert "Date" in header
    assert "Equity" in header
    assert "BuyHold" in header
    assert len(text.splitlines()) > 2


def test_equity_chart_png_bytes(sample_backtest):
    _, equity, buy_hold, _, _ = sample_backtest
    png, err = render_equity_chart_png(
        equity,
        benchmark_curve=buy_hold,
        benchmark_column="BuyHoldEquity",
    )
    assert err is None
    assert png is not None
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_pdf_has_valid_header(sample_backtest):
    _, equity, buy_hold, metrics, data = sample_backtest
    meta = ReportMetadata(
        mode="single",
        title_line="Test backtest",
        ticker_or_tickers="SPY",
        start_date=str(data.index.min().date()),
        end_date=str(data.index.max().date()),
        strategy_name="SMA Crossover",
        strategy_params={"fast_period": 10, "slow_period": 20},
        initial_capital=10000.0,
        commission=0.001,
        slippage=0.0005,
    )
    pdf_bytes, chart_err = build_backtest_report_pdf(
        metadata=meta,
        kpi_rows=kpi_rows_from_metrics(metrics),
        equity_curve=equity,
        benchmark_curve=buy_hold,
        benchmark_column="BuyHoldEquity",
    )
    assert chart_err is None
    assert pdf_bytes.startswith(PDF_MAGIC)
    assert len(pdf_bytes) > 500


def test_pdf_without_chart_still_valid(sample_backtest):
    _, equity, _, metrics, data = sample_backtest
    meta = ReportMetadata(
        mode="single",
        title_line="Test backtest",
        ticker_or_tickers="SPY",
        start_date=str(data.index.min().date()),
        end_date=str(data.index.max().date()),
        strategy_name="SMA",
        strategy_params={},
        initial_capital=10000.0,
        commission=0.0,
    )
    pdf_bytes = build_summary_pdf_bytes(meta, kpi_rows_from_metrics(metrics), chart_png=None)
    assert pdf_bytes.startswith(PDF_MAGIC)


def test_empty_trades_csv_header():
    raw = trades_to_csv_bytes(pd.DataFrame())
    assert b"Entry Date" in raw
