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
from backtester.ticker_presets import (
    get_grouped_ticker_options,
    is_separator,
    get_ticker_description,
)


st.set_page_config(
    page_title="演算法交易回測系統",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)


def plot_equity_curve(
    equity_df: pd.DataFrame,
    buy_hold_df: Optional[pd.DataFrame] = None,
    event_markers: Optional[pd.DataFrame] = None,
    earnings_markers: Optional[pd.DataFrame] = None,
) -> go.Figure:
    """Create equity curve chart with optional buy-and-hold benchmark and event markers."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=equity_df.index,
        y=equity_df["Equity"],
        mode="lines",
        name="策略權益 / Strategy Equity",
        line=dict(color="#00D9FF", width=2.5),
    ))
    
    if buy_hold_df is not None and not buy_hold_df.empty:
        fig.add_trace(go.Scatter(
            x=buy_hold_df.index,
            y=buy_hold_df["BuyHoldEquity"],
            mode="lines",
            name="買入持有 / Buy & Hold",
            line=dict(color="#6B7280", width=1.5, dash="dot"),
            opacity=0.7,
        ))
    
    # Normalize equity index to naive days for marker alignment (handles tz-aware yfinance data)
    equity_index_naive = pd.DatetimeIndex([_to_naive_day(d) for d in equity_df.index])
    
    # Add economic event markers (L1 display layer - does not affect L0 backtest)
    if event_markers is not None and not event_markers.empty:
        # Group by event type for color coding
        event_colors = {
            "CPI": "#F59E0B",
            "NFP": "#8B5CF6",
            "FOMC": "#EC4899",
            "Unemployment": "#3B82F6",
            "GDP": "#10B981",
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
        title=dict(text="權益曲線 / Equity Curve", font=dict(size=16, weight=600)),
        xaxis_title="日期 / Date",
        yaxis_title="權益 / Equity ($)",
        hovermode="x unified",
        template="plotly_dark",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(
            showgrid=True,
            gridwidth=0.5,
            gridcolor="rgba(128,128,128,0.2)",
        ),
        yaxis=dict(
            showgrid=True,
            gridwidth=0.5,
            gridcolor="rgba(128,128,128,0.2)",
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor="rgba(0,0,0,0)",
        ),
        margin=dict(l=50, r=20, t=60, b=50),
    )
    return fig


def plot_drawdown(equity_df: pd.DataFrame) -> go.Figure:
    """Create drawdown chart."""
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
        line=dict(color="#EF4444", width=2),
        fillcolor="rgba(239, 68, 68, 0.2)",
    ))
    fig.update_layout(
        title=dict(text="回撤圖 / Drawdown", font=dict(size=16, weight=600)),
        xaxis_title="日期 / Date",
        yaxis_title="回撤 / Drawdown (%)",
        hovermode="x unified",
        template="plotly_dark",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(
            showgrid=True,
            gridwidth=0.5,
            gridcolor="rgba(128,128,128,0.2)",
        ),
        yaxis=dict(
            showgrid=True,
            gridwidth=0.5,
            gridcolor="rgba(128,128,128,0.2)",
        ),
        margin=dict(l=50, r=20, t=60, b=50),
    )
    return fig


def main():
    st.title("演算法交易回測系統")
    st.caption("Algorithmic Trading Backtesting System")
    
    with st.sidebar:
        st.header("設定面板 / Settings")
        
        strategy_type = st.selectbox(
            "策略 / Strategy",
            ["SMA Crossover", "RSI Mean Reversion"],
        )
        
        st.subheader("數據來源 / Data Source")
        data_source = st.radio(
            "類型 / Type",
            ["Yahoo Finance", "範例數據 / Sample CSV", "上傳 CSV / Upload CSV"],
            label_visibility="collapsed",
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
                st.caption(description)
            
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
            st.info(
                "⚠️ 範例數據僅涵蓋 2020-01-02 至 2020-06-01（約 104 個交易日，COVID-19 熊市期間）。"
                "此期間不足以充分測試 SMA 50/200 策略（需要 200+ 個交易日）。"
            )
        
        else:  # Upload CSV
            uploaded_file = st.file_uploader(
                "上傳 OHLCV CSV 文件 / Upload OHLCV CSV",
                type=["csv"],
            )
        
        st.subheader("資金設定 / Capital")
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
        
        st.subheader("策略參數 / Strategy Parameters")
        
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
        
        with st.expander("研究層 / Research Layers", expanded=False):
            st.caption("L1 研究層：顯示與對齊 / L1 Research: Display & Alignment")
            
            st.markdown("**經濟日曆 / Economic Calendar**")
            show_calendar = st.checkbox(
                "顯示經濟公佈日 / Show Economic Releases",
                value=True,
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
                )
                
                st.markdown("**研究過濾（可選）/ Research Filter**")
                st.caption("此過濾僅用於研究對比 / For research comparison only")
                
                calendar_filter_enabled = st.checkbox(
                    "啟用避開公佈日過濾 / Enable Avoidance Filter",
                    value=False,
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
            st.markdown("**新聞研究 / News Research**")
            show_news = st.checkbox(
                "顯示新聞（研究）/ Show News",
                value=False,
            )
            
            if show_news:
                st.caption("⚠️ 研究用途、非完整歷史 / For research only")
            
            st.markdown("---")
            st.markdown("**財報時間線 / Earnings Timeline**")
            show_earnings = st.checkbox(
                "顯示財報（研究）/ Show Earnings",
                value=False,
            )
        
        earnings_filter_enabled = False
        earnings_filter_days_before = 0
        earnings_filter_days_after = 0
        
        if show_earnings:
            st.caption("單一股票顯示財報日期 / Single stocks show earnings dates")
            
            st.markdown("**研究過濾（可選）/ Research Filter**")
            st.caption("此過濾僅用於研究對比 / For research comparison only")
            
            earnings_filter_enabled = st.checkbox(
                "啟用避開財報日過濾 / Enable Avoidance Filter",
                value=False,
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
        
        run_backtest = st.button("運行回測 / Run Backtest", type="primary", use_container_width=True)
    
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
                if strategy_type == "SMA Crossover":
                    strategy = SMACrossover(
                        fast_period=int(fast_period),
                        slow_period=int(slow_period),
                    )
                else:
                    strategy = RSIMeanReversion(
                        period=int(rsi_period),
                        oversold=rsi_oversold,
                        overbought=rsi_overbought,
                    )
                
                engine = BacktestEngine(
                    initial_capital=initial_capital,
                    commission=commission,
                    slippage=slippage,
                    position_size_type="fixed_fraction",
                    position_size_value=position_size,
                )
                
                equity_curve = engine.run(strategy, data)
                
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
                    st.caption(f"經濟事件標記：{len(calendar_events)} 個 / Economic events: {len(calendar_events)}")
                elif show_calendar:
                    st.caption("⚠️ 經濟日曆數據未載入 / Economic calendar data not loaded")
            
            # Display news status if enabled
            if show_news:
                if news_loaded and news_items is not None and not news_items.empty:
                    source_label = "示範 CSV" if news_source == "sample_csv" else "yfinance"
                    st.caption(f"新聞：{len(news_items)} 則（來源：{source_label}）/ News: {len(news_items)} items (source: {source_label})")
                else:
                    st.caption("⚠️ 新聞數據未載入 / News data not loaded")
            
            # Display earnings status if enabled
            if show_earnings:
                if earnings_loaded and earnings_events is not None and not earnings_events.empty:
                    if earnings_source == "sample_csv":
                        source_label = "示範 CSV"
                    elif earnings_source == "yfinance":
                        source_label = "yfinance"
                    else:
                        source_label = "無 / None"
                    st.caption(f"財報事件：{len(earnings_events)} 個（來源：{source_label}）/ Earnings: {len(earnings_events)} events (source: {source_label})")
                else:
                    st.caption("⚠️ 財報數據未載入 / Earnings data not loaded")
            
            # KPI Metric Strip at top
            st.markdown("### 績效摘要 / Performance Summary")
            
            def format_metric(value, fmt=".2f", suffix=""):
                """Format metric safely, handling NaN/inf values."""
                if pd.isna(value) or not np.isfinite(value):
                    return "N/A"
                return f"{value:{fmt}}{suffix}"
            
            def format_pct_with_color(value, inverse=False):
                """Format percentage with color coding."""
                if pd.isna(value) or not np.isfinite(value):
                    return "N/A", None
                color = "inverse" if inverse else "normal"
                sign = "+" if value > 0 else ""
                return f"{sign}{value:.2f}%", color
            
            # Top row: Key metrics
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                total_ret = metrics.get('total_return_pct', float('nan'))
                st.metric(
                    "總回報 / Total Return",
                    format_metric(total_ret, suffix="%"),
                )
            with col2:
                cagr = metrics.get('cagr_pct', float('nan'))
                st.metric(
                    "年化報酬 / CAGR",
                    format_metric(cagr, suffix="%"),
                )
            with col3:
                max_dd = metrics.get('max_drawdown_pct', float('nan'))
                st.metric(
                    "最大回撤 / Max Drawdown",
                    format_metric(max_dd, suffix="%"),
                )
            with col4:
                sharpe = metrics.get('sharpe_ratio', float('nan'))
                st.metric(
                    "夏普比率 / Sharpe",
                    format_metric(sharpe),
                )
            with col5:
                win_rate = metrics.get('win_rate_pct', float('nan'))
                st.metric(
                    "勝率 / Win Rate",
                    format_metric(win_rate, fmt=".1f", suffix="%"),
                )
            
            # Second row: Capital and trade stats
            col6, col7, col8, col9, col10 = st.columns(5)
            with col6:
                st.metric(
                    "初始資金 / Initial",
                    f"${metrics.get('initial_capital', 0):,.0f}",
                )
            with col7:
                final_eq = metrics.get('final_equity', float('nan'))
                final_eq_str = "N/A" if pd.isna(final_eq) or not np.isfinite(final_eq) else f"${final_eq:,.0f}"
                st.metric(
                    "最終權益 / Final",
                    final_eq_str,
                )
            with col8:
                st.metric(
                    "買入持有回報 / Buy & Hold",
                    f"{metrics['buy_hold_return_pct']:.2f}%",
                )
            with col9:
                st.metric(
                    "交易次數 / Trades",
                    f"{metrics.get('trade_count', 0)}",
                )
            with col10:
                bh_final = metrics.get('buy_hold_final', float('nan'))
                bh_str = "N/A" if pd.isna(bh_final) or not np.isfinite(bh_final) else f"${bh_final:,.0f}"
                st.metric(
                    "買入持有最終 / B&H Final",
                    bh_str,
                )
            
            # Educational note
            with st.expander("教育性說明 / Educational Note", expanded=False):
                st.info(
                    "策略回報為正不代表策略有效——需要比較「買入持有」基準。"
                    "這些策略僅供教育和研究使用，不構成投資建議。"
                    "過去績效不代表未來表現。"
                    "\n\n"
                    "A positive strategy return does not mean the strategy is effective—you must compare against "
                    "the buy-and-hold benchmark. These strategies are for educational and research purposes only "
                    "and do not constitute investment advice. Past performance does not guarantee future results."
                )
            
            # Charts section
            st.markdown("### 圖表 / Charts")
            
            tab1, tab2 = st.tabs(["權益曲線 / Equity Curve", "回撤圖 / Drawdown"])
            
            with tab1:
                # Pass calendar events and earnings to chart (L1 display only - does not affect L0 backtest)
                chart_events = calendar_events if (show_calendar and calendar_loaded) else None
                chart_earnings = earnings_events if (show_earnings and earnings_loaded) else None
                st.plotly_chart(
                    plot_equity_curve(equity_curve, buy_hold_curve, event_markers=chart_events, earnings_markers=chart_earnings),
                    use_container_width=True
                )
            
            with tab2:
                st.plotly_chart(plot_drawdown(equity_curve), use_container_width=True)
            
            # Details sections in expanders
            # Economic events table (L1 display)
            if show_calendar and calendar_loaded and calendar_events is not None and not calendar_events.empty:
                with st.expander("經濟事件列表 / Economic Events List", expanded=False):
                    st.dataframe(
                        calendar_events.style.format({"Date": lambda x: x.strftime("%Y-%m-%d")}),
                        use_container_width=True,
                    )
                    st.caption(
                        "時區：美東時間｜資料來源：靜態 CSV / Timezone: US Eastern | Data source: Static CSV"
                    )
            
            # News panel (L1 display)
            if show_news and news_loaded and news_items is not None and not news_items.empty:
                with st.expander("新聞列表 / News Headlines", expanded=False):
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
                        f"⚠️ 研究用途、非完整歷史（來源：{news_source}）/ For research only (source: {news_source})"
                    )
            
            # Earnings events table (L1 display)
            if show_earnings and earnings_loaded and earnings_events is not None and not earnings_events.empty:
                with st.expander("財報事件列表 / Earnings Events List", expanded=False):
                    earnings_display = earnings_events[["Date", "Event", "Symbol"]].copy()
                    earnings_display["Date"] = earnings_display["Date"].dt.strftime("%Y-%m-%d")
                    
                    st.dataframe(
                        earnings_display,
                        use_container_width=True,
                        hide_index=True,
                    )
                    st.caption(
                        f"⚠️ 研究用途、非完整歷史（來源：{earnings_source}）/ For research only (source: {earnings_source})"
                    )
                    
                    # CSV export option
                    if st.button("匯出財報事件 CSV / Export Earnings CSV"):
                        csv = earnings_events.to_csv(index=False)
                        st.download_button(
                            label="下載 CSV / Download CSV",
                            data=csv,
                            file_name=f"earnings_events_{symbol}_{data.index.min().strftime('%Y%m%d')}_{data.index.max().strftime('%Y%m%d')}.csv",
                            mime="text/csv",
                        )
            
            # Research filter comparison (opt-in only, shows side-by-side)
            if show_calendar and calendar_loaded and calendar_filter_enabled and calendar_events is not None:
                with st.expander("研究過濾對比 / Research Filter Comparison", expanded=False):
                    st.warning(
                        "⚠️ **研究過濾警告 / Research Filter Notice**\n\n"
                        "此過濾僅用於研究目的，比較避開經濟數據發布日的績效差異。主回測結果保持不變。\n\n"
                        "This filter is for research purposes only. Main backtest results remain unchanged."
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
                    
                    st.markdown("**對比摘要 / Comparison Summary**")
                    col_left, col_right = st.columns(2)
                    
                    with col_left:
                        st.markdown("**完整回測 / Full Backtest**")
                        st.metric("交易次數 / Trades", metrics.get('trade_count', 0))
                        st.metric("總回報 / Return", f"{metrics.get('total_return_pct', 0):.2f}%")
                        st.metric("勝率 / Win Rate", f"{metrics.get('win_rate_pct', 0):.1f}%")
                    
                    with col_right:
                        st.markdown(f"**過濾後（避開 ±{calendar_filter_days_before}/{calendar_filter_days_after} 日）/ Filtered**")
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
                    
                    st.caption(
                        "對比完整回測與過濾後結果，可研究經濟數據發布對策略績效的影響。\n\n"
                        "Compare full vs. filtered results to research the impact of economic releases."
                    )
            
            # Earnings research filter comparison (opt-in only)
            if show_earnings and earnings_loaded and earnings_filter_enabled and earnings_events is not None:
                with st.expander("財報過濾對比 / Earnings Filter Comparison", expanded=False):
                    st.warning(
                        "⚠️ **研究過濾警告 / Research Filter Notice**\n\n"
                        "此過濾僅用於研究目的，比較避開財報發布日的績效差異。主回測結果保持不變。\n\n"
                        "This filter is for research purposes only. Main backtest results remain unchanged."
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
                    
                    st.markdown("**對比摘要 / Comparison Summary**")
                    col_left, col_right = st.columns(2)
                    
                    with col_left:
                        st.markdown("**完整回測 / Full Backtest**")
                        st.metric("交易次數 / Trades", metrics.get('trade_count', 0))
                        st.metric("總回報 / Return", f"{metrics.get('total_return_pct', 0):.2f}%")
                        st.metric("勝率 / Win Rate", f"{metrics.get('win_rate_pct', 0):.1f}%")
                    
                    with col_right:
                        st.markdown(f"**過濾後（避開財報 ±{earnings_filter_days_before}/{earnings_filter_days_after} 日）/ Filtered**")
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
                    
                    st.caption(
                        "對比完整回測與過濾後結果，可研究財報發布對策略績效的影響。\n\n"
                        "Compare full vs. filtered results to research the impact of earnings releases."
                    )
            
            # Trade details
            st.markdown("### 交易明細 / Trade Details")
            
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
                    label="下載交易記錄 / Download Trades",
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
        st.info("請在左側設定參數並點擊「運行回測」按鈕開始\n\nPlease configure parameters in the sidebar and click 'Run Backtest'")
        
        st.markdown("### 快速開始 / Quick Start")
        st.markdown("""
        **預設設定已可運行：**
        1. 數據來源：Yahoo Finance（SPY，2018-01-01 至今）
        2. 策略：SMA 交叉（快線 20 / 慢線 50）
        3. 點擊「運行回測」按鈕
        
        **Default settings are ready to run:**
        1. Data source: Yahoo Finance (SPY, 2018-01-01 to today)
        2. Strategy: SMA Crossover (fast 20 / slow 50)
        3. Click 'Run Backtest' button
        """)


if __name__ == "__main__":
    main()
