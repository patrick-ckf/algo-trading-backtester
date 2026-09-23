"""
Streamlit Dashboard for Backtesting System
"""

import streamlit as st
import pandas as pd
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


st.set_page_config(
    page_title="演算法交易回測系統",
    page_icon="📈",
    layout="wide",
)


def plot_equity_curve(equity_df: pd.DataFrame, buy_hold_df: Optional[pd.DataFrame] = None) -> go.Figure:
    """Create equity curve chart with optional buy-and-hold benchmark."""
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
    
    fig.update_layout(
        title="權益曲線 / Equity Curve",
        xaxis_title="日期 / Date",
        yaxis_title="權益 / Equity ($)",
        hovermode="x unified",
        template="plotly_white",
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
            symbol = st.text_input("股票代號 / Symbol", value="SPY")
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
            
            st.success("✅ 回測完成 / Backtest complete!")
            
            st.markdown("## 📊 績效指標 / Performance Metrics")
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric(
                    "總回報 / Total Return",
                    f"{metrics['total_return_pct']:.2f}%",
                )
            with col2:
                st.metric(
                    "年化報酬 / CAGR",
                    f"{metrics['cagr_pct']:.2f}%",
                )
            with col3:
                st.metric(
                    "最大回撤 / Max Drawdown",
                    f"{metrics['max_drawdown_pct']:.2f}%",
                )
            with col4:
                st.metric(
                    "夏普比率 / Sharpe",
                    f"{metrics['sharpe_ratio']:.2f}",
                )
            
            col5, col6, col7, col8 = st.columns(4)
            with col5:
                st.metric(
                    "初始資金 / Initial",
                    f"${metrics['initial_capital']:,.0f}",
                )
            with col6:
                st.metric(
                    "最終權益 / Final",
                    f"${metrics['final_equity']:,.0f}",
                )
            with col7:
                st.metric(
                    "交易次數 / Trades",
                    f"{metrics['trade_count']}",
                )
            with col8:
                st.metric(
                    "勝率 / Win Rate",
                    f"{metrics['win_rate_pct']:.1f}%",
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
                st.plotly_chart(plot_equity_curve(equity_curve, buy_hold_curve), use_container_width=True)
            
            with tab2:
                st.plotly_chart(plot_drawdown(equity_curve), use_container_width=True)
            
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
