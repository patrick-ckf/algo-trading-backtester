"""
Backtest report export: CSV (trades, equity curve) and one-page PDF summary.

Read-only over backtest results; does not modify engine math or paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple, Union

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PDF_MAGIC = b"%PDF"


@dataclass
class ReportMetadata:
    """Context shown on the PDF cover / header."""

    mode: str  # "single" | "portfolio"
    title_line: str
    ticker_or_tickers: str
    start_date: str
    end_date: str
    strategy_name: str
    strategy_params: Dict[str, Any]
    initial_capital: float
    commission: float
    slippage: Optional[float] = None
    generated_at: Optional[datetime] = None


def trades_to_csv_bytes(trades_df: pd.DataFrame) -> bytes:
    """Serialize trades table to UTF-8 CSV bytes."""
    if trades_df is None or trades_df.empty:
        return (
            "Entry Date,Exit Date,Entry Price,Exit Price,Shares,PnL,Return %\n"
        ).encode("utf-8")
    return trades_df.to_csv(index=False).encode("utf-8")


def equity_curve_to_csv_bytes(
    equity_curve: pd.DataFrame,
    equity_column: str = "Equity",
    benchmark_curve: Optional[pd.DataFrame] = None,
    benchmark_column: Optional[str] = None,
    benchmark_csv_name: str = "Benchmark",
) -> bytes:
    """
    Build equity curve CSV with Date, Equity, and optional benchmark column.

    Aligns benchmark to equity index via reindex (forward-fill).
    """
    if equity_curve is None or equity_curve.empty or equity_column not in equity_curve.columns:
        return "Date,Equity\n".encode("utf-8")

    out = pd.DataFrame(index=equity_curve.index)
    out["Date"] = pd.to_datetime(out.index).strftime("%Y-%m-%d")
    out["Equity"] = equity_curve[equity_column].values

    if (
        benchmark_curve is not None
        and not benchmark_curve.empty
        and benchmark_column
        and benchmark_column in benchmark_curve.columns
    ):
        aligned = benchmark_curve[benchmark_column].reindex(equity_curve.index).ffill()
        out[benchmark_csv_name] = aligned.values

    return out.to_csv(index=False).encode("utf-8")


def render_equity_chart_png(
    equity_curve: pd.DataFrame,
    equity_column: str = "Equity",
    benchmark_curve: Optional[pd.DataFrame] = None,
    benchmark_column: Optional[str] = None,
    equity_label: str = "Strategy Equity",
    benchmark_label: str = "Benchmark",
    title: str = "Equity Curve",
    figsize: Tuple[float, float] = (8.0, 3.2),
    dpi: int = 120,
) -> Tuple[Optional[bytes], Optional[str]]:
    """
    Render equity (+ optional benchmark) to PNG bytes via matplotlib.

    Returns (png_bytes, error_message). On failure png_bytes is None.
    """
    try:
        if equity_curve is None or equity_curve.empty or equity_column not in equity_curve.columns:
            return None, "Equity curve is empty"

        dates = pd.to_datetime(equity_curve.index)
        if getattr(dates, "tz", None) is not None:
            dates = dates.tz_localize(None)

        fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
        ax.plot(dates, equity_curve[equity_column].values, label=equity_label, color="#2E86DE", linewidth=1.8)

        if (
            benchmark_curve is not None
            and not benchmark_curve.empty
            and benchmark_column
            and benchmark_column in benchmark_curve.columns
        ):
            bench = benchmark_curve[benchmark_column].reindex(equity_curve.index).ffill()
            ax.plot(dates, bench.values, label=benchmark_label, color="#95A5A6", linewidth=1.5, linestyle="--")

        ax.set_title(title, fontsize=11)
        ax.set_xlabel("Date", fontsize=9)
        ax.set_ylabel("Equity ($)", fontsize=9)
        ax.legend(loc="best", fontsize=8)
        ax.grid(True, alpha=0.25)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        fig.autofmt_xdate()
        fig.tight_layout()

        buf = BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        return buf.getvalue(), None
    except Exception as exc:  # noqa: BLE001 — graceful degradation for UI
        plt.close("all")
        return None, str(exc)


def _register_cjk_font() -> Optional[str]:
    """Try to register a CJK-capable TTF/OTF for ReportLab; return font name or None."""
    import os

    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    candidates = [
        ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 0),
        ("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", 0),
        ("/usr/share/fonts/opentype/noto/NotoSansTC-Regular.otf", None),
        ("/usr/share/fonts/truetype/arphic/ukai.ttc", 0),
        ("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc", 0),
    ]
    for path, subfont in candidates:
        if not os.path.isfile(path):
            continue
        try:
            font_name = "ReportCJK"
            if subfont is not None:
                pdfmetrics.registerFont(TTFont(font_name, path, subfontIndex=subfont))
            else:
                pdfmetrics.registerFont(TTFont(font_name, path))
            return font_name
        except Exception:
            continue
    return None


def _pdf_labels(use_cjk: bool) -> Dict[str, str]:
    if use_cjk:
        return {
            "title": "回測報告 / Backtest Report",
            "meta": "摘要 / Summary",
            "kpis": "績效指標 / Performance KPIs",
            "metric": "指標 / Metric",
            "value": "數值 / Value",
            "params": "策略參數 / Strategy parameters",
            "chart": "權益曲線 / Equity curve",
            "no_chart": "（圖表無法生成）/ Chart unavailable",
        }
    return {
        "title": "Backtest Report",
        "meta": "Summary",
        "kpis": "Performance KPIs",
        "metric": "Metric",
        "value": "Value",
        "params": "Strategy parameters",
        "chart": "Equity curve",
        "no_chart": "Chart unavailable",
    }


def _format_params(params: Dict[str, Any]) -> str:
    if not params:
        return "—"
    return ", ".join(f"{k}={v}" for k, v in sorted(params.items()))


def kpi_rows_from_metrics(metrics: Dict[str, Union[float, int]]) -> List[Tuple[str, str]]:
    """Standard KPI rows for single-asset PerformanceMetrics.calculate_all()."""
    rows: List[Tuple[str, str]] = []

    def _f(key: str, fmt: str = ".2f", suffix: str = "") -> str:
        val = metrics.get(key)
        if val is None or (isinstance(val, float) and (pd.isna(val) or not np.isfinite(val))):
            return "N/A"
        if isinstance(val, (int, float)):
            return f"{val:{fmt}}{suffix}"
        return str(val)

    rows.append(("Total return", _f("total_return_pct", suffix="%")))
    rows.append(("CAGR", _f("cagr_pct", suffix="%")))
    rows.append(("Sharpe (252d)", _f("sharpe_ratio")))
    rows.append(("Max drawdown", _f("max_drawdown_pct", suffix="%")))
    rows.append(("Trade count", _f("trade_count", fmt="d")))
    rows.append(("Win rate", _f("win_rate_pct", suffix="%")))
    rows.append(("Avg trade return", _f("avg_trade_return_pct", suffix="%")))
    rows.append(("Initial capital", f"${metrics.get('initial_capital', 0):,.0f}"))
    final = metrics.get("final_equity")
    if final is not None and pd.notna(final):
        rows.append(("Final equity", f"${float(final):,.0f}"))
    if metrics.get("buy_hold_return_pct") is not None:
        rows.append(("Buy & hold return", _f("buy_hold_return_pct", suffix="%")))
    return rows


def portfolio_kpi_rows(
    portfolio_metrics: Any,
    spy_return_pct: Optional[float] = None,
) -> List[Tuple[str, str]]:
    """KPI rows from PortfolioMetrics dataclass."""
    rows = [
        ("Total return", f"{portfolio_metrics.total_return_pct:.2f}%"),
        ("CAGR", f"{portfolio_metrics.cagr_pct:.2f}%"),
        ("Sharpe (252d)", f"{portfolio_metrics.sharpe_ratio:.2f}"),
        ("Max drawdown", f"{portfolio_metrics.max_drawdown_pct:.2f}%"),
        ("Volatility", f"{portfolio_metrics.volatility_pct:.2f}%"),
        ("Initial capital", f"${portfolio_metrics.initial_capital:,.0f}"),
        ("Final equity", f"${portfolio_metrics.final_equity:,.0f}"),
    ]
    if spy_return_pct is not None:
        outperf = portfolio_metrics.total_return_pct - spy_return_pct
        rows.append(("SPY return", f"{spy_return_pct:.2f}%"))
        rows.append(("vs SPY", f"{outperf:+.2f}%"))
    return rows


def build_summary_pdf_bytes(
    metadata: ReportMetadata,
    kpi_rows: List[Tuple[str, str]],
    chart_png: Optional[bytes] = None,
) -> bytes:
    """
    Build a one-page PDF summary. Always returns valid PDF bytes (may omit chart).
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    cjk_font = _register_cjk_font()
    use_cjk = cjk_font is not None
    labels = _pdf_labels(use_cjk)
    base_font = cjk_font if use_cjk else "Helvetica"
    bold_font = cjk_font if use_cjk else "Helvetica-Bold"

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=0.65 * inch,
        rightMargin=0.65 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Heading1"],
        fontName=bold_font,
        fontSize=16,
        spaceAfter=10,
    )
    body_style = ParagraphStyle(
        "ReportBody",
        parent=styles["Normal"],
        fontName=base_font,
        fontSize=9,
        leading=12,
    )

    story: list = []
    story.append(Paragraph(labels["title"], title_style))
    story.append(Spacer(1, 6))

    generated = metadata.generated_at or datetime.now(timezone.utc)
    meta_lines = [
        f"<b>{metadata.title_line}</b>",
        f"Symbol(s): {metadata.ticker_or_tickers}",
        f"Period: {metadata.start_date} → {metadata.end_date}",
        f"Strategy: {metadata.strategy_name}",
        f"{labels['params']}: {_format_params(metadata.strategy_params)}",
        f"Capital: ${metadata.initial_capital:,.0f} | Commission: {metadata.commission:.4f}",
    ]
    if metadata.slippage is not None:
        meta_lines.append(f"Slippage: {metadata.slippage:.4f}")
    meta_lines.append(f"Generated: {generated.strftime('%Y-%m-%d %H:%M UTC')}")

    for line in meta_lines:
        story.append(Paragraph(line, body_style))
    story.append(Spacer(1, 10))

    story.append(Paragraph(f"<b>{labels['kpis']}</b>", body_style))
    table_data = [[labels["metric"], labels["value"]]] + [[a, b] for a, b in kpi_rows]
    tbl = Table(table_data, colWidths=[2.6 * inch, 3.4 * inch])
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2E86DE")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, -1), base_font),
                ("FONTNAME", (0, 0), (-1, 0), bold_font),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
            ]
        )
    )
    story.append(tbl)
    story.append(Spacer(1, 12))

    if chart_png:
        story.append(Paragraph(f"<b>{labels['chart']}</b>", body_style))
        story.append(Spacer(1, 4))
        img = Image(BytesIO(chart_png), width=6.8 * inch, height=2.7 * inch)
        story.append(img)
    else:
        story.append(Paragraph(labels["no_chart"], body_style))

    doc.build(story)
    data = buf.getvalue()
    if not data.startswith(PDF_MAGIC):
        raise ValueError("Generated PDF missing %PDF header")
    return data


def build_backtest_report_pdf(
    metadata: ReportMetadata,
    kpi_rows: List[Tuple[str, str]],
    equity_curve: pd.DataFrame,
    equity_column: str = "Equity",
    benchmark_curve: Optional[pd.DataFrame] = None,
    benchmark_column: Optional[str] = None,
    equity_label: str = "Strategy Equity",
    benchmark_label: str = "Benchmark",
) -> Tuple[bytes, Optional[str]]:
    """
    Build PDF with chart image when possible.

    Returns (pdf_bytes, chart_error). chart_error is set when PNG step failed.
    """
    chart_png, chart_err = render_equity_chart_png(
        equity_curve=equity_curve,
        equity_column=equity_column,
        benchmark_curve=benchmark_curve,
        benchmark_column=benchmark_column,
        equity_label=equity_label,
        benchmark_label=benchmark_label,
        title=metadata.title_line,
    )
    pdf_bytes = build_summary_pdf_bytes(metadata, kpi_rows, chart_png=chart_png)
    return pdf_bytes, chart_err


def safe_filename_part(text: str, max_len: int = 40) -> str:
    """Sanitize a string for use in download filenames."""
    cleaned = "".join(c if c.isalnum() or c in "-_" else "_" for c in text.strip())
    return cleaned[:max_len] or "report"
