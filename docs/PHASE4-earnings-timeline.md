# Phase 4：財報／商蹤時間線

**階段狀態：開發中 🚧**

本文件說明 Phase 4 財報／商蹤事件時間線功能的實現方式、數據來源、符號行為、限制與 Phase 0 合規性。

---

## 1. 功能概述

Phase 4 加入**企業財報及重要商業事件時間線**作為 L1 研究層疊加，提供：

1. **圖表標記**：在權益曲線上標記財報發布日期（區別於經濟日曆和新聞標記）
2. **事件列表**：顯示回測期間內的財報事件時間線
3. **研究過濾（可選）**：提供「避開財報日±N天」的過濾功能，用於研究對比
4. **CSV 匯出**：可匯出事件列表供進一步分析

### 核心原則（Phase 0 合規）

| 原則 | 說明 |
|------|------|
| **L1 層級** | 財報時間線為研究層（L1），**不修改** L0 回測引擎或策略邏輯 |
| **預設行為** | 預設為「顯示標記」模式，不影響回測結果 |
| **研究過濾** | 「避開財報日」過濾必須**明確啟用**，並標示為研究用途 |
| **對比展示** | 過濾結果以**次要結果**展示，主回測結果保持可見 |
| **優雅降級** | 若財報數據載入失敗，顯示提示但不影響回測運行 |

---

## 2. 符號行為

Phase 4 對不同類型的標的有不同處理方式：

### 2.1 單一股票（Individual Stocks）

**範例**：AAPL, MSFT, GOOGL, AMZN, TSLA

**行為**：
- ✅ 顯示該股票的財報發布日期
- ✅ 可從 yfinance 嘗試抓取（best-effort）
- ✅ 備用：從示範 CSV 加載（確保離線可運行）
- ✅ 支援研究過濾功能

**數據來源優先級**：
1. 示範 CSV（預設，確保可重現）
2. yfinance earnings_dates（可選，實時但可能不完整）

### 2.2 指數／ETF（Index/ETF Symbols）

**範例**：SPY, QQQ, DIA, IWM, 2800.HK

**行為**：
- ⚠️ **優雅降級**：不提供完整成分股財報日曆
- 📊 顯示相關大型股的樣本財報（若啟用）
- ℹ️ 明確標示「指數不支援完整財報日曆」
- 🔄 備用：顯示示範 CSV 中的相關樣本事件

**原因**：
- 指數包含數十至數百支成分股
- 提供完整成分股財報日曆需付費 API
- 避免誤導：不假裝有完整數據
- Phase 0 原則：免費 API、可重現

---

## 3. 數據來源

### 3.1 示範 CSV 文件（主要來源）

採用**靜態 CSV 文件**作為主要數據源：

- **路徑**：`data/earnings_calendar.csv`
- **涵蓋期間**：2020-01-01 至 2025-01-31
- **符號範圍**：AAPL, MSFT, GOOGL, META (FB), AMZN
- **事件類型**：Earnings（財報發布）

### 3.2 數據格式

```csv
Date,Event,Type,Symbol
2024-01-25,Microsoft Q2 2024 Earnings,Earnings,MSFT
2024-02-01,Alphabet Q4 2023 Earnings,Earnings,GOOGL
2024-02-02,Apple Q1 2024 Earnings,Earnings,AAPL
```

**欄位說明**：
- `Date`：財報發布日期（YYYY-MM-DD）
- `Event`：事件描述（公司名稱 + 季度 + 年份）
- `Type`：事件類型（目前僅 "Earnings"）
- `Symbol`：股票代號

### 3.3 yfinance 動態抓取（備用）

當使用者選擇 `prefer_yfinance=True` 時：

- 嘗試從 yfinance 抓取 `ticker.earnings_dates`
- **限制**：
  - 覆蓋範圍有限（不一定有歷史數據）
  - 可能失敗或不完整
  - 需網絡連接
- **降級策略**：抓取失敗時回退到示範 CSV

### 3.4 為何選擇示範 CSV 優先？

| 優勢 | 說明 |
|------|------|
| **免費** | 無需 API key，Streamlit Community Cloud 可直接運行 |
| **可重現** | 歷史數據固定，回測結果可完全重現 |
| **透明** | 數據來源清晰，用戶可檢視與編輯 |
| **快速** | 本地加載，無網絡延遲 |
| **離線可用** | 無網絡環境也能運行完整回測 |

---

## 4. 使用說明

### 4.1 UI 控制（Streamlit 側欄）

#### 顯示控制

```
📊 財報／商蹤時間線 / Earnings Timeline
L1 研究層：顯示與對齊 / L1 Research: Display & Alignment

☑️ 顯示財報／商蹤（研究）/ Show Earnings/Business Events (Research)
    顯示回測期間的財報及重要企業事件

💡 單一股票：顯示財報日期 / Single stocks: Show earnings dates
💡 指數／ETF：優雅降級（樣本數據）/ Index/ETF: Graceful degradation (sample data)
```

- **預設狀態**：關閉（避免干擾，由用戶選擇啟用）
- **效果**：在權益曲線圖上以彩色方塊標記財報日期

#### 研究過濾（可選）

```
⚠️ 研究過濾（可選）/ Research Filter (Optional)
此過濾僅用於研究對比，不會修改主回測結果

□ 啟用避開財報日過濾 / Enable Earnings Date Avoidance Filter

[  1  ] 避開前 N 日（財報）/ Days Before (Earnings)
[  0  ] 避開後 N 日（財報）/ Days After (Earnings)
```

- **預設狀態**：關閉
- **效果**：啟用後，顯示「財報過濾對比」區塊，展示排除特定窗口交易後的績效

### 4.2 圖表標記

權益曲線圖上以不同顏色方塊標記各股票的財報：

| 視覺元素 | 說明 |
|---------|------|
| 符號 | ■ 方塊（區別於經濟日曆的 ◆ 菱形） |
| 顏色 | 每個股票自動分配一致的顏色 |
| Hover | 顯示日期、事件名稱、當日權益值 |

**與其他標記的區別**：
- 經濟日曆：◆ 菱形，按事件類型分色（紅/橘/紫/綠）
- 新聞：（無圖表標記，僅列表）
- 財報：■ 方塊，按股票符號分色

### 4.3 事件列表

「財報事件列表」摺疊面板（Expander）顯示：

| 欄位 | 說明 |
|------|------|
| Date | 日期（YYYY-MM-DD）|
| Event | 事件名稱（例如：Apple Q1 2024 Earnings）|
| Symbol | 股票代號 |

**額外功能**：
- 📥 **CSV 匯出**：可下載事件列表為 CSV 檔案
- 檔名格式：`earnings_events_{symbol}_{start_date}_{end_date}.csv`

### 4.4 研究過濾對比

啟用研究過濾後，顯示「🔬 財報過濾對比」區塊：

**左欄：🔵 完整回測**
- 交易次數
- 總回報
- 勝率

**右欄：🔬 過濾後**
- 交易次數（顯示減少數量）
- 總回報（顯示差異 Δ）
- 勝率（顯示差異 Δ）

**解讀提示**：
- 若過濾後績效顯著改善 → 可考慮開發 L2 事件驅動策略
- 若無明顯差異 → 說明策略對財報發布日不敏感
- 若過濾後績效變差 → 可能策略在波動期（財報前後）表現更好

---

## 5. 技術實現

### 5.1 模組結構

```
backtester/
├── earnings_calendar.py       # L1 財報日曆模組
│   ├── EarningsCalendar       # 日曆加載與過濾類
│   ├── is_index_or_etf        # 指數/ETF 檢測函數
│   ├── try_fetch_yfinance_earnings  # yfinance 抓取（best-effort）
│   └── calculate_research_metrics   # 研究指標計算
│
data/
├── earnings_calendar.csv      # 靜態財報日曆數據
│
tests/
├── test_earnings_calendar.py  # 完整測試套件
```

### 5.2 EarningsCalendar 類

```python
calendar = EarningsCalendar()
calendar.load()  # 加載數據（預設從示範 CSV）

# 或嘗試從 yfinance 抓取
calendar.load(
    symbol="AAPL",
    start_date=pd.Timestamp("2020-01-01"),
    end_date=pd.Timestamp("2020-12-31"),
    prefer_yfinance=True,  # 嘗試 yfinance，失敗則回退 CSV
)

# 過濾事件
events = calendar.filter_by_date_range(
    start_date=pd.Timestamp("2020-01-01"),
    end_date=pd.Timestamp("2020-12-31"),
    symbol="AAPL",  # 可選：過濾特定股票
)

# 獲取事件日期（用於圖表標記）
event_dates = calendar.get_event_dates(start, end, symbol="AAPL")

# 創建排除窗口（研究過濾）
excluded_dates = calendar.create_exclusion_window(
    event_dates,
    days_before=1,
    days_after=0,
)

# 過濾交易
filtered_trades = calendar.filter_trades_by_exclusion(
    trades_df,
    excluded_dates,
    entry_column="Entry Date",
)
```

### 5.3 指數/ETF 檢測

```python
from backtester.earnings_calendar import is_index_or_etf

is_index_or_etf("SPY")   # True
is_index_or_etf("AAPL")  # False
is_index_or_etf("QQQ")   # True
```

**檢測邏輯**：
- 白名單：常見指數 ETF（SPY, QQQ, DIA, IWM, VTI, VOO, etc.）
- 港股指數：檢測 `.HK` 後綴並判斷代號範圍
- 預設：未匹配的視為個股

### 5.4 Streamlit 整合

```python
# 側欄控制
show_earnings = st.checkbox("顯示財報／商蹤（研究）", value=False)
earnings_filter_enabled = st.checkbox("啟用避開財報日過濾", value=False)

# 加載財報日曆（L1 層，不影響 L0）
if show_earnings:
    earnings_calendar = EarningsCalendar()
    if earnings_calendar.load(symbol=symbol, ...):
        earnings_events = earnings_calendar.filter_by_date_range(...)

# 傳遞給圖表（display-only）
plot_equity_curve(
    equity_curve, 
    buy_hold_curve, 
    event_markers=calendar_events,
    earnings_markers=earnings_events,  # Phase 4
)

# 研究過濾（opt-in）
if earnings_filter_enabled:
    # 顯示對比結果（不修改主回測結果）
    ...
```

---

## 6. Phase 0 合規性驗證

### 6.1 測試策略

Phase 4 測試套件 (`tests/test_earnings_calendar.py`) 包含專門的 Phase 0 合規測試類：

```python
class TestPhase0Compliance:
    """測試 Phase 0 合規性"""
    
    def test_l0_unchanged_when_calendar_not_used(self):
        """驗證財報日曆未使用時 L0 結果不變"""
        # 運行兩次回測：一次無日曆，一次有日曆但不過濾
        # 驗證所有 L0 指標完全相同
        
    def test_research_filter_is_opt_in_only(self):
        """驗證研究過濾必須明確啟用"""
        # 創建排除窗口但不應用
        # 驗證原始交易數據不受影響
        
    def test_calendar_load_failure_does_not_crash(self):
        """驗證財報日曆載入失敗時優雅降級"""
        # 使用不存在的日曆路徑
        # 驗證回測仍可正常運行
```

### 6.2 合規檢查清單

- [ ] 關閉財報顯示時，回測結果與 Phase 3 完全相同
- [ ] 只開啟財報顯示（不啟用過濾）時，回測結果與 Phase 3 完全相同
- [ ] 研究過濾預設為「關閉」
- [ ] 研究過濾啟用時，主回測結果保持可見且不變
- [ ] 研究過濾結果明確標示為「次要／研究用途」
- [ ] 財報日曆載入失敗時，顯示提示但不中斷回測
- [ ] Streamlit Community Cloud 可無 API key 運行
- [ ] 指數/ETF 優雅降級，明確標示限制

---

## 7. 限制與已知問題

### 7.1 數據限制

| 限制項目 | 說明 |
|---------|------|
| **歷史數據不完整** | 示範 CSV 僅涵蓋 2020 年至 2025 年，更早期數據需手動補充 |
| **僅主要科技股** | 示範數據僅包含 AAPL, MSFT, GOOGL, META, AMZN |
| **未來日期可能變動** | 未來財報日期為預計時間，可能因公司調整而變動 |
| **無財報實際內容** | 僅提供發布日期，不包含 EPS、營收等實際數據 |

### 7.2 功能限制

| 限制項目 | 說明 |
|---------|------|
| **盤中時間** | 不支持盤中精確時間對齊（財報通常盤後發布）|
| **指數成分股** | 不提供指數完整成分股財報日曆（需付費 API）|
| **業績預期** | 不提供市場預期 vs. 實際業績的差異分析 |
| **其他企業事件** | 目前僅財報，未包含併購、拆分、產品發表等事件 |

### 7.3 yfinance 限制

| 限制項目 | 說明 |
|---------|------|
| **覆蓋率不穩定** | yfinance earnings_dates 覆蓋範圍因股票而異 |
| **歷史數據有限** | 可能僅提供近期財報，歷史數據不完整 |
| **抓取可能失敗** | 網絡問題或 API 變更可能導致抓取失敗 |
| **無服務保證** | yfinance 為非官方 API，無可靠性保證 |

### 7.4 研究過濾限制

| 限制項目 | 說明 |
|---------|------|
| **簡化模型** | 僅以「進場日期」判斷是否排除，未考慮持倉期間的財報 |
| **不是策略** | 過濾結果僅供研究，不能直接用作交易策略 |
| **樣本偏差** | 排除部分交易後，可能產生樣本選擇偏差 |
| **時區考量** | 盤後財報可能影響次日開盤，簡單日期過濾可能不精確 |

---

## 8. 未來擴展方向（Phase 5+）

| 方向 | 階段 | 說明 |
|------|------|------|
| **更多企業事件** | Phase 5 | 併購、拆分、產品發表、重大訴訟等 |
| **業績驚喜分析** | Phase 5+ | 實際 vs. 預期的差異（需付費 API）|
| **指數成分股支援** | Phase 5+ | 提供指數完整成分股財報（需付費 API）|
| **事件驅動策略** | Phase 5 | L2 層策略：根據財報結果調整倉位 |
| **盤後交易影響** | Phase 5+ | 分析盤後財報對次日開盤的影響 |

---

## 9. 常見問題（FAQ）

### Q1：為何不用付費 API（如 Alpha Vantage, Polygon）？

**A**：Phase 0 原則要求「Streamlit Community Cloud 預設可跑」。付費 API 需要 key，會導致未設定 key 的用戶無法使用。示範 CSV 保證所有人都能直接運行。

### Q2：如何更新財報日曆數據？

**A**：直接編輯 `data/earnings_calendar.csv`，按照現有格式新增行即可。建議每季度補充未來 3-6 個月的預計財報日。

### Q3：指數 ETF（如 SPY）為何不顯示完整財報？

**A**：SPY 追蹤標普 500 指數，包含 500 支股票。提供完整成分股財報日曆需：
1. 付費 API（違反 Phase 0 原則）
2. 龐大數據量（影響效能）
3. 實時更新（成分股會調整）

因此，指數符號採用**優雅降級**：明確告知限制，並提供相關大型股樣本（可選）。

### Q4：研究過濾的「避開±N天」應該設多少？

**A**：沒有標準答案，取決於研究目的：
- **±0 天**：只避開財報發布當日
- **±1 天**：避開前後各 1 天（常見設定，考慮盤後發布影響次日）
- **±2+ 天**：避開更大窗口（樣本會顯著減少）

建議從 ±1 天開始，觀察對比結果。

### Q5：為何過濾後績效反而更差？

**A**：可能原因：
1. 策略本身在波動期（財報前後）表現更好
2. 財報前後流動性更高，策略更易成交
3. 樣本數減少導致統計不穩定
4. 隨機性（需更長回測期驗證）

這正是「研究過濾」的價值：幫助理解策略特性。

### Q6：可以把「避開財報日」直接加入策略嗎？

**A**：可以，但需要**明確設計為 L2 事件驅動策略**（Phase 5），並：
1. 創建獨立策略類（例如 `EarningsAwareSMACrossover`）
2. 文件說明事件規則邏輯
3. 提供對照測試（有／無事件規則的績效對比）
4. 標示為「實驗性策略」

**不要**直接在現有 `SMACrossover` 或 `RSIMeanReversion` 中偷偷加入財報規則。

### Q7：yfinance 抓取財報日期可靠嗎？

**A**：**不完全可靠**：
- yfinance 為非官方 Yahoo Finance API 包裝
- 數據覆蓋率因股票而異
- 可能因 Yahoo 改版而失效
- 建議主要依賴示範 CSV，yfinance 僅作補充

---

## 10. 參考資料

### 數據來源

- [Yahoo Finance Earnings Calendar](https://finance.yahoo.com/calendar/earnings)
- [yfinance Python Library](https://github.com/ranaroussi/yfinance)
- 各公司投資者關係網頁（IR）

### 相關文件

- [docs/PHASE0-boundaries.md](./PHASE0-boundaries.md) - 產品邊界與數據原則
- [docs/PHASE2-economic-calendar.md](./PHASE2-economic-calendar.md) - 經濟日曆實現參考
- [docs/PHASE3-news-panel.md](./PHASE3-news-panel.md) - 新聞面板實現參考
- [README.md](../README.md) - 項目總覽

---

## 11. 變更歷史

| 版本 | 日期 | 說明 |
|------|------|------|
| 1.0.0 | 2024 | Phase 4 初版：財報／商蹤時間線上線 |

---

**Phase 4 完成標準**：
- [ ] 靜態 CSV 財報日曆數據（2020-2025）
- [ ] 側欄控制（顯示／研究過濾）
- [ ] 圖表標記（彩色方塊 + Hover）
- [ ] 財報事件列表摺疊面板
- [ ] CSV 匯出功能
- [ ] 研究過濾對比（side-by-side）
- [ ] 指數/ETF 優雅降級
- [ ] Phase 0 合規測試通過
- [ ] 優雅降級（無 key 可運行）
- [ ] 文件完成（本文件 + README 指向）

🚧 Phase 4 財報時間線功能開發中！
