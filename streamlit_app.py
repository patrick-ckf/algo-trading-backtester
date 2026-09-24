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
from backtester.economic_calendar import EconomicCalendar, calculate_research_metrics
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
                # Find closest equity value
                if event_date in equity_df.index:
                    y_values.append(equity_df.loc[event_date, "Equity"])
                    x_values.append(event_date)
                else:
                    # Find nearest date
                    nearest_idx = equity_df.index.get_indexer([event_date], method="nearest")[0]
                    if 0 <= nearest_idx < len(equity_df):
                        y_values.append(equity_df.iloc[nearest_idx]["Equity"])
                        x_values.append(event_date)
            
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
                # Find closest equity value
                if event_date in equity_df.index:
                    y_values.append(equity_df.loc[event_date, "Equity"])
                    x_values.append(event_date)
                    hover_texts.append(f"<b>{event_date.strftime('%Y-%m-%d')}</b><br>{row['Event']}<br>權益: ${equity_df.loc[event_date, 'Equity']:,.0f}")
                else:
                    # Find nearest date
                    nearest_idx = equity_df.index.get_indexer([event_date], method="nearest")[0]
                    if 0 <= nearest_idx < len(equity_df):
                        y_values.append(equity_df.iloc[nearest_idx]["Equity"])
                        x_values.append(event_date)
                        hover_texts.append(f"<b>{event_date.strftime('%Y-%m-%d')}</b><br>{row['Event']}<br>權益: ${equity_df.iloc[nearest_idx]['Equity']:,.0f}")
            
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
        title="權益曲線 / Equity Curve",
        xaxis_title="日期 / Date",
        yaxis_title="權益 / Equity ($)",
        hovermode="x unified",
        template="plotly_white",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
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
        line=dict(color="#EA2027", width=2),
    ))
    fig.update_layout(
        title="回撤圖 / Drawdown",
        xaxis_title="日期 / Date",
        yaxis_title="回撤 / Drawdown (%)",
        hovermode="x unified",
        template="plotly_white",
    )
    return fig


def main():
    st.title("📈 演算法交易回測系統")
    st.markdown("**Algorithmic Trading Backtesting System**")
    st.markdown("---")
    
    with st.sidebar:
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
            
            st.markdown("---")
            
            st.markdown("## 📈 圖表 / Charts")
            
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
