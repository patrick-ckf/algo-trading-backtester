# Phase 2：經濟日曆疊加層

**階段狀態：已完成 ✅**

本文件說明 Phase 2 經濟日曆功能的實現方式、數據來源、時區處理、限制與 Phase 0 合規性。

---

## 1. 功能概述

Phase 2 加入**美國宏觀經濟數據發布日曆**作為 L1 研究層疊加，提供：

1. **圖表標記**：在權益曲線上標記重要經濟數據發布日（CPI、NFP、FOMC、失業率、GDP）
2. **事件列表**：顯示回測期間內的經濟事件時間線
3. **研究過濾（可選）**：提供「避開公佈日±N天」的過濾功能，用於研究對比

### 核心原則（Phase 0 合規）

| 原則 | 說明 |
|------|------|
| **L1 層級** | 經濟日曆為研究層（L1），**不修改** L0 回測引擎或策略邏輯 |
| **預設行為** | 預設為「顯示標記」模式，不影響回測結果 |
| **研究過濾** | 「避開公佈日」過濾必須**明確啟用**，並標示為研究用途 |
| **對比展示** | 過濾結果以**次要結果**展示，主回測結果保持可見 |
| **優雅降級** | 若日曆數據載入失敗，顯示提示但不影響回測運行 |

---

## 2. 數據來源

### 2.1 靜態 CSV 文件

採用**靜態 CSV 文件**作為主要數據源：

- **路徑**：`data/economic_calendar.csv`
- **涵蓋期間**：2018-01-01 至 2026-01-31（可定期更新）
- **事件類型**：
  - **CPI**：消費者物價指數（月度）
  - **NFP**：非農就業人口（月度）
  - **FOMC**：聯準會利率決議（每年 8 次）
  - **GDP**：國內生產總值（季度，包含 Advance/Final）
  - **Unemployment**：失業率（未來可擴展）

### 2.2 數據格式

```csv
Date,Event,Type,Country
2024-01-11,CPI,CPI,US
2024-01-05,Nonfarm Payrolls,NFP,US
2024-01-31,FOMC Decision,FOMC,US
```

### 2.3 更新策略

- **頻率**：建議每季度更新一次，補充未來 6-12 個月的預定發布日期
- **來源參考**：
  - [美國勞工統計局（BLS）發布日曆](https://www.bls.gov/schedule/)
  - [聯準會會議時程](https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm)
  - [美國經濟分析局（BEA）發布日曆](https://www.bea.gov/news/schedule)
- **手動編輯**：可直接編輯 CSV 文件新增或修正日期

### 2.4 為何選擇靜態 CSV？

| 優勢 | 說明 |
|------|------|
| **免費** | 無需 API key，Streamlit Community Cloud 可直接運行 |
| **可重現** | 歷史數據固定，回測結果可完全重現 |
| **透明** | 數據來源清晰，用戶可檢視與編輯 |
| **快速** | 本地加載，無網絡延遲 |

---

## 3. 時區處理

### 3.1 儲存格式

- **儲存時區**：數據以**美東時間（US Eastern Time）**儲存
- **原因**：美國經濟數據發布時間皆為美東時間（例如 CPI 通常在美東上午 8:30 發布）

### 3.2 顯示邏輯

- **圖表標記**：以日期（Date）為單位，不涉及具體時間
- **用戶提示**：UI 標註「時區：美東時間」
- **亞洲時區**：UI 說明中提及「對應亞洲時區為 Asia/Taipei 晚間」，但不做強制轉換

### 3.3 回測對齊

- 回測使用**日線（Daily）OHLCV 數據**，經濟數據發布日標記在當日 Close 價格對應點
- 不涉及盤中（Intraday）時間對齊

---

## 4. 使用說明

### 4.1 UI 控制（Streamlit 側欄）

#### 顯示控制

```
📅 經濟日曆 / Economic Calendar
L1 研究層：顯示與對齊 / L1 Research: Display & Alignment

☑️ 顯示經濟公佈日 / Show Economic Releases
    在圖表上標記重要經濟數據發布日期

□ CPI
□ NFP
□ FOMC
□ GDP
```

- **預設狀態**：開啟顯示，選擇所有事件類型
- **效果**：在權益曲線圖上以彩色菱形標記事件日期

#### 研究過濾（可選）

```
⚠️ 研究過濾（可選）/ Research Filter (Optional)
此過濾僅用於研究對比，不會修改主回測結果

□ 啟用避開公佈日過濾 / Enable Release Date Avoidance Filter

[  1  ] 避開前 N 日 / Days Before
[  0  ] 避開後 N 日 / Days After
```

- **預設狀態**：關閉
- **效果**：啟用後，顯示「研究過濾對比」區塊，展示排除特定窗口交易後的績效

### 4.2 圖表標記

權益曲線圖上以不同顏色標記事件類型：

| 事件類型 | 顏色 | 符號 |
|---------|------|------|
| CPI | 🔴 紅色 | ◆ |
| NFP | 🟠 橘色 | ◆ |
| FOMC | 🟣 紫色 | ◆ |
| GDP | 🟢 綠色 | ◆ |

滑鼠懸停（Hover）顯示：
- 日期
- 事件類型
- 當日權益值

### 4.3 事件列表

「經濟事件列表」摺疊面板（Expander）顯示：
- 日期（YYYY-MM-DD）
- 事件名稱
- 事件類型
- 國家（US）

### 4.4 研究過濾對比

啟用研究過濾後，顯示「🔬 研究過濾對比」區塊：

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
- 若無明顯差異 → 說明策略對經濟數據發布日不敏感

---

## 5. 技術實現

### 5.1 模組結構

```
backtester/
├── economic_calendar.py       # L1 經濟日曆模組
│   ├── EconomicCalendar      # 日曆加載與過濾類
│   └── calculate_research_metrics  # 研究指標計算
│
data/
├── economic_calendar.csv      # 靜態日曆數據
│
tests/
├── test_economic_calendar.py  # 完整測試套件
```

### 5.2 EconomicCalendar 類

```python
calendar = EconomicCalendar()
calendar.load()  # 加載數據

# 過濾事件
events = calendar.filter_by_date_range(
    start_date=pd.Timestamp("2020-01-01"),
    end_date=pd.Timestamp("2020-12-31"),
    event_types=["CPI", "FOMC"],
)

# 獲取事件日期（用於圖表標記）
event_dates = calendar.get_event_dates(start, end, event_types)

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
)
```

### 5.3 Streamlit 整合

```python
# 側欄控制
show_calendar = st.checkbox("顯示經濟公佈日", value=True)
calendar_event_types = st.multiselect("事件類型", [...])
calendar_filter_enabled = st.checkbox("啟用避開公佈日過濾", value=False)

# 加載日曆（L1 層，不影響 L0）
if show_calendar:
    economic_calendar = EconomicCalendar()
    if economic_calendar.load():
        calendar_events = economic_calendar.filter_by_date_range(...)

# 傳遞給圖表（display-only）
plot_equity_curve(equity_curve, buy_hold_curve, event_markers=calendar_events)

# 研究過濾（opt-in）
if calendar_filter_enabled:
    # 顯示對比結果（不修改主回測結果）
    ...
```

---

## 6. Phase 0 合規性驗證

### 6.1 測試策略

Phase 2 測試套件 (`tests/test_economic_calendar.py`) 包含專門的 Phase 0 合規測試類：

```python
class TestPhase0Compliance:
    """測試 Phase 0 合規性"""
    
    def test_l0_unchanged_when_calendar_not_used(self):
        """驗證日曆未使用時 L0 結果不變"""
        # 運行兩次回測：一次無日曆，一次有日曆但不過濾
        # 驗證所有 L0 指標完全相同
        
    def test_research_filter_is_opt_in_only(self):
        """驗證研究過濾必須明確啟用"""
        # 創建排除窗口但不應用
        # 驗證原始交易數據不受影響
        
    def test_calendar_load_failure_does_not_crash(self):
        """驗證日曆載入失敗時優雅降級"""
        # 使用不存在的日曆路徑
        # 驗證回測仍可正常運行
```

### 6.2 合規檢查清單

- [x] 關閉日曆顯示時，回測結果與 Phase 1 完全相同
- [x] 只開啟日曆顯示（不啟用過濾）時，回測結果與 Phase 1 完全相同
- [x] 研究過濾預設為「關閉」
- [x] 研究過濾啟用時，主回測結果保持可見且不變
- [x] 研究過濾結果明確標示為「次要／研究用途」
- [x] 日曆載入失敗時，顯示提示但不中斷回測
- [x] Streamlit Community Cloud 可無 API key 運行

---

## 7. 限制與已知問題

### 7.1 數據限制

| 限制項目 | 說明 |
|---------|------|
| **歷史數據不完整** | 僅涵蓋 2018 年至今，更早期數據需手動補充 |
| **預定日期可能變動** | 未來發布日期為預計時間，可能因假日或特殊情況調整 |
| **僅美國數據** | 不包含歐洲、亞洲等其他地區經濟數據 |

### 7.2 功能限制

| 限制項目 | 說明 |
|---------|------|
| **盤中時間** | 不支持盤中精確時間對齊（例如 8:30 AM ET 發布） |
| **實際值與預期值** | 不提供數據實際值與市場預期差異 |
| **市場反應** | 不分析數據發布後的市場波動幅度 |

### 7.3 研究過濾限制

| 限制項目 | 說明 |
|---------|------|
| **簡化模型** | 僅以「進場日期」判斷是否排除，未考慮持倉期間的事件 |
| **不是策略** | 過濾結果僅供研究，不能直接用作交易策略 |
| **樣本偏差** | 排除部分交易後，可能產生樣本選擇偏差 |

---

## 8. 未來擴展方向（Phase 3+）

| 方向 | 階段 | 說明 |
|------|------|------|
| **其他國家數據** | Phase 3 | 歐洲 ECB、英國 BOE、日本 BOJ 等 |
| **財報日曆** | Phase 4 | 標普 500 成分股財報發布日 |
| **新聞事件** | Phase 3 | 重要新聞事件時間線 |
| **實際值 API** | Phase 3+ | 整合 FRED API 提供歷史實際值 |
| **事件驅動策略** | Phase 5 | L2 層策略：根據數據優劣調整倉位 |

---

## 9. 常見問題（FAQ）

### Q1：為何不用付費 API（如 TradingEconomics）？

**A**：Phase 0 原則要求「Streamlit Community Cloud 預設可跑」。付費 API 需要 key，會導致未設定 key 的用戶無法使用。靜態 CSV 保證所有人都能直接運行。

### Q2：如何更新日曆數據？

**A**：直接編輯 `data/economic_calendar.csv`，按照現有格式新增行即可。建議每季度補充未來 6-12 個月的預定發布日。

### Q3：研究過濾的「避開±N天」應該設多少？

**A**：沒有標準答案，取決於研究目的：
- **±0 天**：只避開發布當日
- **±1 天**：避開前後各 1 天（常見設定）
- **±2+ 天**：避開更大窗口（樣本會顯著減少）

建議從 ±1 天開始，觀察對比結果。

### Q4：為何過濾後績效反而更差？

**A**：可能原因：
1. 策略本身在波動期（經濟數據發布前後）表現更好
2. 樣本數減少導致統計不穩定
3. 隨機性（需更長回測期驗證）

這正是「研究過濾」的價值：幫助理解策略特性。

### Q5：可以把「避開公佈日」直接加入策略嗎？

**A**：可以，但需要**明確設計為 L2 事件驅動策略**（Phase 5），並：
1. 創建獨立策略類（例如 `EventAwareSMACrossover`）
2. 文件說明事件規則邏輯
3. 提供對照測試（有／無事件規則的績效對比）
4. 標示為「實驗性策略」

**不要**直接在現有 `SMACrossover` 或 `RSIMeanReversion` 中偷偷加入事件規則。

---

## 10. 參考資料

### 數據來源

- [美國勞工統計局（BLS）發布日曆](https://www.bls.gov/schedule/)
- [聯準會會議時程](https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm)
- [美國經濟分析局（BEA）](https://www.bea.gov/news/schedule)

### 相關文件

- [docs/PHASE0-boundaries.md](./PHASE0-boundaries.md) - 產品邊界與數據原則
- [README.md](../README.md) - 項目總覽

---

## 11. 變更歷史

| 版本 | 日期 | 說明 |
|------|------|------|
| 1.0.0 | 2024 | Phase 2 完成：經濟日曆疊加層上線 |

---

**Phase 2 完成標準**：
- [x] 靜態 CSV 日曆數據（2018-2026）
- [x] 側欄控制（顯示／事件類型／研究過濾）
- [x] 圖表標記（彩色菱形 + Hover）
- [x] 事件列表摺疊面板
- [x] 研究過濾對比（side-by-side）
- [x] Phase 0 合規測試通過
- [x] 優雅降級（無 key 可運行）
- [x] 文件完成（本文件 + README 指向）

🎉 Phase 2 經濟日曆功能已上線！
