# Backtester - 演算法交易回測系統

一個乾淨、可運行的 Python 演算法交易回測系統，讓交易者能夠定義策略、在歷史 OHLCV 數據上運行並獲得清晰的績效報告。

## 功能特點

- 📊 **數據層**：支援從 CSV 加載數據或透過 yfinance 獲取免費歷史數據
- 🎯 **策略 API**：簡單的基礎策略類，易於擴展
- 🔄 **回測引擎**：支援多頭/平倉策略，含佣金和滑點模擬
- 📈 **績效指標**：總回報、CAGR、最大回撤、夏普比率、勝率等
- 💻 **命令行界面**：開箱即用的 CLI 工具
- ✅ **單元測試**：確保核心功能正確性

## 路線圖 / Roadmap

後續會按階段加入指數快捷、經濟日曆、新聞與商蹤／財報等**研究層**。加功能前已鎖定產品邊界（回測只信 OHLCV；研究層預設只顯示、唔改訊號）：見 [docs/PHASE0-boundaries.md](docs/PHASE0-boundaries.md)。

**已完成階段 / Completed Phases**：
- ✅ **Phase 0**: 產品邊界與數據原則 / Product boundaries and data principles
- ✅ **Phase 1**: 指數／ETF 快捷清單 / Index/ETF presets
- ✅ **Phase 2**: 經濟日曆疊加層 / Economic calendar overlay ([docs](docs/PHASE2-economic-calendar.md))
- ✅ **Phase 3**: 新聞研究面板 / News research panel ([docs](docs/PHASE3-news-panel.md))
- ✅ **Phase 4**: 財報／商蹤時間線 / Earnings timeline ([docs](docs/PHASE4-earnings-timeline.md))

### 已完成階段

- **Phase 0**：產品邊界與數據原則 → [docs/PHASE0-boundaries.md](docs/PHASE0-boundaries.md)
- **Phase 2**：經濟日曆疊加層 ✅ → [docs/PHASE2-economic-calendar.md](docs/PHASE2-economic-calendar.md)
  - 美國宏觀經濟數據發布日標記（CPI、NFP、FOMC、GDP）
  - 圖表疊加顯示與事件列表
  - 可選研究過濾：對比「避開公佈日±N天」的績效差異
  - Phase 0 合規：L1 研究層，不修改 L0 回測引擎
- **Phase 3**：新聞研究面板 ✅ → [docs/PHASE3-news-panel.md](docs/PHASE3-news-panel.md)
  - 回測期間新聞標題列表顯示
  - 簡單啟發式情緒標籤（正面、負面、中性）
  - 符號過濾與指數關鍵字匹配（如 SPY → S&P 500）
  - 示範 CSV + yfinance 降級，無需 API key
  - Phase 0 合規：L1 研究層，情緒標籤不影響交易訊號

## 內建策略

1. **SMA 交叉策略**：快慢均線交叉信號
2. **RSI 均值回歸策略**：基於超買超賣區間的反轉交易

## 快速開始

### 安裝

```bash
# 克隆儲存庫
git clone <repo-url>
cd backtester

# 安裝依賴
pip install -r requirements.txt

# 或使用開發模式安裝
pip install -e .
```

### 運行示例

使用內建範例數據運行 SMA 策略：

```bash
python -m backtester --strategy sma --csv data/sample/SPY_sample.csv
```

從 Yahoo Finance 獲取數據並運行回測：

```bash
python -m backtester --strategy sma --symbol SPY --start 2020-01-01 --end 2023-12-31
```

運行 RSI 策略：

```bash
python -m backtester --strategy rsi --symbol AAPL --start 2021-01-01
```

### CLI 參數說明

```
--strategy        策略類型 (sma 或 rsi)，預設：sma
--symbol          股票代號，預設：SPY
--start           開始日期 (YYYY-MM-DD)，預設：2020-01-01
--end             結束日期 (YYYY-MM-DD)，預設：最新
--csv             使用 CSV 文件而非 Yahoo Finance
--capital         初始資金，預設：100,000
--commission      佣金率，預設：0.001 (0.1%)
--slippage        滑點率，預設：0.0005 (0.05%)
--position-size   倉位大小（股權的比例），預設：0.95

# SMA 策略參數
--fast-period     快線週期，預設：50
--slow-period     慢線週期，預設：200

# RSI 策略參數
--rsi-period      RSI 週期，預設：14
--rsi-oversold    超賣閾值，預設：30
--rsi-overbought  超買閾值，預設：70

--output-dir      輸出目錄，預設：outputs/
```

## 創建自定義策略

在 `backtester/strategies/` 目錄下創建新的策略文件：

```python
from backtester.strategy import Strategy, Signal
import pandas as pd

class MyStrategy(Strategy):
    """你的策略描述"""
    
    def __init__(self, param1: int = 10):
        super().__init__(name="MyStrategy")
        self.param1 = param1
    
    def setup(self, data: pd.DataFrame) -> None:
        """在回測開始前計算指標"""
        super().setup(data)
        # 計算你的指標
        self.indicator = data["Close"].rolling(self.param1).mean()
    
    def on_bar(self, index: int, row: pd.Series) -> Signal:
        """為每個 bar 生成交易信號"""
        if index < self.param1:
            return "HOLD"
        
        # 你的策略邏輯
        if self.indicator.iloc[index] > row["Close"]:
            return "BUY"
        elif self.indicator.iloc[index] < row["Close"]:
            return "SELL"
        
        return "HOLD"
```

然後在 CLI 中註冊並使用你的策略。

## 項目結構

```
backtester/
├── backtester/          # 主要套件
│   ├── __init__.py
│   ├── data.py          # 數據加載器
│   ├── strategy.py      # 策略基礎類
│   ├── engine.py        # 回測引擎
│   ├── metrics.py       # 績效指標
│   ├── cli.py           # 命令行界面
│   └── strategies/      # 策略實現
│       ├── sma_crossover.py
│       └── rsi_mean_reversion.py
├── data/
│   ├── sample/          # 範例數據
│   └── cache/           # 下載數據緩存
├── outputs/             # 回測結果輸出
├── tests/               # 單元測試
├── pyproject.toml       # 項目配置
├── requirements.txt     # Python 依賴
└── README.md
```

## 運行測試 / Running Tests

系統包含完整的測試套件，涵蓋單元測試、端到端測試和壓力測試。

### 運行所有測試（預設）

```bash
# 運行單元測試和端到端測試（排除壓力測試）
pytest

# 或更詳細的輸出
pytest -v
```

### 按類別運行測試

```bash
# 只運行單元測試（最快）
pytest tests/test_engine.py tests/test_metrics.py tests/test_strategies.py tests/test_data.py -v

# 只運行端到端測試
pytest -m e2e -v

# 只運行壓力/性能測試（較慢，~30秒）
pytest -m stress -v

# 運行所有測試包括壓力測試
pytest -m "" -v
```

### 測試覆蓋範圍

**單元測試** (快速, <1秒):
- `test_engine.py` - 回測引擎核心功能
- `test_metrics.py` - 績效指標計算
- `test_strategies.py` - SMA 和 RSI 策略信號生成
- `test_data.py` - 數據加載器和緩存

**端到端測試** (中等, ~5秒):
- `test_e2e.py` - CLI 命令行介面
- `test_dashboard_integration.py` - 儀表板工作流程

**壓力測試** (較慢, ~30秒):
- `test_stress.py` - 大數據集性能測試（10k-50k 個數據點）
- 參數網格搜索
- 極端市場條件
- 記憶體穩定性

### 測試統計

```bash
# 顯示測試摘要
pytest --collect-only

# 生成覆蓋率報告
pytest --cov=backtester --cov-report=html
```

## 績效指標

回測完成後，系統會輸出以下指標：

- **初始資金**：起始資金量
- **最終權益**：回測結束時的總權益
- **總回報**：總回報百分比
- **CAGR**：年化複合增長率
- **最大回撤**：歷史最大跌幅
- **夏普比率**：風險調整後收益（假設 252 個交易日）
- **交易次數**：執行的交易總數
- **勝率**：盈利交易的百分比
- **平均交易回報**：每筆交易的平均回報

輸出文件保存在 `outputs/` 目錄：
- `equity_curve_*.csv`：權益曲線
- `trades_*.csv`：交易明細

## 數據源

系統支援兩種數據來源：

1. **CSV 文件**：需包含 Date, Open, High, Low, Close, Volume 欄位
2. **Yahoo Finance**：透過 yfinance 自動獲取並緩存數據

支援的代號示例：
- 美股：SPY, AAPL, MSFT, GOOGL
- 加密貨幣：BTC-USD, ETH-USD
- 其他市場：請參考 Yahoo Finance 支援列表

## 限制說明

- 當前版本僅支援多頭/平倉策略（不支援做空）
- 不包含實盤交易功能
- 不需要 API 密鑰即可使用基本功能

## 網頁儀表板 / Web Dashboard

### 啟動儀表板

系統現在包含互動式網頁儀表板，無需使用命令行即可運行回測：

```bash
# 安裝依賴（包含 Streamlit）
pip install -r requirements.txt

# 啟動儀表板
streamlit run streamlit_app.py
```

儀表板將在瀏覽器中自動打開（預設：http://localhost:8501）

### 儀表板功能

- 🎯 **互動式控制面板**：選擇策略、設定參數、選擇數據源
- 🌓 **雙主題支援**：深色交易終端風格（預設）與明亮現代介面，可透過 Settings → Theme 切換
- 📊 **即時圖表**：權益曲線、回撤圖
- 📈 **績效指標**：總回報、CAGR、夏普比率、勝率等
- 📉 **買入持有基準**：與被動投資策略比較
- 📋 **交易明細**：完整的交易記錄表格
- 📥 **下載功能**：匯出交易記錄為 CSV
- 🔄 **多種數據源**：內建範例、Yahoo Finance、上傳 CSV
- ⚡ **快速選股（Phase 1）**：預設常用指數/ETF 快速選擇（美股、板塊、港股/亞洲、債券/商品等）

### 主題切換 / Theme Switching

儀表板預設為深色交易終端風格，適合長時間觀看市場數據。如需切換至明亮主題：

1. 點擊右上角 ⋮ 選單
2. 選擇 Settings
3. 在 Theme 選項中選擇 Light 或 Dark

The dashboard defaults to a dark trading terminal style. To switch to light theme:
1. Click the ⋮ menu in the top-right
2. Select Settings
3. Choose Light or Dark under Theme

### 快速開始（儀表板）

1. 啟動應用程式：`streamlit run streamlit_app.py`
2. 預設已設定為最佳實踐：
   - 數據來源：Yahoo Finance（SPY，2018-01-01 至今）
   - 策略：SMA 交叉（快線 20 / 慢線 50）
3. 點擊「運行回測」按鈕
4. 查看圖表和指標，包括買入持有基準比較

**注意**：內建範例 CSV 僅涵蓋 2020 年初 COVID-19 熊市期間（~104 個交易日），不建議用於測試長期策略（如 SMA 50/200）。

## 雲端部署 / Cloud Deployment

### 方式 1：Streamlit Community Cloud（最簡單）

1. 將儲存庫推送到 GitHub
2. 訪問 [share.streamlit.io](https://share.streamlit.io)
3. 連接你的 GitHub 儲存庫
4. 主文件路徑：`streamlit_app.py`
5. 點擊 Deploy

完全免費，無需信用卡。

### 方式 2：Docker 部署（任何雲端平台）

```bash
# 本地建構和測試
docker build -t backtester-dashboard .
docker run -p 8501:8501 backtester-dashboard

# 訪問 http://localhost:8501
```

#### 部署到 Render

1. 連接你的 Git 儲存庫到 [render.com](https://render.com)
2. 選擇「New Web Service」
3. 環境選擇「Docker」
4. Render 會自動檢測 `Dockerfile` 和 `render.yaml`
5. 部署（免費方案可用）

#### 部署到 Railway

1. 訪問 [railway.app](https://railway.app)
2. 點擊「New Project」→「Deploy from GitHub repo」
3. 選擇儲存庫
4. Railway 會自動檢測 `Dockerfile` 和 `Procfile`
5. 添加環境變數 `PORT=8501`（如需要）
6. 部署

#### 部署到 Fly.io

```bash
# 安裝 Fly CLI
curl -L https://fly.io/install.sh | sh

# 初始化和部署
fly launch
fly deploy
```

### 方式 3：Heroku

```bash
# 安裝 Heroku CLI 並登入
heroku login

# 創建應用程式
heroku create your-backtester-app

# 推送代碼
git push heroku main

# 應用程式會使用 Procfile 自動啟動
```

### Docker 環境變數

Docker 映像支援以下環境變數：

- `PORT`：應用程式監聽端口（預設：8501）
- `STREAMLIT_SERVER_PORT`：Streamlit 伺服器端口
- `STREAMLIT_SERVER_ADDRESS`：綁定地址（預設：0.0.0.0）

### 健康檢查

應用程式在 `/_stcore/health` 路徑提供健康檢查端點，適用於 Docker 和雲端平台的健康監控。

## 技術棧

### 核心
- Python 3.11+
- pandas - 數據處理
- numpy - 數值計算
- yfinance - 獲取歷史數據
- pytest - 單元測試

### 網頁界面
- Streamlit - 互動式儀表板
- Plotly - 圖表繪製

### 部署
- Docker - 容器化
- 支援 Streamlit Cloud、Render、Railway、Heroku、Fly.io

---

# English Section

## Overview

A clean, runnable Python algorithmic-trading backtesting system that lets traders define strategies, run them on historical OHLCV data, and get clear performance reports. Now with an interactive web dashboard!

## Quick Start

### CLI Mode

```bash
# Install dependencies
pip install -r requirements.txt

# Run with sample data
python3 -m backtester --strategy sma --csv data/sample/SPY_sample.csv

# Run with Yahoo Finance data
python3 -m backtester --strategy sma --symbol SPY --start 2020-01-01
```

### Web Dashboard

```bash
# Install dependencies
pip install -r requirements.txt

# Launch dashboard
streamlit run streamlit_app.py
```

Open your browser to http://localhost:8501 and start backtesting with the interactive UI!

## Features

### Interactive Dashboard
- 📊 Real-time charts (equity curve, drawdown)
- 🌓 **Dual theme support**: Dark trading terminal (default) & clean light theme, switchable via Settings → Theme
- 🎯 Visual controls for all parameters
- 📈 Complete performance metrics
- 📉 Buy-and-hold benchmark comparison
- 📋 Trade history table
- 📥 Download results as CSV
- 🔄 Multiple data sources (sample CSV, Yahoo Finance, file upload)
- ⚡ Quick-select shortcuts (Phase 1): Preset common indices/ETFs for faster backtesting

### Theme Switching

The dashboard defaults to a dark trading terminal style for extended market data viewing. To switch themes:

1. Click the ⋮ menu in the top-right corner
2. Select Settings
3. Choose your preferred theme under Theme (Light/Dark)

### Built-in Strategies

1. **SMA Crossover**: Fast/slow moving average crossover
2. **RSI Mean Reversion**: Oversold/overbought reversal trading

## Cloud Deployment

### Streamlit Community Cloud (Easiest)

1. Push repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repo
4. Main file: `streamlit_app.py`
5. Deploy!

Free, no credit card required.

### Docker Deployment

```bash
# Build and run locally
docker build -t backtester-dashboard .
docker run -p 8501:8501 backtester-dashboard
```

Deploy to: Render, Railway, Fly.io, Heroku (see detailed instructions in Traditional Chinese section above).

## Adding Custom Strategies

Extend the `Strategy` base class and implement the `on_bar()` method. See the Traditional Chinese section above for detailed examples.

## Running Tests

The system includes a comprehensive test suite covering unit, end-to-end, and stress tests.

### Run All Tests (Default)

```bash
# Run unit and e2e tests (excludes stress tests)
pytest

# With verbose output
pytest -v
```

### Run by Category

```bash
# Unit tests only (fastest)
pytest tests/test_engine.py tests/test_metrics.py tests/test_strategies.py tests/test_data.py -v

# End-to-end tests only
pytest -m e2e -v

# Stress/performance tests only (slower, ~30s)
pytest -m stress -v

# All tests including stress
pytest -m "" -v
```

### Test Coverage

**Unit Tests** (fast, <1s):
- Engine core functionality
- Metrics calculations
- Strategy signal generation
- Data loading and caching

**E2E Tests** (moderate, ~5s):
- CLI workflows
- Dashboard workflows

**Stress Tests** (slower, ~30s):
- Large dataset performance (10k-50k bars)
- Parameter sweeps
- Extreme market conditions
- Memory stability

## Tech Stack

- **Core**: Python 3.11+, pandas, numpy, yfinance
- **Web UI**: Streamlit, Plotly
- **Deployment**: Docker, supports all major cloud platforms

## License

This project is for educational and research purposes.
