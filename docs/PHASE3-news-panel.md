# Phase 3：新聞研究面板

**階段狀態：已完成 ✅**

本文件說明 Phase 3 新聞研究面板功能的實現方式、數據來源、情緒分析、限制與 Phase 0 合規性。

---

## 1. 功能概述

Phase 3 加入**新聞研究面板**作為 L1 研究層疊加，提供：

1. **新聞列表顯示**：回測期間內相關的新聞標題列表
2. **簡單情緒標籤**：基於關鍵字的啟發式情緒分類（正面、負面、中性）
3. **符號過濾**：針對特定股票代號（如 SPY）的新聞，包含指數關鍵字匹配
4. **研究用途說明**：清楚標示數據非完整歷史記錄

### 核心原則（Phase 0 合規）

| 原則 | 說明 |
|------|------|
| **L1 層級** | 新聞面板為研究層（L1），**不修改** L0 回測引擎或策略邏輯 |
| **預設行為** | 預設為「關閉」，開啟後僅顯示新聞列表 |
| **不影響訊號** | 情緒標籤僅供參考顯示，**不會**輸入策略計算 |
| **優雅降級** | 若新聞數據載入失敗，顯示提示但不影響回測運行 |
| **無需 API Key** | Streamlit Cloud 可直接運行，不需要付費 API 金鑰 |

---

## 2. 數據來源

### 2.1 主要來源：示範 CSV 文件

採用**靜態示範 CSV 文件**作為主要數據源：

- **路徑**：`data/news_sample.csv`
- **涵蓋期間**：2018-01-01 至 2024-12-31（主要市場事件）
- **符號涵蓋**：SPY、QQQ、DIA 等主流 ETF
- **事件類型**：
  - 市場重大事件（如 2020 COVID-19 暴跌、2022 熊市）
  - 聯準會政策新聞
  - 科技股/指數相關新聞
  - 地緣政治事件

### 2.2 數據格式

```csv
Date,Headline,Symbol,Sentiment
2020-03-12,S&P 500 Plunges 10% in Worst Day Since 1987,SPY,Negative
2020-03-23,Fed Announces Unlimited QE to Support Economy,SPY,Positive
2024-09-18,Fed Cuts Rates by Half Point,SPY,Positive
```

**必要欄位**：
- `Date`：新聞日期（YYYY-MM-DD）
- `Headline`：新聞標題
- `Symbol`：相關符號（SPY、QQQ、S&P 500 等）
- `Sentiment`：情緒標籤（Positive / Negative / Neutral）

### 2.3 次要來源：yfinance（可選）

系統會嘗試從 yfinance 獲取新聞，但：

- **涵蓋範圍有限**：yfinance 新聞通常只有近期數據
- **不可靠**：可能無法獲取或返回空結果
- **自動降級**：若 yfinance 失敗，自動使用示範 CSV

### 2.4 為何選擇示範 CSV？

| 優勢 | 說明 |
|------|------|
| **免費** | 無需 API key，Streamlit Community Cloud 可直接運行 |
| **可重現** | 固定數據，回測結果可完全重現 |
| **透明** | 數據來源清晰，用戶可檢視與編輯 |
| **穩定** | 不依賴外部 API 可用性 |
| **教育性** | 涵蓋重要歷史事件，適合學習與研究 |

---

## 3. 情緒分析

### 3.1 簡單啟發式方法

新聞情緒採用**關鍵字匹配**的簡單啟發式分類：

**正面關鍵字**（部分示例）：
- soar, surge, gain, rally, rise, climb
- beat, exceed, record, high, jump, boost
- strong, better, growth, profit, upgrade
- optimistic, positive, breakthrough, success

**負面關鍵字**（部分示例）：
- fall, drop, plunge, decline, crash, sink
- miss, low, tumble, slide, weak, worse
- downgrade, pessimistic, negative, concern
- fail, cut, layoff, lawsuit, crisis, recession

**中性**：
- 正負關鍵字數量相同，或無明顯傾向

### 3.2 限制說明

- **僅供參考**：這是基本的啟發式分類，不是專業 NLP 模型
- **不用於交易**：情緒標籤**不會**輸入策略邏輯（L1 研究層）
- **可能不準確**：簡單關鍵字無法理解上下文或諷刺
- **教育目的**：主要用於示範和研究，不應依賴用於實際交易決策

### 3.3 顯示方式

在 UI 中以表情符號標示：
- 🟢 Positive（正面）
- 🔴 Negative（負面）
- ⚪ Neutral（中性）

---

## 4. 使用說明

### 4.1 UI 控制（Streamlit 側欄）

```
📰 新聞研究 / News Research
L1 研究層：顯示與對齊 / L1 Research: Display & Alignment

□ 顯示新聞（研究）/ Show News (Research)
    顯示回測期間的新聞標題（僅供研究參考，不影響回測結果）

⚠️ 研究用途、非完整歷史 / For research only, not comprehensive historical coverage
```

- **預設狀態**：關閉
- **開啟後**：在回測完成後顯示新聞列表摺疊面板

### 4.2 新聞列表顯示

在主要內容區域的「📰 新聞列表 / News Headlines」摺疊面板中顯示：

| 日期 | 標題 | 情緒 |
|------|------|------|
| 2020-03-12 | S&P 500 Plunges 10% in Worst Day Since 1987 | 🔴 Negative |
| 2020-03-23 | Fed Announces Unlimited QE to Support Economy | 🟢 Positive |
| 2024-09-18 | Fed Cuts Rates by Half Point | 🟢 Positive |

### 4.3 符號過濾與關鍵字匹配

系統會自動過濾與回測符號相關的新聞：

- **直接匹配**：符號為 "SPY" 時，顯示 Symbol = "SPY" 的新聞
- **關鍵字匹配**：也會顯示相關關鍵字（如 "S&P 500"、"SP500"）

**支援的指數關鍵字映射**：
```python
{
    "SPY": ["SPY", "S&P", "S&P 500", "SP500"],
    "QQQ": ["QQQ", "NASDAQ", "NASDAQ 100", "NASDAQ-100"],
    "DIA": ["DIA", "DOW", "DOW JONES", "DJIA"],
    "IWM": ["IWM", "RUSSELL", "RUSSELL 2000"],
}
```

---

## 5. 技術實現

### 5.1 模組架構

```
backtester/
├── news.py                    # 新聞模組（新增）
│   ├── NewsPanel              # 主要類別
│   ├── compute_simple_sentiment  # 情緒計算
│   └── try_fetch_yfinance_news   # yfinance 獲取（可選）
│
data/
└── news_sample.csv            # 示範新聞數據（新增）

tests/
└── test_news.py               # 單元測試（新增）
```

### 5.2 NewsPanel 類別

```python
class NewsPanel:
    def __init__(self, sample_csv_path: Optional[str] = None)
    def load(self, symbol=None, start_date=None, end_date=None, prefer_yfinance=False) -> bool
    def load_sample() -> bool
    def load_yfinance(symbol, start_date, end_date) -> bool
    def is_loaded() -> bool
    def get_data_source() -> str  # "sample_csv", "yfinance", or "none"
    def filter_by_date_range(start_date, end_date, symbol=None) -> pd.DataFrame
    def get_news_by_date(date) -> pd.DataFrame
```

### 5.3 Streamlit 整合

```python
# 載入新聞（若啟用）
if show_news:
    news_panel = NewsPanel()
    if news_panel.load(symbol=symbol, start_date=data.index.min(), end_date=data.index.max()):
        news_items = news_panel.filter_by_date_range(
            start_date=data.index.min(),
            end_date=data.index.max(),
            symbol=symbol,
        )
```

### 5.4 時區處理

- **儲存格式**：新聞日期以 timezone-naive 格式儲存
- **對齊邏輯**：使用 `_to_naive_day()` 函數與 OHLCV 索引對齊
- **比較一致性**：確保日期比較不會因時區差異產生 TypeError

---

## 6. 測試

### 6.1 測試涵蓋範圍

```python
tests/test_news.py
├── TestNewsPanelBasics        # 基本載入與過濾
├── TestSentimentComputation   # 情緒分類測試
├── TestTimezoneHandling       # 時區處理
├── TestPhase0Compliance       # Phase 0 合規性（核心）
├── TestDataSourceFallback     # 數據源降級
└── TestEdgeCases              # 邊界情況
```

### 6.2 Phase 0 合規性測試

**核心測試**：`test_news_panel_does_not_affect_backtest_results`

驗證：
1. 執行基準回測（未載入新聞）
2. 載入新聞面板
3. 執行相同回測（新聞已載入但僅顯示）
4. 驗證兩次回測結果**完全相同**：
   - Equity curve 一致
   - 交易次數相同
   - 所有績效指標一致（總回報、夏普比率、最大回撤等）

### 6.3 運行測試

```bash
# 運行所有新聞模組測試
pytest tests/test_news.py -v

# 只運行 Phase 0 合規性測試
pytest tests/test_news.py::TestPhase0Compliance -v

# 測試情緒計算
pytest tests/test_news.py::TestSentimentComputation -v
```

---

## 7. 限制與注意事項

### 7.1 數據限制

| 限制 | 說明 |
|------|------|
| **非完整歷史** | 示範 CSV 僅涵蓋重要市場事件，不是全部新聞 |
| **選擇性偏差** | 人工挑選的新聞可能有偏差 |
| **符號涵蓋** | 主要針對 SPY、QQQ 等主流 ETF |
| **yfinance 不可靠** | yfinance 新聞涵蓋範圍有限且不穩定 |

### 7.2 功能限制

| 限制 | 說明 |
|------|------|
| **僅顯示** | L1 研究層，不影響交易訊號 |
| **簡單情緒** | 關鍵字匹配，不是 NLP 模型 |
| **無全文** | 僅標題，無新聞內容 |
| **無來源連結** | 示範數據無原始新聞連結 |

### 7.3 不適用場景

❌ **不應使用新聞面板的場景**：
- 依賴情緒標籤做實際交易決策
- 假設涵蓋了所有重要新聞
- 將其視為專業新聞分析工具
- 需要新聞全文或深度分析
- 需要即時新聞推送

✅ **適合使用的場景**：
- 回顧歷史市場事件
- 研究新聞與價格走勢的時間關聯
- 教育與學習市場歷史
- 回測期間的情境參考
- 開發更複雜新聞功能的原型

---

## 8. Phase 0 合規性確認

### 8.1 合規檢查清單

- [x] **不修改 L0 引擎**：新聞面板僅載入與顯示，不影響 `BacktestEngine`
- [x] **不修改策略**：情緒標籤不輸入 `Strategy.on_bar()`
- [x] **不修改 OHLCV**：新聞數據獨立，不改變價格數據
- [x] **預設關閉或不影響**：預設為關閉，開啟後僅顯示
- [x] **優雅降級**：數據載入失敗時不影響回測運行
- [x] **測試驗證**：`test_news_panel_does_not_affect_backtest_results` 通過

### 8.2 成功標準

用同一組參數跑固定標的（SPY / sample CSV）：

1. **關閉新聞面板** → equity curve 與核心 metrics 與加功能前一致 ✅
2. **開啟新聞面板（僅顯示）** → equity curve 與 metrics 仍一致 ✅
3. **數據載入失敗** → 回測正常完成，僅提示降級 ✅

---

## 9. 未來擴展（超出 Phase 3 範圍）

以下功能**不在** Phase 3 中實現，留待未來可能的階段：

### Phase 4（可能）：商蹤／財報時間線
- 財報發布日期標記
- 指數成分股財報聚合（需降級說明）
- 財報季節性分析

### Phase 5（可能）：事件驅動策略（L2）
- **用戶 opt-in**：明確啟用才可改訊號
- 避開新聞發布前後 N 天
- 情緒驅動的持倉調整
- **需對照測試**：顯示事件規則開關的績效對比

### 進階新聞功能（未來）
- 整合付費新聞 API（可選，環境變數）
- NLP 情緒模型（需額外依賴）
- 新聞全文提取
- 多語言新聞支援
- 即時新聞推送

---

## 10. 參考文件

- [Phase 0 產品邊界](PHASE0-boundaries.md) - 核心合約與分層模型
- [Phase 2 經濟日曆](PHASE2-economic-calendar.md) - L1 研究層實現參考
- [README](../README.md) - 主要專案說明

---

## 11. 變更記錄

| 日期 | 變更 |
|------|------|
| 2024-12-XX | Phase 3 完成：新聞研究面板（L1 顯示層） |

---

## 12. 常見問題

**Q: 為什麼預設關閉新聞面板？**  
A: 因為示範數據非完整歷史，且主要用於教育與研究。預設關閉避免誤導使用者以為有完整新聞覆蓋。

**Q: 情緒標籤準確嗎？**  
A: 這是簡單的關鍵字匹配，僅供參考。不應依賴它做實際交易決策。

**Q: 可以加入自己的新聞嗎？**  
A: 可以！編輯 `data/news_sample.csv`，加入符合格式的新聞即可。

**Q: yfinance 新聞為什麼經常失敗？**  
A: yfinance 新聞 API 涵蓋範圍有限且不穩定。系統會自動降級到示範 CSV。

**Q: 新聞會影響回測結果嗎？**  
A: 不會。這是 L1 研究層，僅顯示，不修改 L0 回測引擎或策略訊號。測試驗證了這一點。

**Q: 如何加入更多符號的新聞？**  
A: 編輯 `data/news_sample.csv`，加入新符號的新聞。也可以在 `backtester/news.py` 中擴展 `index_keywords` 映射。

---

**Phase 3 完成標記：**
- [x] 新聞模組實現（`backtester/news.py`）
- [x] 示範數據（`data/news_sample.csv`）
- [x] Streamlit 整合
- [x] 單元測試（`tests/test_news.py`）
- [x] Phase 0 合規性驗證
- [x] 文件完成（本文件）
- [x] README 更新
