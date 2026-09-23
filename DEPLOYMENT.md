# 部署指南 / Deployment Guide

## 快速部署 / Quick Deploy

### 1. Streamlit Community Cloud（推薦 / Recommended）

最簡單的部署方式，完全免費，無需信用卡。

**步驟：**

1. 將代碼推送到 GitHub
2. 前往 https://share.streamlit.io
3. 使用 GitHub 帳號登入
4. 點擊「New app」
5. 選擇你的儲存庫
6. 主文件路徑：`streamlit_app.py`
7. 點擊「Deploy」

✅ 數分鐘內即可上線
✅ 自動 HTTPS
✅ 無需配置

---

### 2. Docker 本地測試

```bash
# 建構映像
docker build -t backtester-dashboard .

# 運行容器
docker run -p 8501:8501 backtester-dashboard

# 訪問
open http://localhost:8501
```

---

### 3. Render.com 部署

**免費方案可用**

1. 前往 https://render.com
2. 連接 Git 儲存庫
3. 創建「New Web Service」
4. 選擇環境：Docker
5. Render 自動檢測 `render.yaml`
6. 點擊「Create Web Service」

**配置：**
- Environment: Docker
- Port: 8501 (自動從 `render.yaml` 讀取)
- Health Check Path: `/_stcore/health`

---

### 4. Railway.app 部署

**$5/月免費額度**

1. 前往 https://railway.app
2. 點擊「New Project」
3. 選擇「Deploy from GitHub repo」
4. 選擇你的儲存庫
5. Railway 自動檢測 `Dockerfile`
6. 添加環境變數（如需要）：
   - `PORT=8501`
7. 部署

---

### 5. Fly.io 部署

**免費方案：3 個小型應用**

```bash
# 安裝 Fly CLI
curl -L https://fly.io/install.sh | sh

# 登入
fly auth login

# 初始化並部署
fly launch
fly deploy

# 查看應用
fly open
```

---

### 6. Heroku 部署

```bash
# 安裝 Heroku CLI
# macOS: brew install heroku/brew/heroku
# Linux: curl https://cli-assets.heroku.com/install.sh | sh

# 登入
heroku login

# 創建應用
heroku create your-app-name

# 推送代碼（使用 Procfile）
git push heroku main

# 打開應用
heroku open
```

---

## 環境變數 / Environment Variables

所有部署方式都支援以下環境變數：

| 變數名稱 | 預設值 | 說明 |
|---------|-------|------|
| `PORT` | 8501 | 應用程式監聽端口 |
| `STREAMLIT_SERVER_PORT` | 8501 | Streamlit 伺服器端口 |
| `STREAMLIT_SERVER_ADDRESS` | 0.0.0.0 | 綁定地址 |
| `STREAMLIT_SERVER_HEADLESS` | true | 無頭模式 |

---

## 健康檢查 / Health Check

所有雲端平台都可以使用以下健康檢查端點：

```
GET /_stcore/health
```

**預期響應：** HTTP 200 OK

---

## 本地開發 / Local Development

```bash
# 安裝依賴
pip install -r requirements.txt

# 運行儀表板
streamlit run streamlit_app.py

# 訪問
open http://localhost:8501
```

---

## 疑難排解 / Troubleshooting

### 問題：端口衝突

```bash
# 使用自訂端口
streamlit run streamlit_app.py --server.port=8502
```

### 問題：依賴安裝失敗

```bash
# 升級 pip
pip install --upgrade pip

# 重新安裝
pip install -r requirements.txt --force-reinstall
```

### 問題：Docker 構建緩慢

```bash
# 使用 BuildKit
DOCKER_BUILDKIT=1 docker build -t backtester-dashboard .
```

### 問題：記憶體不足（雲端平台）

- 確保使用免費方案的 512MB-1GB RAM
- 減少歷史數據範圍
- 使用範例 CSV 而非大量下載

---

## 功能限制 / Limitations

### 免費方案限制

**Streamlit Cloud:**
- 1 個應用
- 1 GB RAM
- 1 個 CPU
- 閒置 7 天後休眠

**Render:**
- 750 小時/月
- 512 MB RAM
- 0.1 CPU
- 15 分鐘不活動後休眠

**Railway:**
- $5 免費額度/月
- 500 MB RAM
- 0.5 CPU

**Fly.io:**
- 3 個小型應用
- 256 MB RAM
- Shared CPU

---

## 效能優化 / Performance Tips

1. **使用範例數據**：離線運行，速度最快
2. **限制日期範圍**：下載較少數據
3. **調整策略參數**：減少計算複雜度
4. **使用緩存**：yfinance 自動緩存數據

---

## 安全建議 / Security

- ✅ 無需 API 密鑰即可使用基本功能
- ✅ Yahoo Finance 為公開數據
- ✅ 不存儲用戶數據
- ✅ 所有計算在伺服器端進行
- ⚠️ 上傳的 CSV 文件僅在會話期間存在

---

## 支援 / Support

遇到問題？檢查：

1. README.md - 完整文檔
2. tests/ - 測試案例
3. GitHub Issues - 報告問題

---

## 授權 / License

本項目僅供教育和研究用途。
This project is for educational and research purposes only.
