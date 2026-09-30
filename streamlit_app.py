"""
Streamlit Dashboard for Backtesting System
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from typing import Optional
import io

from backtester.data import DataLoader
from backtester.engine import BacktestEngine
from backtester.metrics import PerformanceMetrics, calculate_buy_and_hold
from backtester.strategies.sma_crossover import SMACrossover
from backtester.strategies.rsi_mean_reversion import RSIMeanReversion
from backtester.economic_calendar import EconomicCalendar, calculate_research_metrics, _to_naive_day
from backtester.news import NewsPanel
from backtester.earnings_calendar import EarningsCalendar
from backtester.event_rules import EventRuleConfig, run_control_vs_event_aware
from backtester.ticker_presets import (
    get_grouped_ticker_options,
    is_separator,
    get_ticker_description,
)


st.set_page_config(
    page_title="演算法交易回測系統",
    page_icon="📈",
    layout="wide",
)


def plot_equity_curve(
    equity_df: pd.DataFrame,
    buy_hold_df: Optional[pd.DataFrame] = None,
    event_markers: Optional[pd.DataFrame] = None,
    earnings_markers: Optional[pd.DataFrame] = None,
    theme: str = "dark",
) -> go.Figure:
    """Create equity curve chart with theme-adaptive styling."""
    # Theme-specific colors
    if theme == "light":
        paper_bg = "#FFFFFF"
        plot_bg = "#F8F9FA"
        font_color = "#1F2937"
        grid_color = "rgba(128,128,128,0.2)"
    else:
        paper_bg = "rgba(0,0,0,0)"
        plot_bg = "rgba(0,0,0,0)"
        font_color = "#FAFAFA"
        grid_color = "rgba(128,128,128,0.15)"
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=equity_df.index,
        y=equity_df["Equity"],
        mode="lines",
        name="策略權益 / Strategy Equity",
        line=dict(color="#2E86DE", width=2),
    ))
    
    if buy_hold_df is not None and not buy_hold_df.empty:
        fig.add_trace(go.Scatter(
            x=buy_hold_df.index,
            y=buy_hold_df["BuyHoldEquity"],
            mode="lines",
            name="買入持有 / Buy & Hold",
            line=dict(color="#95A5A6", width=2, dash="dash"),
        ))
    
    # Normalize equity index to naive days for marker alignment (handles tz-aware yfinance data)
    equity_index_naive = pd.DatetimeIndex([_to_naive_day(d) for d in equity_df.index])
    
    # Add economic event markers (L1 display layer - does not affect L0 backtest)
    if event_markers is not None and not event_markers.empty:
        # Group by event type for color coding
        event_colors = {
            "CPI": "#E74C3C",
            "NFP": "#F39C12",
            "FOMC": "#9B59B6",
            "Unemployment": "#3498DB",
            "GDP": "#1ABC9C",
        }
        
        for event_type in event_markers["Type"].unique():
            type_events = event_markers[event_markers["Type"] == event_type]
            
            # Get y-values at event dates for scatter plot
            y_values = []
            x_values = []
            for event_date in type_events["Date"]:
                # Normalize event date for comparison
                event_date_naive = _to_naive_day(event_date)
                
                # Find closest equity value using normalized dates
                if event_date_naive in equity_index_naive:
                    idx_pos = equity_index_naive.get_loc(event_date_naive)
                    y_values.append(equity_df.iloc[idx_pos]["Equity"])
                    x_values.append(equity_df.index[idx_pos])
                else:
                    # Find nearest date using normalized index
                    nearest_idx = equity_index_naive.get_indexer([event_date_naive], method="nearest")[0]
                    if 0 <= nearest_idx < len(equity_df):
                        y_values.append(equity_df.iloc[nearest_idx]["Equity"])
                        x_values.append(equity_df.index[nearest_idx])
            
            if x_values and y_values:
                fig.add_trace(go.Scatter(
                    x=x_values,
                    y=y_values,
                    mode="markers",
                    name=f"{event_type}",
                    marker=dict(
                        size=8,
                        color=event_colors.get(event_type, "#34495E"),
                        symbol="diamond",
                        line=dict(width=1, color="white"),
                    ),
                    hovertemplate="<b>%{x}</b><br>" + f"{event_type}<br>" + "權益 / Equity: $%{y:,.0f}<extra></extra>",
                ))
    
    # Add earnings event markers (L1 display layer - Phase 4)
    if earnings_markers is not None and not earnings_markers.empty:
        # Group by symbol for color coding
        import hashlib
        
        for symbol in earnings_markers["Symbol"].unique():
            symbol_events = earnings_markers[earnings_markers["Symbol"] == symbol]
            
            # Generate consistent color for symbol
            color_hash = int(hashlib.md5(symbol.encode()).hexdigest()[:6], 16)
            color = f"#{color_hash:06x}"
            
            # Get y-values at event dates for scatter plot
            y_values = []
            x_values = []
            hover_texts = []
            for _, row in symbol_events.iterrows():
                event_date = row["Date"]
                # Normalize event date for comparison
                event_date_naive = _to_naive_day(event_date)
                
                # Find closest equity value using normalized dates
                if event_date_naive in equity_index_naive:
                    idx_pos = equity_index_naive.get_loc(event_date_naive)
                    equity_val = equity_df.iloc[idx_pos]["Equity"]
                    y_values.append(equity_val)
                    x_values.append(equity_df.index[idx_pos])
                    hover_texts.append(f"<b>{event_date_naive.strftime('%Y-%m-%d')}</b><br>{row['Event']}<br>權益: ${equity_val:,.0f}")
                else:
                    # Find nearest date using normalized index
                    nearest_idx = equity_index_naive.get_indexer([event_date_naive], method="nearest")[0]
                    if 0 <= nearest_idx < len(equity_df):
                        equity_val = equity_df.iloc[nearest_idx]["Equity"]
                        y_values.append(equity_val)
                        x_values.append(equity_df.index[nearest_idx])
                        hover_texts.append(f"<b>{event_date_naive.strftime('%Y-%m-%d')}</b><br>{row['Event']}<br>權益: ${equity_val:,.0f}")
            
            if x_values and y_values:
                fig.add_trace(go.Scatter(
                    x=x_values,
                    y=y_values,
                    mode="markers",
                    name=f"📊 {symbol} Earnings",
                    marker=dict(
                        size=10,
                        color=color,
                        symbol="square",
                        line=dict(width=1, color="white"),
                    ),
                    hovertemplate="%{text}<extra></extra>",
                    text=hover_texts,
                ))
    
    fig.update_layout(
        title=dict(text="權益曲線 / Equity Curve", font=dict(color=font_color)),
        xaxis_title="日期 / Date",
        yaxis_title="權益 / Equity ($)",
        hovermode="x unified",
        template="plotly",
        plot_bgcolor=plot_bg,
        paper_bgcolor=paper_bg,
        font=dict(
            family="sans-serif",
            size=12,
            color=font_color,
        ),
        xaxis=dict(
            showgrid=True,
            gridwidth=1,
            gridcolor=grid_color,
            zeroline=False,
            color=font_color,
        ),
        yaxis=dict(
            showgrid=True,
            gridwidth=1,
            gridcolor=grid_color,
            zeroline=False,
            color=font_color,
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(color=font_color),
        ),
    )
    return fig


def plot_drawdown(equity_df: pd.DataFrame, theme: str = "dark") -> go.Figure:
    """Create drawdown chart with theme-adaptive styling."""
    # Theme-specific colors
    if theme == "light":
        paper_bg = "#FFFFFF"
        plot_bg = "#F8F9FA"
        font_color = "#1F2937"
        grid_color = "rgba(128,128,128,0.2)"
    else:
        paper_bg = "rgba(0,0,0,0)"
        plot_bg = "rgba(0,0,0,0)"
        font_color = "#FAFAFA"
        grid_color = "rgba(128,128,128,0.15)"
    
    equity = equity_df["Equity"]
    running_max = equity.expanding().max()
    drawdown = (equity - running_max) / running_max * 100
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=equity_df.index,
        y=drawdown,
        mode="lines",
        name="回撤",
        fill="tozeroy",
        line=dict(color="#EA2027", width=2),
    ))
    fig.update_layout(
        title=dict(text="回撤圖 / Drawdown", font=dict(color=font_color)),
        xaxis_title="日期 / Date",
        yaxis_title="回撤 / Drawdown (%)",
        hovermode="x unified",
        template="plotly",
        plot_bgcolor=plot_bg,
        paper_bgcolor=paper_bg,
        font=dict(
            family="sans-serif",
            size=12,
            color=font_color,
        ),
        xaxis=dict(
            showgrid=True,
            gridwidth=1,
            gridcolor=grid_color,
            zeroline=False,
            color=font_color,
        ),
        yaxis=dict(
            showgrid=True,
            gridwidth=1,
            gridcolor=grid_color,
            zeroline=False,
            color=font_color,
        ),
    )
    return fig


def main():
    # Initialize theme in session state (default to dark)
    if "theme" not in st.session_state:
        st.session_state.theme = "dark"
    
    st.title("📈 演算法交易回測系統")
    st.markdown("**Algorithmic Trading Backtesting System**")
    st.markdown("---")
    
    # Inject theme-specific CSS (CSS-only approach, no JavaScript)
    if st.session_state.theme == "light":
        st.markdown("""
        <style>
            /* === LIGHT THEME: Clean Modern Fintech Aesthetic === */
            /* Using high specificity to override config.toml dark theme */
            
            /* Main background: soft gray */
            [data-testid="stAppViewContainer"],
            [data-testid="stAppViewContainer"] > div:first-child,
            .main .block-container {
                background-color: #F8F9FA !important;
            }
            
            /* Sidebar: white with subtle border */
            [data-testid="stSidebar"],
            [data-testid="stSidebar"] > div:first-child {
                background-color: #FFFFFF !important;
                border-right: 1px solid #E5E7EB !important;
            }
            
            /* Text: high contrast dark text on light background */
            [data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
            [data-testid="stSidebar"] label,
            [data-testid="stSidebar"] p,
            .stMarkdown,
            .stMarkdown p,
            body,
            .main {
                color: #1F2937 !important;
            }
            
            /* Headers: darker for emphasis */
            h1, h2, h3, h4, h5, h6 {
                color: #111827 !important;
            }
            
            /* Metric cards: dark text on light background */
            [data-testid="stMetricValue"] {
                color: #111827 !important;
                font-size: 1.5rem;
                font-weight: 600;
            }
            
            [data-testid="stMetricLabel"] {
                color: #6B7280 !important;
                font-size: 0.875rem;
            }
            
            /* Metric delta colors */
            [data-testid="stMetricDelta"] svg {
                fill: #10B981 !important;
            }
            
            [data-testid="stMetricDelta"][data-testid*="decrease"] svg {
                fill: #EF4444 !important;
            }
            
            /* Expanders: white with border */
            [data-testid="stExpander"] {
                background-color: #FFFFFF !important;
                border: 1px solid #E5E7EB !important;
                border-radius: 0.5rem;
            }
            
            [data-testid="stExpander"] details summary {
                color: #1F2937 !important;
            }
            
            /* DataFrames: clean white */
            .stDataFrame,
            [data-testid="stDataFrame"],
            .dataframe {
                background-color: #FFFFFF !important;
                border: 1px solid #E5E7EB !important;
                color: #1F2937 !important;
            }
            
            .dataframe th,
            .dataframe td {
                color: #1F2937 !important;
                background-color: #FFFFFF !important;
            }
            
            .dataframe thead th {
                background-color: #F3F4F6 !important;
            }
            
            /* Buttons: refined fintech style */
            .stButton > button {
                border: 1px solid #D1D5DB !important;
                background-color: #FFFFFF !important;
                color: #374151 !important;
            }
            
            .stButton > button[kind="primary"] {
                background-color: #2E86DE !important;
                color: #FFFFFF !important;
                border: none !important;
                font-weight: 600;
            }
            
            .stButton > button:hover {
                border-color: #9CA3AF !important;
                background-color: #F9FAFB !important;
            }
            
            .stButton > button[kind="primary"]:hover {
                background-color: #1565C0 !important;
            }
            
            /* Input fields: clean borders */
            .stTextInput > div > div > input,
            .stNumberInput > div > div > input,
            .stSelectbox > div > div > div,
            .stSelectbox [data-baseweb="select"],
            input[type="text"],
            input[type="number"] {
                border-color: #D1D5DB !important;
                background-color: #FFFFFF !important;
                color: #1F2937 !important;
            }
            
            /* Date input */
            .stDateInput > div > div > input {
                background-color: #FFFFFF !important;
                color: #1F2937 !important;
                border-color: #D1D5DB !important;
            }
            
            /* Radio buttons */
            .stRadio > label {
                color: #1F2937 !important;
            }
            
            .stRadio [role="radiogroup"] label {
                color: #374151 !important;
            }
            
            /* Slider */
            .stSlider > div > div > div {
                color: #1F2937 !important;
            }
            
            /* Checkbox */
            .stCheckbox > label {
                color: #1F2937 !important;
            }
            
            /* Tabs: refined look */
            .stTabs [data-baseweb="tab-list"] {
                background-color: #F3F4F6 !important;
                border-radius: 0.5rem;
            }
            
            .stTabs [data-baseweb="tab"] {
                color: #6B7280 !important;
            }
            
            .stTabs [aria-selected="true"] {
                color: #111827 !important;
                background-color: #FFFFFF !important;
            }
            
            /* Info/warning/success boxes: subtle backgrounds */
            .stAlert {
                background-color: #F0F9FF !important;
                border-left: 4px solid #3B82F6 !important;
                color: #1E3A8A !important;
            }
            
            [data-testid="stInfo"],
            [data-testid="stWarning"],
            [data-testid="stSuccess"],
            [data-testid="stError"] {
                color: #1F2937 !important;
            }
            
            /* Captions */
            .stCaption {
                color: #6B7280 !important;
            }
            
            /* Code blocks */
            code {
                background-color: #F3F4F6 !important;
                color: #1F2937 !important;
            }
            
            /* Spinner */
            .stSpinner > div {
                border-top-color: #2E86DE !important;
            }
            
            /* Download button */
            .stDownloadButton > button {
                background-color: #FFFFFF !important;
                color: #374151 !important;
                border: 1px solid #D1D5DB !important;
            }
            
            /* Scrollbar styling */
            ::-webkit-scrollbar {
                width: 8px;
                height: 8px;
            }
            
            ::-webkit-scrollbar-track {
                background: #F3F4F6 !important;
            }
            
            ::-webkit-scrollbar-thumb {
                background: #D1D5DB !important;
                border-radius: 4px;
            }
            
            ::-webkit-scrollbar-thumb:hover {
                background: #9CA3AF !important;
            }
            
            /* Plotly chart containers */
            [data-testid="stPlotlyChart"] {
                border-radius: 0.5rem;
            }
        </style>
        """, unsafe_allow_html=True)
    else:
        # Dark theme: minimal overrides (config.toml handles most of it)
        st.markdown("""
        <style>
            /* === DARK THEME: Trading Terminal Feel === */
            /* Config.toml provides base dark theme, these refine it */
            
            [data-testid="stExpander"] {
                background-color: rgba(30, 32, 39, 0.5) !important;
                border: 1px solid rgba(255, 255, 255, 0.1) !important;
            }
            
            [data-testid="stMetricValue"] {
                font-size: 1.5rem;
                font-weight: 600;
            }
            
            /* Compact spacing for KPI strip */
            [data-testid="stHorizontalBlock"] {
                gap: 0.5rem;
            }
            
            /* Scrollbar styling */
            ::-webkit-scrollbar {
                width: 8px;
                height: 8px;
            }
            
            ::-webkit-scrollbar-track {
                background: rgba(255, 255, 255, 0.05) !important;
            }
            
            ::-webkit-scrollbar-thumb {
                background: rgba(255, 255, 255, 0.2) !important;
                border-radius: 4px;
            }
            
            ::-webkit-scrollbar-thumb:hover {
                background: rgba(255, 255, 255, 0.3) !important;
            }
        </style>
        """, unsafe_allow_html=True)
    
    with st.sidebar:
        # Theme toggle at the top of sidebar (mobile-friendly)
        st.markdown("### 🎨 主題 / Theme")
        
        # Theme selector
        theme_option = st.radio(
            "選擇主題 / Select Theme",
            options=["dark", "light"],
            format_func=lambda x: "深色 / Dark" if x == "dark" else "淺色 / Light",
            index=0 if st.session_state.theme == "dark" else 1,
            horizontal=True,
            label_visibility="collapsed",
            help="切換深色/淺色主題 / Switch between dark and light themes"
        )
        
        # Update session state if changed
        if theme_option != st.session_state.theme:
            st.session_state.theme = theme_option
            st.rerun()
        
        st.markdown("---")
        st.header("⚙️ 回測設定 / Settings")
        
        strategy_type = st.selectbox(
            "策略 / Strategy",
            ["SMA Crossover", "RSI Mean Reversion"],
            help="選擇交易策略 / Select trading strategy"
        )
        
        st.subheader("📊 數據來源 / Data Source")
        data_source = st.radio(
            "數據類型 / Data Type",
            ["Yahoo Finance", "範例數據 / Sample CSV", "上傳 CSV / Upload CSV"],
        )
        
        symbol = None
        start_date = None
        end_date = None
        uploaded_file = None
        data_path = None
        
        if data_source == "Yahoo Finance":
            # Phase 1: Quick-pick shortcuts for common indices/ETFs
            ticker_options = get_grouped_ticker_options()
            
            # Initialize session state for symbol if not exists
            if "current_symbol" not in st.session_state:
                st.session_state.current_symbol = "SPY"
            
            # Quick-pick selectbox
            st.markdown("**快速選擇 / Quick Select**")
            selected_preset = st.selectbox(
                "常用指數/ETF",
                options=ticker_options,
                index=ticker_options.index("SPY") if "SPY" in ticker_options else 0,
                format_func=lambda x: x if not is_separator(x) else f"─────────────",
                label_visibility="collapsed",
                key="preset_selector",
            )
            
            # If a valid ticker is selected (not a separator or manual input header)
            if not is_separator(selected_preset):
                st.session_state.current_symbol = selected_preset
            
            # Manual input field (always available)
            st.markdown("**或手動輸入 / Or Manual Input**")
            manual_symbol = st.text_input(
                "股票代號 / Symbol",
                value=st.session_state.current_symbol,
                label_visibility="collapsed",
                key="manual_input",
            )
            
            # Use manual input if it differs from current state
            if manual_symbol != st.session_state.current_symbol:
                st.session_state.current_symbol = manual_symbol
            
            symbol = st.session_state.current_symbol
            
            # Show description if available
            description = get_ticker_description(symbol)
            if description:
                st.caption(f"📊 {description}")
            
            col1, col2 = st.columns(2)
            with col1:
                start_date = st.date_input(
                    "開始日期 / Start",
                    value=datetime(2018, 1, 1)
                )
            with col2:
                end_date = st.date_input(
                    "結束日期 / End",
                    value=datetime.now()
                )
        
        elif data_source == "範例數據 / Sample CSV":
            data_path = "data/sample/SPY_sample.csv"
            st.warning(
                "⚠️ 範例數據僅涵蓋 2020-01-02 至 2020-06-01（約 104 個交易日，COVID-19 熊市期間）。"
                "此期間不足以充分測試 SMA 50/200 策略（需要 200+ 個交易日）。"
                "\n\n⚠️ Sample data covers only 2020-01-02 to 2020-06-01 (~104 bars, COVID-19 bear market). "
                "Insufficient for SMA 50/200 strategy (needs 200+ bars)."
            )
        
        else:  # Upload CSV
            uploaded_file = st.file_uploader(
                "上傳 OHLCV CSV 文件",
                type=["csv"],
                help="需包含 Date, Open, High, Low, Close, Volume"
            )
        
        st.subheader("💰 資金設定 / Capital")
        initial_capital = st.number_input(
            "初始資金 / Initial Capital ($)",
            min_value=1000,
            max_value=10000000,
            value=100000,
            step=10000,
        )
        
        commission = st.number_input(
            "佣金率 / Commission (%)",
            min_value=0.0,
            max_value=1.0,
            value=0.1,
            step=0.01,
            format="%.2f",
        ) / 100
        
        slippage = st.number_input(
            "滑點率 / Slippage (%)",
            min_value=0.0,
            max_value=1.0,
            value=0.05,
            step=0.01,
            format="%.2f",
        ) / 100
        
        position_size = st.slider(
            "倉位大小 / Position Size (%)",
            min_value=10,
            max_value=100,
            value=95,
            step=5,
        ) / 100
        
        st.subheader("🎯 策略參數 / Strategy Parameters")
        
        if strategy_type == "SMA Crossover":
            fast_period = st.number_input(
                "快線週期 / Fast Period",
                min_value=5,
                max_value=200,
                value=20,
                step=5,
            )
            slow_period = st.number_input(
                "慢線週期 / Slow Period",
                min_value=10,
                max_value=300,
                value=50,
                step=10,
            )
        else:  # RSI
            rsi_period = st.number_input(
                "RSI 週期 / RSI Period",
                min_value=5,
                max_value=50,
                value=14,
                step=1,
            )
            rsi_oversold = st.number_input(
                "超賣閾值 / Oversold",
                min_value=10,
                max_value=40,
                value=30,
                step=5,
            )
            rsi_overbought = st.number_input(
                "超買閾值 / Overbought",
                min_value=60,
                max_value=90,
                value=70,
                step=5,
            )
        
        st.markdown("---")
        st.subheader("📅 經濟日曆 / Economic Calendar")
        st.caption("L1 研究層：顯示與對齊 / L1 Research: Display & Alignment")
        
        show_calendar = st.checkbox(
            "顯示經濟公佈日 / Show Economic Releases",
            value=True,
            help="在圖表上標記重要經濟數據發布日期 / Mark major economic data release dates on chart"
        )
        
        calendar_event_types = []
        calendar_filter_enabled = False
        calendar_filter_days_before = 0
        calendar_filter_days_after = 0
        
        if show_calendar:
            # Load calendar to get available types
            temp_cal = EconomicCalendar()
            if temp_cal.load():
                available_types = temp_cal.get_available_types()
                calendar_event_types = st.multiselect(
                    "事件類型 / Event Types",
                    options=available_types,
                    default=available_types,
                    help="選擇要顯示的經濟事件類型 / Select economic event types to display"
                )
                
                st.markdown("**⚠️ 研究過濾（可選）/ Research Filter (Optional)**")
                st.caption("此過濾僅用於研究對比，不會修改主回測結果 / For research comparison only, does not modify main backtest results")
                
                calendar_filter_enabled = st.checkbox(
                    "啟用避開公佈日過濾 / Enable Release Date Avoidance Filter",
                    value=False,
                    help="過濾在經濟數據發布前後±N天進場的交易（僅研究用途）/ Filter trades entered ±N days around releases (research only)"
                )
                
                if calendar_filter_enabled:
                    col_before, col_after = st.columns(2)
                    with col_before:
                        calendar_filter_days_before = st.number_input(
                            "避開前 N 日 / Days Before",
                            min_value=0,
                            max_value=5,
                            value=1,
                            step=1,
                        )
                    with col_after:
                        calendar_filter_days_after = st.number_input(
                            "避開後 N 日 / Days After",
                            min_value=0,
                            max_value=5,
                            value=0,
                            step=1,
                        )
        
        st.markdown("---")
        st.subheader("📰 新聞研究 / News Research")
        st.caption("L1 研究層：顯示與對齊 / L1 Research: Display & Alignment")
        
        show_news = st.checkbox(
            "顯示新聞（研究）/ Show News (Research)",
            value=False,
            help="顯示回測期間的新聞標題（僅供研究參考，不影響回測結果）/ Display news headlines during backtest period (research only, does not affect backtest results)"
        )
        
        if show_news:
            st.caption("⚠️ 研究用途、非完整歷史 / For research only, not comprehensive historical coverage")
        
        st.markdown("---")
        st.subheader("📊 財報／商蹤時間線 / Earnings Timeline")
        st.caption("L1 研究層：顯示與對齊 / L1 Research: Display & Alignment")
        
        show_earnings = st.checkbox(
            "顯示財報／商蹤（研究）/ Show Earnings/Business Events (Research)",
            value=False,
            help="顯示回測期間的財報及重要企業事件（僅供研究參考，不影響回測結果）/ Display earnings and major business events during backtest period (research only, does not affect backtest results)"
        )
        
        earnings_filter_enabled = False
        earnings_filter_days_before = 0
        earnings_filter_days_after = 0
        
        if show_earnings:
            st.caption("**單一股票**：顯示財報日期 / **Single stocks**: Show earnings dates")
            st.caption("**指數／ETF**：優雅降級（樣本數據）/ **Index/ETF**: Graceful degradation (sample data)")
            
            st.markdown("**⚠️ 研究過濾（可選）/ Research Filter (Optional)**")
            st.caption("此過濾僅用於研究對比，不會修改主回測結果 / For research comparison only, does not modify main backtest results")
            
            earnings_filter_enabled = st.checkbox(
                "啟用避開財報日過濾 / Enable Earnings Date Avoidance Filter",
                value=False,
                help="過濾在財報發布前後±N天進場的交易（僅研究用途）/ Filter trades entered ±N days around earnings (research only)"
            )
            
            if earnings_filter_enabled:
                col_before, col_after = st.columns(2)
                with col_before:
                    earnings_filter_days_before = st.number_input(
                        "避開前 N 日（財報）/ Days Before (Earnings)",
                        min_value=0,
                        max_value=5,
                        value=1,
                        step=1,
                        key="earnings_before"
                    )
                with col_after:
                    earnings_filter_days_after = st.number_input(
                        "避開後 N 日（財報）/ Days After (Earnings)",
                        min_value=0,
                        max_value=5,
                        value=0,
                        step=1,
                        key="earnings_after"
                    )
        
        st.markdown("---")
        st.subheader("🎯 Phase 5：事件驅動規則 / Event-Driven Rules")
        st.caption("L2 層：可選事件感知策略 / L2 Layer: Opt-in event-aware strategy")
        
        enable_phase5 = st.checkbox(
            "啟用 Phase 5 對比 / Enable Phase 5 Comparison",
            value=False,
            help="運行控制組與事件感知策略對比（在已知事件前後阻止進場）/ Run control vs event-aware strategy comparison (blocks entries around known events)"
        )
        
        phase5_economic_enabled = False
        phase5_economic_types = None
        phase5_economic_before = 1
        phase5_economic_after = 0
        phase5_earnings_enabled = False
        phase5_earnings_before = 1
        phase5_earnings_after = 0
        
        if enable_phase5:
            st.info(
                "⚠️ **Phase 5 說明 / Phase 5 Notice**\n\n"
                "Phase 5 會運行兩個回測：\n"
                "1. **控制組**：您的策略不變（L0 預設）\n"
                "2. **事件感知**：同樣策略，但在事件前後 ±N 日阻止買入訊號（L2 規則）\n\n"
                "Phase 5 runs two backtests:\n"
                "1. **Control**: Your strategy unchanged (L0 default)\n"
                "2. **Event-aware**: Same strategy, but blocks BUY signals ±N days around events (L2 rules)"
            )
            
            st.markdown("**經濟事件黑名單 / Economic Event Blackout**")
            phase5_economic_enabled = st.checkbox(
                "使用經濟事件黑名單 / Use Economic Event Blackout",
                value=True,
                help="在重要經濟數據發布前後阻止進場 / Block entries around major economic releases"
            )
            
            if phase5_economic_enabled:
                # Load calendar to get available types
                temp_cal = EconomicCalendar()
                if temp_cal.load():
                    available_types = temp_cal.get_available_types()
                    phase5_economic_types = st.multiselect(
                        "事件類型 / Event Types",
                        options=available_types,
                        default=available_types,
                        help="選擇要避開的經濟事件類型 / Select economic event types to avoid",
                        key="phase5_econ_types"
                    )
                
                col_before, col_after = st.columns(2)
                with col_before:
                    phase5_economic_before = st.number_input(
                        "前 N 日 / Days Before",
                        min_value=0,
                        max_value=5,
                        value=1,
                        step=1,
                        key="phase5_econ_before"
                    )
                with col_after:
                    phase5_economic_after = st.number_input(
                        "後 N 日 / Days After",
                        min_value=0,
                        max_value=5,
                        value=0,
                        step=1,
                        key="phase5_econ_after"
                    )
            
            st.markdown("**財報事件黑名單 / Earnings Event Blackout**")
            phase5_earnings_enabled = st.checkbox(
                "使用財報事件黑名單 / Use Earnings Event Blackout",
                value=True,
                help="在財報發布前後阻止進場 / Block entries around earnings releases"
            )
            
            if phase5_earnings_enabled:
                col_before, col_after = st.columns(2)
                with col_before:
                    phase5_earnings_before = st.number_input(
                        "前 N 日（財報）/ Days Before (Earnings)",
                        min_value=0,
                        max_value=5,
                        value=1,
                        step=1,
                        key="phase5_earn_before"
                    )
                with col_after:
                    phase5_earnings_after = st.number_input(
                        "後 N 日（財報）/ Days After (Earnings)",
                        min_value=0,
                        max_value=5,
                        value=0,
                        step=1,
                        key="phase5_earn_after"
                    )
        
        st.markdown("---")
        run_backtest = st.button("🚀 運行回測 / Run Backtest", use_container_width=True)
    
    if run_backtest:
        try:
            with st.spinner("正在加載數據... / Loading data..."):
                loader = DataLoader()
                
                if data_path:
                    data = loader.load_csv(data_path)
                elif uploaded_file:
                    data = pd.read_csv(
                        uploaded_file,
                        parse_dates=["Date"],
                        index_col="Date"
                    )
                    data = data.sort_index()
                elif symbol:
                    data = loader.fetch_yahoo(
                        symbol,
                        start_date.strftime("%Y-%m-%d"),
                        end_date.strftime("%Y-%m-%d"),
                    )
                else:
                    st.error("請選擇數據來源 / Please select a data source")
                    return
                
                st.success(f"✅ 加載 {len(data)} 個數據點 / Loaded {len(data)} bars")
            
            with st.spinner("正在運行回測... / Running backtest..."):
                # Determine strategy class
                if strategy_type == "SMA Crossover":
                    strategy_class = SMACrossover
                    strategy_params = {
                        "fast_period": int(fast_period),
                        "slow_period": int(slow_period),
                    }
                else:
                    strategy_class = RSIMeanReversion
                    strategy_params = {
                        "period": int(rsi_period),
                        "oversold": rsi_oversold,
                        "overbought": rsi_overbought,
                    }
                
                # Phase 5: Run control vs event-aware comparison if enabled
                if enable_phase5:
                    # Configure event rules
                    event_config = EventRuleConfig(
                        enabled=True,
                        use_economic_events=phase5_economic_enabled,
                        economic_event_types=phase5_economic_types if phase5_economic_enabled else None,
                        economic_days_before=phase5_economic_before,
                        economic_days_after=phase5_economic_after,
                        use_earnings_events=phase5_earnings_enabled,
                        earnings_days_before=phase5_earnings_before,
                        earnings_days_after=phase5_earnings_after,
                    )
                    
                    # Create strategy instance factory
                    def create_strategy():
                        return strategy_class(**strategy_params)
                    
                    # Run comparison
                    phase5_results = run_control_vs_event_aware(
                        strategy=create_strategy,
                        data=data,
                        initial_capital=initial_capital,
                        commission=commission,
                        slippage=slippage,
                        position_size=position_size,
                        event_config=event_config,
                        symbol=symbol,
                    )
                    
                    # Extract control results (this is the L0 default)
                    engine = phase5_results["control"]["engine"]
                    equity_curve = phase5_results["control"]["equity"]
                    
                    # Store event-aware results for later display
                    phase5_event_engine = phase5_results["event_aware"]["engine"]
                    phase5_event_equity = phase5_results["event_aware"]["equity"]
                    phase5_blocked_signals = phase5_results["event_aware"]["blocked_signals"]
                else:
                    # Standard L0 backtest (no Phase 5)
                    strategy = strategy_class(**strategy_params)
                    
                    engine = BacktestEngine(
                        initial_capital=initial_capital,
                        commission=commission,
                        slippage=slippage,
                        position_size_type="fixed_fraction",
                        position_size_value=position_size,
                    )
                    
                    equity_curve = engine.run(strategy, data)
                    phase5_event_engine = None
                    phase5_event_equity = None
                    phase5_blocked_signals = 0
                
                # Calculate buy-and-hold benchmark
                buy_hold_curve = calculate_buy_and_hold(
                    data=data,
                    initial_capital=initial_capital,
                    commission=commission,
                )
                
                metrics_calculator = PerformanceMetrics(
                    equity_curve=equity_curve,
                    trades=engine.trades,
                    initial_capital=initial_capital,
                    buy_hold_curve=buy_hold_curve,
                )
                metrics = metrics_calculator.calculate_all()
            
            # Load economic calendar if enabled (L1 layer - does not affect L0 backtest)
            calendar_events = None
            calendar_loaded = False
            if show_calendar and calendar_event_types:
                economic_calendar = EconomicCalendar()
                if economic_calendar.load():
                    calendar_loaded = True
                    calendar_events = economic_calendar.filter_by_date_range(
                        start_date=data.index.min(),
                        end_date=data.index.max(),
                        event_types=calendar_event_types if calendar_event_types else None,
                    )
            
            # Load news panel if enabled (L1 layer - does not affect L0 backtest)
            news_items = None
            news_loaded = False
            news_source = "none"
            if show_news:
                news_panel = NewsPanel()
                # Try to load news (prefer sample CSV for reproducibility)
                if news_panel.load(symbol=symbol, start_date=data.index.min(), end_date=data.index.max()):
                    news_loaded = True
                    news_source = news_panel.get_data_source()
                    news_items = news_panel.filter_by_date_range(
                        start_date=data.index.min(),
                        end_date=data.index.max(),
                        symbol=symbol,
                    )
            
            # Load earnings calendar if enabled (L1 layer - does not affect L0 backtest)
            earnings_events = None
            earnings_loaded = False
            earnings_source = "none"
            if show_earnings:
                earnings_calendar = EarningsCalendar()
                # Try to load earnings (prefer sample CSV, with yfinance fallback)
                if earnings_calendar.load(symbol=symbol, start_date=data.index.min(), end_date=data.index.max(), prefer_yfinance=False):
                    earnings_loaded = True
                    earnings_source = earnings_calendar.get_data_source()
                    earnings_events = earnings_calendar.filter_by_date_range(
                        start_date=data.index.min(),
                        end_date=data.index.max(),
                        symbol=symbol if earnings_source != "sample_csv" else None,  # Sample CSV may have multiple symbols
                    )
            
            st.success("✅ 回測完成 / Backtest complete!")
            
            # Display calendar status if enabled
            if show_calendar:
                if calendar_loaded and calendar_events is not None and not calendar_events.empty:
                    st.info(f"📅 已載入 {len(calendar_events)} 個經濟事件標記 / Loaded {len(calendar_events)} economic event markers")
                elif show_calendar:
                    st.caption("⚠️ 經濟日曆數據未載入（優雅降級）/ Economic calendar data not loaded (graceful degradation)")
            
            # Display news status if enabled
            if show_news:
                if news_loaded and news_items is not None and not news_items.empty:
                    source_label = "示範 CSV / Sample CSV" if news_source == "sample_csv" else "yfinance"
                    st.info(f"📰 已載入 {len(news_items)} 則新聞（來源：{source_label}）/ Loaded {len(news_items)} news items (source: {source_label})")
                else:
                    st.caption("⚠️ 新聞數據未載入（優雅降級；回測結果不受影響）/ News data not loaded (graceful degradation; backtest results unaffected)")
            
            # Display earnings status if enabled
            if show_earnings:
                if earnings_loaded and earnings_events is not None and not earnings_events.empty:
                    if earnings_source == "sample_csv":
                        source_label = "示範 CSV / Sample CSV"
                    elif earnings_source == "yfinance":
                        source_label = "yfinance"
                    elif earnings_source == "index_not_supported":
                        source_label = "指數不支援 / Index not supported"
                    else:
                        source_label = "無 / None"
                    st.info(f"📊 已載入 {len(earnings_events)} 個財報事件（來源：{source_label}）/ Loaded {len(earnings_events)} earnings events (source: {source_label})")
                elif earnings_source == "index_not_supported":
                    st.caption("ℹ️ 指數／ETF 符號：完整成分股財報日曆未提供（顯示樣本數據）/ Index/ETF symbol: Full constituent earnings calendar not provided (showing sample data)")
                else:
                    st.caption("⚠️ 財報數據未載入（優雅降級；回測結果不受影響）/ Earnings data not loaded (graceful degradation; backtest results unaffected)")
            
            st.markdown("## 📊 績效指標 / Performance Metrics")
            
            def format_metric(value, fmt=".2f", suffix=""):
                """Format metric safely, handling NaN/inf values."""
                if pd.isna(value) or not np.isfinite(value):
                    return "N/A"
                return f"{value:{fmt}}{suffix}"
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric(
                    "總回報 / Total Return",
                    format_metric(metrics.get('total_return_pct', float('nan')), suffix="%"),
                )
            with col2:
                st.metric(
                    "年化報酬 / CAGR",
                    format_metric(metrics.get('cagr_pct', float('nan')), suffix="%"),
                )
            with col3:
                st.metric(
                    "最大回撤 / Max Drawdown",
                    format_metric(metrics.get('max_drawdown_pct', float('nan')), suffix="%"),
                )
            with col4:
                st.metric(
                    "夏普比率 / Sharpe",
                    format_metric(metrics.get('sharpe_ratio', float('nan'))),
                )
            
            col5, col6, col7, col8 = st.columns(4)
            with col5:
                st.metric(
                    "初始資金 / Initial",
                    f"${metrics.get('initial_capital', 0):,.0f}",
                )
            with col6:
                final_eq = metrics.get('final_equity', float('nan'))
                final_eq_str = "N/A" if pd.isna(final_eq) or not np.isfinite(final_eq) else f"${final_eq:,.0f}"
                st.metric(
                    "最終權益 / Final",
                    final_eq_str,
                )
            with col7:
                st.metric(
                    "交易次數 / Trades",
                    f"{metrics.get('trade_count', 0)}",
                )
            with col8:
                st.metric(
                    "勝率 / Win Rate",
                    format_metric(metrics.get('win_rate_pct', float('nan')), fmt=".1f", suffix="%"),
                )
            
            # Buy-and-hold benchmark comparison
            st.markdown("### 📉 買入持有基準 / Buy & Hold Benchmark")
            col9, col10 = st.columns(2)
            with col9:
                st.metric(
                    "買入持有最終權益 / Buy & Hold Final",
                    f"${metrics['buy_hold_final']:,.0f}",
                )
            with col10:
                st.metric(
                    "買入持有回報 / Buy & Hold Return",
                    f"{metrics['buy_hold_return_pct']:.2f}%",
                )
            
            # Educational note in Traditional Chinese
            st.info(
                "💡 **教育性說明 / Educational Note**\n\n"
                "策略回報為正不代表策略有效——需要比較「買入持有」基準。"
                "這些策略僅供教育和研究使用，不構成投資建議。"
                "過去績效不代表未來表現。"
                "\n\n"
                "A positive strategy return does not mean the strategy is effective—you must compare against "
                "the buy-and-hold benchmark. These strategies are for educational and research purposes only "
                "and do not constitute investment advice. Past performance does not guarantee future results."
            )
            
            # Phase 5 comparison display
            if enable_phase5 and phase5_event_engine is not None:
                st.markdown("---")
                st.markdown("## 🎯 Phase 5：控制組 vs 事件感知對比 / Control vs Event-Aware Comparison")
                
                st.warning(
                    "⚠️ **Phase 5 對比說明 / Phase 5 Comparison Notice**\n\n"
                    "**控制組（上方）**：您的策略不變，這是 L0 預設回測結果。\n"
                    "**事件感知（下方）**：同樣策略，但在已知事件前後阻止買入訊號（L2 事件驅動規則）。\n\n"
                    "**Control (above)**: Your strategy unchanged, this is the L0 default backtest result.\n"
                    "**Event-aware (below)**: Same strategy, but blocks BUY signals around known events (L2 event-driven rules)."
                )
                
                # Calculate event-aware metrics
                phase5_event_metrics_calc = PerformanceMetrics(
                    equity_curve=phase5_event_equity,
                    trades=phase5_event_engine.trades,
                    initial_capital=initial_capital,
                    buy_hold_curve=buy_hold_curve,
                )
                phase5_event_metrics = phase5_event_metrics_calc.calculate_all()
                
                st.markdown("### 績效對比摘要 / Performance Comparison Summary")
                
                col_left, col_right = st.columns(2)
                
                with col_left:
                    st.markdown("**🔵 控制組（L0 預設）/ Control (L0 Default)**")
                    st.metric("交易次數 / Trades", metrics.get('trade_count', 0))
                    st.metric("總回報 / Return", f"{metrics.get('total_return_pct', 0):.2f}%")
                    st.metric("夏普比率 / Sharpe", format_metric(metrics.get('sharpe_ratio', float('nan')), fmt=".2f"))
                    st.metric("最大回撤 / Max DD", f"{metrics.get('max_drawdown_pct', 0):.2f}%")
                    st.metric("勝率 / Win Rate", f"{metrics.get('win_rate_pct', 0):.1f}%")
                
                with col_right:
                    st.markdown("**🟢 事件感知（L2 規則）/ Event-Aware (L2 Rules)**")
                    blocked_count = metrics.get('trade_count', 0) - phase5_event_metrics.get('trade_count', 0)
                    st.metric(
                        "交易次數 / Trades",
                        phase5_event_metrics.get('trade_count', 0),
                        delta=f"-{blocked_count} (阻止 {phase5_blocked_signals} 訊號 / blocked {phase5_blocked_signals} signals)",
                        delta_color="off"
                    )
                    return_delta = phase5_event_metrics.get('total_return_pct', 0) - metrics.get('total_return_pct', 0)
                    st.metric(
                        "總回報 / Return",
                        f"{phase5_event_metrics.get('total_return_pct', 0):.2f}%",
                        delta=f"{return_delta:+.2f}%",
                    )
                    sharpe_control = metrics.get('sharpe_ratio', float('nan'))
                    sharpe_event = phase5_event_metrics.get('sharpe_ratio', float('nan'))
                    sharpe_delta = sharpe_event - sharpe_control if not (pd.isna(sharpe_control) or pd.isna(sharpe_event)) else float('nan')
                    st.metric(
                        "夏普比率 / Sharpe",
                        format_metric(sharpe_event, fmt=".2f"),
                        delta=format_metric(sharpe_delta, fmt=".2f") if not pd.isna(sharpe_delta) else "N/A",
                    )
                    dd_delta = phase5_event_metrics.get('max_drawdown_pct', 0) - metrics.get('max_drawdown_pct', 0)
                    st.metric(
                        "最大回撤 / Max DD",
                        f"{phase5_event_metrics.get('max_drawdown_pct', 0):.2f}%",
                        delta=f"{dd_delta:+.2f}%",
                        delta_color="inverse",
                    )
                    win_rate_delta = phase5_event_metrics.get('win_rate_pct', 0) - metrics.get('win_rate_pct', 0)
                    st.metric(
                        "勝率 / Win Rate",
                        f"{phase5_event_metrics.get('win_rate_pct', 0):.1f}%",
                        delta=f"{win_rate_delta:+.1f}%",
                    )
                
                st.info(
                    "💡 **解讀 / Interpretation**\n\n"
                    "對比控制組與事件感知結果，可研究在已知事件前後阻止進場對策略績效的影響。\n"
                    "若事件感知版本績效顯著改善，可考慮將事件規則整合到策略中（需獨立驗證與測試）。\n\n"
                    "Comparing control vs. event-aware results helps research the impact of blocking entries around known events. "
                    "If event-aware performance is significantly better, consider integrating event rules into your strategy (requires independent validation and testing)."
                )
                
                # Overlay equity curves
                st.markdown("### 權益曲線對比 / Equity Curve Comparison")
                fig_comparison = go.Figure()
                
                # Control equity curve
                fig_comparison.add_trace(go.Scatter(
                    x=equity_curve.index,
                    y=equity_curve["Equity"],
                    mode="lines",
                    name="控制組 / Control",
                    line=dict(color="#2E86DE", width=2),
                ))
                
                # Event-aware equity curve
                fig_comparison.add_trace(go.Scatter(
                    x=phase5_event_equity.index,
                    y=phase5_event_equity["Equity"],
                    mode="lines",
                    name="事件感知 / Event-Aware",
                    line=dict(color="#27AE60", width=2, dash="dash"),
                ))
                
                # Theme-specific styling
                if st.session_state.theme == "light":
                    paper_bg = "#FFFFFF"
                    plot_bg = "#F8F9FA"
                    font_color = "#1F2937"
                    grid_color = "rgba(128,128,128,0.2)"
                else:
                    paper_bg = "rgba(0,0,0,0)"
                    plot_bg = "rgba(0,0,0,0)"
                    font_color = "#FAFAFA"
                    grid_color = "rgba(128,128,128,0.15)"
                
                fig_comparison.update_layout(
                    title=dict(text="控制組 vs 事件感知權益曲線 / Control vs Event-Aware Equity Curves", font=dict(color=font_color)),
                    xaxis_title="日期 / Date",
                    yaxis_title="權益 / Equity ($)",
                    hovermode="x unified",
                    template="plotly",
                    plot_bgcolor=plot_bg,
                    paper_bgcolor=paper_bg,
                    font=dict(family="sans-serif", size=12, color=font_color),
                    xaxis=dict(showgrid=True, gridwidth=1, gridcolor=grid_color, zeroline=False, color=font_color),
                    yaxis=dict(showgrid=True, gridwidth=1, gridcolor=grid_color, zeroline=False, color=font_color),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color=font_color)),
                )
                
                st.plotly_chart(fig_comparison, use_container_width=True)
            
            st.markdown("---")
            
            st.markdown("## 📈 圖表 / Charts")
            
            tab1, tab2 = st.tabs(["權益曲線 / Equity Curve", "回撤圖 / Drawdown"])
            
            with tab1:
                # Pass calendar events and earnings to chart (L1 display only - does not affect L0 backtest)
                chart_events = calendar_events if (show_calendar and calendar_loaded) else None
                chart_earnings = earnings_events if (show_earnings and earnings_loaded) else None
                st.plotly_chart(
                    plot_equity_curve(equity_curve, buy_hold_curve, event_markers=chart_events, earnings_markers=chart_earnings, theme=st.session_state.theme),
                    use_container_width=True
                )
            
            with tab2:
                st.plotly_chart(plot_drawdown(equity_curve, theme=st.session_state.theme), use_container_width=True)
            
            st.markdown("---")
            
            # Economic events table (L1 display)
            if show_calendar and calendar_loaded and calendar_events is not None and not calendar_events.empty:
                with st.expander("📅 經濟事件列表 / Economic Events List", expanded=False):
                    st.dataframe(
                        calendar_events.style.format({"Date": lambda x: x.strftime("%Y-%m-%d")}),
                        use_container_width=True,
                    )
                    st.caption(
                        "🕐 時區：美東時間（US Eastern Time）｜"
                        "資料來源：靜態 CSV（可定期更新）｜"
                        "Data source: Static CSV (periodic updates) | Timezone: US Eastern"
                    )
            
            # News panel (L1 display)
            if show_news and news_loaded and news_items is not None and not news_items.empty:
                with st.expander("📰 新聞列表 / News Headlines", expanded=False):
                    # Format news display
                    news_display = news_items[["Date", "Headline", "Sentiment"]].copy()
                    news_display["Date"] = news_display["Date"].dt.strftime("%Y-%m-%d")
                    
                    # Add sentiment emoji
                    sentiment_emoji = {
                        "Positive": "🟢",
                        "Negative": "🔴",
                        "Neutral": "⚪",
                    }
                    news_display["Sentiment"] = news_display["Sentiment"].apply(
                        lambda x: f"{sentiment_emoji.get(x, '⚪')} {x}"
                    )
                    
                    st.dataframe(
                        news_display,
                        use_container_width=True,
                        hide_index=True,
                    )
                    st.caption(
                        f"⚠️ 研究用途、非完整歷史（來源：{news_source}）/ For research only, not comprehensive (source: {news_source})\n\n"
                        f"💡 情緒標籤為簡單啟發式分類，僅供參考 / Sentiment labels are simple heuristic-based, for reference only"
                    )
            
            # Earnings events table (L1 display)
            if show_earnings and earnings_loaded and earnings_events is not None and not earnings_events.empty:
                with st.expander("📊 財報事件列表 / Earnings Events List", expanded=False):
                    earnings_display = earnings_events[["Date", "Event", "Symbol"]].copy()
                    earnings_display["Date"] = earnings_display["Date"].dt.strftime("%Y-%m-%d")
                    
                    st.dataframe(
                        earnings_display,
                        use_container_width=True,
                        hide_index=True,
                    )
                    st.caption(
                        f"⚠️ 研究用途、非完整歷史（來源：{earnings_source}）/ For research only, not comprehensive (source: {earnings_source})\n\n"
                        f"💡 單一股票顯示財報日期；指數／ETF 為樣本數據 / Single stocks show earnings dates; index/ETF shows sample data"
                    )
                    
                    # CSV export option
                    if st.button("📥 匯出財報事件 CSV / Export Earnings Events CSV"):
                        csv = earnings_events.to_csv(index=False)
                        st.download_button(
                            label="下載 CSV / Download CSV",
                            data=csv,
                            file_name=f"earnings_events_{symbol}_{data.index.min().strftime('%Y%m%d')}_{data.index.max().strftime('%Y%m%d')}.csv",
                            mime="text/csv",
                        )
            
            # Research filter comparison (opt-in only, shows side-by-side)
            if show_calendar and calendar_loaded and calendar_filter_enabled and calendar_events is not None:
                st.markdown("---")
                st.markdown("## 🔬 研究過濾對比 / Research Filter Comparison")
                st.warning(
                    "⚠️ **研究過濾警告 / Research Filter Notice**\n\n"
                    "此過濾僅用於研究目的，比較避開經濟數據發布日的績效差異。"
                    "**主回測結果（上方）保持不變**，此處顯示過濾後的次要結果供對比參考。\n\n"
                    "This filter is for research purposes only, comparing performance when avoiding economic release dates. "
                    "**Main backtest results (above) remain unchanged**. Filtered results shown here for comparison."
                )
                
                # Create exclusion window
                economic_calendar_obj = EconomicCalendar()
                economic_calendar_obj.load()
                event_dates = economic_calendar_obj.get_event_dates(
                    start_date=data.index.min(),
                    end_date=data.index.max(),
                    event_types=calendar_event_types if calendar_event_types else None,
                )
                excluded_dates = economic_calendar_obj.create_exclusion_window(
                    event_dates,
                    days_before=calendar_filter_days_before,
                    days_after=calendar_filter_days_after,
                )
                
                # Filter trades
                trades_df = engine.get_trades_df()
                filtered_trades_df = economic_calendar_obj.filter_trades_by_exclusion(
                    trades_df,
                    excluded_dates,
                    entry_column="Entry Date",
                )
                
                # Calculate filtered metrics
                filtered_metrics = calculate_research_metrics(
                    filtered_trades_df,
                    initial_capital,
                    equity_curve,
                )
                
                st.markdown("### 對比摘要 / Comparison Summary")
                col_left, col_right = st.columns(2)
                
                with col_left:
                    st.markdown("**🔵 完整回測 / Full Backtest**")
                    st.metric("交易次數 / Trades", metrics.get('trade_count', 0))
                    st.metric("總回報 / Return", f"{metrics.get('total_return_pct', 0):.2f}%")
                    st.metric("勝率 / Win Rate", f"{metrics.get('win_rate_pct', 0):.1f}%")
                
                with col_right:
                    st.markdown(f"**🔬 過濾後（避開 ±{calendar_filter_days_before}/{calendar_filter_days_after} 日）/ Filtered**")
                    excluded_count = metrics.get('trade_count', 0) - filtered_metrics['trade_count']
                    st.metric(
                        "交易次數 / Trades",
                        filtered_metrics['trade_count'],
                        delta=f"-{excluded_count}",
                        delta_color="off"
                    )
                    return_delta = filtered_metrics['total_return_pct'] - metrics.get('total_return_pct', 0)
                    st.metric(
                        "總回報 / Return",
                        f"{filtered_metrics['total_return_pct']:.2f}%",
                        delta=f"{return_delta:+.2f}%",
                    )
                    win_rate_delta = filtered_metrics['win_rate_pct'] - metrics.get('win_rate_pct', 0)
                    st.metric(
                        "勝率 / Win Rate",
                        f"{filtered_metrics['win_rate_pct']:.1f}%",
                        delta=f"{win_rate_delta:+.1f}%",
                    )
                
                st.info(
                    "💡 **解讀 / Interpretation**\n\n"
                    "對比完整回測與過濾後結果，可研究經濟數據發布對策略績效的影響。"
                    "若過濾後績效顯著改善，可考慮將「避開公佈日」納入 L2 事件驅動策略（需獨立開發與測試）。\n\n"
                    "Comparing full vs. filtered results helps research the impact of economic releases on strategy performance. "
                    "If filtered performance is significantly better, consider developing an L2 event-driven strategy (requires separate development and testing)."
                )
            
            # Earnings research filter comparison (opt-in only)
            if show_earnings and earnings_loaded and earnings_filter_enabled and earnings_events is not None:
                st.markdown("---")
                st.markdown("## 🔬 財報過濾對比 / Earnings Filter Comparison")
                st.warning(
                    "⚠️ **研究過濾警告 / Research Filter Notice**\n\n"
                    "此過濾僅用於研究目的，比較避開財報發布日的績效差異。"
                    "**主回測結果（上方）保持不變**，此處顯示過濾後的次要結果供對比參考。\n\n"
                    "This filter is for research purposes only, comparing performance when avoiding earnings dates. "
                    "**Main backtest results (above) remain unchanged**. Filtered results shown here for comparison."
                )
                
                # Create exclusion window
                earnings_calendar_obj = EarningsCalendar()
                earnings_calendar_obj.load(symbol=symbol, start_date=data.index.min(), end_date=data.index.max())
                earnings_dates = earnings_calendar_obj.get_event_dates(
                    start_date=data.index.min(),
                    end_date=data.index.max(),
                    symbol=symbol if earnings_source != "sample_csv" else None,
                )
                excluded_earnings_dates = earnings_calendar_obj.create_exclusion_window(
                    earnings_dates,
                    days_before=earnings_filter_days_before,
                    days_after=earnings_filter_days_after,
                )
                
                # Filter trades
                trades_df = engine.get_trades_df()
                filtered_earnings_trades_df = earnings_calendar_obj.filter_trades_by_exclusion(
                    trades_df,
                    excluded_earnings_dates,
                    entry_column="Entry Date",
                )
                
                # Calculate filtered metrics
                from backtester.earnings_calendar import calculate_research_metrics as calc_earnings_metrics
                filtered_earnings_metrics = calc_earnings_metrics(
                    filtered_earnings_trades_df,
                    initial_capital,
                    equity_curve,
                )
                
                st.markdown("### 對比摘要 / Comparison Summary")
                col_left, col_right = st.columns(2)
                
                with col_left:
                    st.markdown("**🔵 完整回測 / Full Backtest**")
                    st.metric("交易次數 / Trades", metrics.get('trade_count', 0))
                    st.metric("總回報 / Return", f"{metrics.get('total_return_pct', 0):.2f}%")
                    st.metric("勝率 / Win Rate", f"{metrics.get('win_rate_pct', 0):.1f}%")
                
                with col_right:
                    st.markdown(f"**🔬 過濾後（避開財報 ±{earnings_filter_days_before}/{earnings_filter_days_after} 日）/ Filtered**")
                    excluded_count = metrics.get('trade_count', 0) - filtered_earnings_metrics['trade_count']
                    st.metric(
                        "交易次數 / Trades",
                        filtered_earnings_metrics['trade_count'],
                        delta=f"-{excluded_count}",
                        delta_color="off"
                    )
                    return_delta = filtered_earnings_metrics['total_return_pct'] - metrics.get('total_return_pct', 0)
                    st.metric(
                        "總回報 / Return",
                        f"{filtered_earnings_metrics['total_return_pct']:.2f}%",
                        delta=f"{return_delta:+.2f}%",
                    )
                    win_rate_delta = filtered_earnings_metrics['win_rate_pct'] - metrics.get('win_rate_pct', 0)
                    st.metric(
                        "勝率 / Win Rate",
                        f"{filtered_earnings_metrics['win_rate_pct']:.1f}%",
                        delta=f"{win_rate_delta:+.1f}%",
                    )
                
                st.info(
                    "💡 **解讀 / Interpretation**\n\n"
                    "對比完整回測與過濾後結果，可研究財報發布對策略績效的影響。"
                    "若過濾後績效顯著改善，可考慮將「避開財報日」納入 L2 事件驅動策略（需獨立開發與測試）。\n\n"
                    "Comparing full vs. filtered results helps research the impact of earnings releases on strategy performance. "
                    "If filtered performance is significantly better, consider developing an L2 event-driven strategy (requires separate development and testing)."
                )
            
            st.markdown("---")
            
            st.markdown("## 📋 交易明細 / Trade Details")
            
            if engine.trades:
                trades_df = engine.get_trades_df()
                st.dataframe(
                    trades_df.style.format({
                        "Entry Price": "${:.2f}",
                        "Exit Price": "${:.2f}",
                        "PnL": "${:,.2f}",
                        "Return %": "{:.2f}%",
                    }),
                    use_container_width=True,
                )
                
                csv = trades_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 下載交易記錄 / Download Trades",
                    data=csv,
                    file_name=f"trades_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                )
            else:
                st.info("在回測期間未執行任何交易 / No trades executed during backtest period")
        
        except Exception as e:
            st.error(f"❌ 錯誤 / Error: {str(e)}")
            st.exception(e)
    
    else:
        st.info("👈 請在左側設定參數並點擊「運行回測」按鈕開始\n\n← Please configure parameters in the sidebar and click 'Run Backtest'")
        
        st.markdown("## 快速開始 / Quick Start")
        st.markdown("""
        **預設設定已可運行：**
        1. 數據來源：Yahoo Finance（SPY，2018-01-01 至今）
        2. 策略：SMA 交叉（快線 20 / 慢線 50）
        3. 點擊「運行回測」按鈕
        
        **Default settings are ready to run:**
        1. Data source: Yahoo Finance (SPY, 2018-01-01 to today)
        2. Strategy: SMA Crossover (fast 20 / slow 50)
        3. Click 'Run Backtest' button
        
        ---
        
        **功能 / Features:**
        - 📊 即時圖表顯示權益曲線和回撤
        - 📈 完整績效指標（回報率、CAGR、夏普比率等）
        - 📉 買入持有基準比較
        - 💰 可自訂佣金、滑點和倉位大小
        - 🔄 支援 Yahoo Finance 線上數據或上傳自己的 CSV
        - 📥 下載交易明細
        """)


if __name__ == "__main__":
    main()
