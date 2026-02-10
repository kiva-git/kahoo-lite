# Kahoo Lite 專案進度（交接用）

更新時間：2026-02-10 22:01 (GMT+8)

## 已完成

### 1) 專案初始化
- 建立路徑：`project/kahoo-lite`
- 結構：
  - `backend/`（FastAPI + WebSocket）
  - `frontend/`（Host / Player / Index）

### 2) 核心遊戲功能
- 建房、加入房間
- 開始遊戲、下一題
- 玩家作答
- 排行榜
- WebSocket 即時狀態同步

### 3) 互動修正
- 玩家按鈕無反應問題修正（顯示錯誤訊息）
- 未開始時禁用作答按鈕
- 同名重連可用（保留分數，不被拒絕）

### 4) 遊戲機制升級
- 倒數計時（每題 20 秒）
- 自動鎖題（超時後不能作答）
- 快答加分（越快答對分數越高）
- 同題重複提交防護（Already answered）

### 5) UI/UX 升級
- Host / Player 分離頁面
- 專業化儀表板風格（Linear / Stripe / Kahoot-like）
- Kahoot 風格選項按鈕（紅/藍/黃/綠）
- Host 全螢幕題目模式
- 排行榜動態轉場
- Host 顯示玩家加入 QR Code

### 6) 部署準備（Render）
- 已改為單服務架構：FastAPI 同時提供 API + 前端靜態頁
- 新增 `render.yaml`
- CORS 可透過 `ALLOWED_ORIGINS` 設定
- 前端 API 位址改為本地/部署自動切換

## 重要檔案
- `project/kahoo-lite/backend/app/main.py`
- `project/kahoo-lite/frontend/index.html`
- `project/kahoo-lite/frontend/host.html`
- `project/kahoo-lite/frontend/player.html`
- `project/kahoo-lite/frontend/styles.css`
- `project/kahoo-lite/render.yaml`
- `project/kahoo-lite/README.md`

## 目前待辦（下一次回來先做）
1. 安裝並啟用 Chrome 擴充：OpenClaw Browser Relay
2. 連上已登入的 Render 分頁（附加 Relay）
3. 用 Blueprint 部署 `project/kahoo-lite/render.yaml`
4. 上線後驗證：
   - `/health`
   - `/host.html`
   - `/player.html`
   - WebSocket 即時更新

## 快速本地啟動

### 後端
```bash
cd /Users/ericlee/.openclaw/workspace/project/kahoo-lite/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 前端（本地分離模式）
```bash
cd /Users/ericlee/.openclaw/workspace/project/kahoo-lite/frontend
python3 -m http.server 5500
```

- Host: `http://127.0.0.1:5500/host.html`
- Player: `http://127.0.0.1:5500/player.html`

---
如需我接續，下一句可直接說：
「繼續部署到 Render」
