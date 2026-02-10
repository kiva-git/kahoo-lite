# Kahoo Lite (Kahoot-like demo)

一個最小可跑的 Kahoot-like 範例：
- Python FastAPI 後端（房間、玩家、答題、排行榜）
- WebSocket 即時推播狀態
- 簡易前端頁面

## 為什麼要虛擬環境
這個專案使用 Python 套件，建議用 `venv` 隔離依賴，避免和系統 Python 衝突。

## 啟動方式

### 1) 後端
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 2) 前端
另開一個終端：
```bash
cd frontend
python3 -m http.server 5500
```

瀏覽器打開：
- `http://127.0.0.1:5500`

## 基本流程
1. 輸入主持人名稱，按「建立房間」
2. 另一個分頁/裝置輸入 PIN + 玩家名稱加入
3. 主持人按「開始遊戲」
4. 玩家點選答案
5. 主持人按「下一題」

## 後端 API 摘要
- `POST /rooms` 建立房間
- `POST /rooms/join` 玩家加入
- `POST /rooms/{pin}/start` 開始
- `POST /rooms/submit` 提交答案
- `POST /rooms/{pin}/next` 下一題
- `GET /rooms/{pin}/leaderboard` 排行
- `WS /ws/{pin}` 即時狀態

## 下一步可擴充
- 題庫管理（CRUD）
- 倒數計時、速度加權計分
- 主持人/玩家分離 UI
- 持久化（SQLite/PostgreSQL）
- 登入與房間權限
