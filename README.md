# StockNexus-Wiki

以真實財經新聞建立可解釋的關聯圖譜，結合 **3D 探索、時間軸與持久快取**。
GitHub 儲存庫命名：`stocknexus-wiki`。

## 功能

- 整合 Google News RSS、Yahoo 地區新聞與 Massive；支援日期範圍、來源與分類篩選。
- 每條關聯保留共同實體、主題或標題相似度的證據。
- 新聞自動存入 SQLite；相同資料與規則可重用持久圖譜快取。
- 支援圖譜快照、JSON 匯出、繁體中文／英文介面及 REST API。
- 3D 預設顯示 800 節點，可調至 2,400；完整資料仍保留於清單、時間軸與匯出。

## 快速啟動

下載專案後，在專案根目錄執行。需要 Python 3.10+、Docker Engine 與 Docker Compose（支援 `up --wait`）。

```bash
./run.sh
```

依提示選擇資料位置與連線方式，完成後開啟 [本機網頁](http://127.0.0.1:8765/)。

```bash
./run.sh up       # 更新程式後重新建置與啟動
./run.sh status   # 查看服務狀態
./run.sh logs     # 查看日誌
./run.sh down     # 停止服務，保留資料
```

不使用 Docker：執行 `./run.sh local` 或 `python3 server.py`。後端使用 Python 標準函式庫，前端不需 npm/build；3D 需要瀏覽器支援 WebGL。

## 使用方式

1. 輸入關鍵字、來源及日期，按「搜尋新聞」。Massive 另需股票代碼與 API key；Google／Yahoo 不需 key。
2. 在 3D 或時間軸探索新聞；圖內搜尋只查已載入的文章。
3. 在「關聯設定」調整規則並按「套用」。成功後，同瀏覽器、同網址會沿用設定。
4. 用「儲存圖譜快照」保留當時的資料與規則；載入快照不等於重新搜尋最新新聞。

「Already in DB」表示文章已存在；關聯另有快取。命中時先顯示完整圖譜，再補抓來源；新增資料的關聯可能仍需更新。

## 文件

- [專案地圖](spec/PROJECT_MAP.md)：程式架構與文件入口。
- [標準工作流程](spec/WORKFLOWS.md)：搜尋、設定、快照、更新及驗收。
- [啟動與資料管理](spec/RUNTIME.md)：Docker、本機模式、Tailscale、搬移與備份。
- [效能與 WebGL 排錯](spec/references/lesson-20261102-rendering-cache-settings.md)：已驗證原因、修正與注意事項。
- [API 文件](docs/API.md)／[本機 Swagger](http://127.0.0.1:8765/docs)。

新聞來源不保證完整歷史，程式未抓取新聞全文；關聯分數不是因果、機率或投資建議。服務適用於本機或受信任網路，目前沒有帳號隔離。
