# LLM Wiki 執行與維護

入口：[PROJECT_MAP](PROJECT_MAP.md)／[完整研究設計](TEMPORAL_WIKI.md)。2026-11-05。

## 已實作範圍

頂部 `LLM Wiki` 按鈕開啟獨立視圖；返回新聞圖譜保留原節點、連線、來源、焦點與鏡頭。先搜尋新聞，再填明確 `EXCHANGE:TICKER`、來源範圍、模型、每批／每日篇數，按「預覽更新範圍」後確認開始。預覽列出選取、已抽取、待處理、模型及持續維護查詢，不呼叫模型。切換股票或修改參數會使舊預覽失效，遲到的回覆也不能恢復確認按鈕。

模型透過既有主機 Codex 登入／SDK，獨立無工具 thread 輸出 JSON。Python 核對引用的新聞版本、內容 hash、標題／摘要逐字區段、關係類型與方向後，原子寫入新版本。LLM 不持有 DB 寫入工具；Claim/Event/Thesis 和關聯均保留提案／假說標示，引用核對不等於事實查核。

Wiki 提供 ArticleRevision、Claim、Event、Thesis 節點，SUPPORTS、CONTRADICTS、UPDATES、DEPENDS_ON、RELATED_TO、TEMPORALLY_PRECEDES 關聯。另有版本／UTC as_of、類型與關係篩選、引用詳情、Markdown 匯出、工作狀態／token 用量與取消。最新 100 版出現在下拉選單；更舊版本仍可用 API version 或 as_of 讀取。圖與 Markdown 最多載入 2,400 節點，並明示截斷；DB 不刪除完整歷史。前端連線最多節點數的三倍。

## 資料與成本

每股獨立保存於 `<新聞 DB 所在目錄>/research/<instrument 的 SHA-256 前 24 字元>/wiki.sqlite3`。內有凍結文章、節點、連線、版本、抽取記錄、設定、工作及呼叫帳本。`metadata.instrument` 驗證股票身分。與新聞 DB、配對快取、新聞圖快照分開；重新開頁或改渲染預算只讀 Wiki，不重新呼叫 LLM。備份時使用 SQLite backup 或停服後連同 WAL 正確備份整個 research 目錄，不能只複製正在寫入的主檔。

增量重用以 article revision 判斷，跨模型與 prompt 版本沿用已完成結果；抽取記錄仍保存模型／prompt 出處。內容改變保留舊 revision 並新增版本。模型每次最多收到一篇標題／摘要及 12 個既有節點摘要；候選從該股全部知識節點依既有文章連結、詞彙重疊選取，不再只看最新 500 個。這是有限詞彙檢索，不是把全圖送進模型，也不代表完整歷史語意檢索。

介面預設「全局」與最近一個月，可用日期欄位／雙滑桿或三個月／全部預設調整。全局指目前搜尋查詢在各來源 DB 的 memberships 加完整已載入文章，不是所有股票或整個新聞 DB；不受主頁來源勾選、800／2400 渲染預算或新聞 edge 規則影響。模型不使用新聞啟發式 edge；Wiki 依引用證據建立自己的關聯。僅改介面選項不會呼叫 LLM，須重新預覽、確認。日期按 UTC 且包含起訖日，無日期文章僅在不限日期時納入；每次最多 10,000 篇，超過時要求縮小範圍。待辦從較新文章開始；下次擴大日期只處理未完成的 revision，不夾帶其他範圍的舊待辦。

「局部校正」是明確手動選項，只複查已抽取文章，每批／每日上限照常計算，不能開持續維護。每篇記錄校正時的已抽取 revision 數量；沒有新增證據時不重複校正，分批可接續其他文章。有新增抽取證據後可再次手動校正。這是成本控制的證據世代標記，不代表依賴傳播或保證事實正確。

預設每批 5 篇、每股每日 20 次；上限每批 20、每日 100。每日按 UTC，呼叫前先記帳，失敗／取消亦可能已消耗用量。這是篇數／嘗試次數上限，不是 token、金額或帳號總額上限。模型端單次 120 秒，compiler 全域一次一篇。失敗停用該股持續維護；重啟時把 running 工作標記 interrupted 並停用自動維護，須重新預覽後續跑，已成功篇數不重做。queued 工作可在重啟後繼續。

「持續維護」預設關閉。啟用後，服務每分鐘檢查預覽列出的來源查詢 memberships，讀取已進入新聞 DB 的內容並處理待辦。日期沿用確認時的固定範圍，不隨日曆或介面日期自動擴大；需要擴大時重新預覽。只追蹤該範圍與指定查詢，不主動抓 provider、不掃全部 DB、不依賴瀏覽器保持開啟。焦點選取只限制首次擷取；持續維護追蹤的是預覽所列整個查詢。每日上限耗盡後，啟用中的維護可於次日續跑。停止自動維護不取消當下工作；工作列表的停止會同時取消該工作與自動維護。

目前的「維護」是新增／變更文章抽取與對既有節點的更新、反證、依賴等連線提案；**尚未實作依賴傳播後重評所有舊觀點、全文擷取、人工審核流程、Forecast/Outcome 或回測**。原研究設計的 20 項完整驗收仍未全部完成。

## 原始碼與 API

| 責任 | 位置 |
| --- | --- |
| 股票 DB、引用核對、版本、圖查詢 | `news_atlas/wiki/store.py` |
| 預覽、授權範圍、工作／配額、每分鐘維護 | `news_atlas/wiki/compiler.py` |
| HTTP 與來源檢查 | `news_atlas/wiki/http.py`、`server.py` |
| 無工具模型橋接與結構輸出 | `chat/wiki.mjs`、`chat/service.mjs` |
| 獨立介面與新聞選取 adapter | `dist/wiki-view.js`、`dist/wiki-view.css`、`dist/app.js` |

`GET /api/wiki/models` 回傳目前 Codex `model/list` 目錄與預設模型；只讀目錄、不呼叫推論，快取五分鐘。`GET /api/wiki/status` 回傳 bridge/default model/股票清單/writable。`GET graph|jobs|article|markdown` 需要 instrument；graph 可帶 version/as_of，article 帶 id，markdown 可帶 version。`POST plan` 接 instrument/model/batch_size/daily_limit/articles/sources/search，另有 scope（global/loaded/focus）、date_range（null 或 start/end ISO 日期）、operation（update/review），回傳有效 10 分鐘 plan_id；`POST jobs` 接 plan_id/continuous；`POST configure` 接 instrument/enabled；`POST cancel` 接 instrument/job_id。見 `/docs`。

Wiki 寫入要求 local peer、同源 Origin/Host；預設僅 localhost/127.0.0.1:8765。透過受信任反向代理使用時，明確設定 `NEWS_ATLAS_WIKI_ORIGINS` 為允許的完整來源（逗號分隔），Compose 會傳入容器。這個設定只擴展 Wiki，沒有放寬原 Chat 本機限定。讀圖不觸發模型工作。主機橋接使用 `./run.sh chat start`，預設模型為 `gpt-6.1-sol`，下拉選單來自安裝中 Codex 的 `model/list`（與 `/model` 的模型目錄同源），工作開始前驗證選擇。若預設模型不可用則要求明確選擇，不悄悄改用另一模型；目錄載入失敗仍可讀圖，但不可預覽啟動。仍須帳號有該模型權限。

## 驗證

`tests/test_wiki.py` 驗證持久重用、修訂、歷史、隔離、引用拒絕、取消晚到、每日上限、重啟不重試、查詢訂閱與 Relation JSON Schema；`tests/test_wiki_http.py` 驗證 API 與同源邊界；`tests/chat-wiki.test.mjs` 驗證結構輸出、禁止工具、單飛與取消；`tests/browser_wiki.py` 以隔離 Chromium／真實 HTTP 資產／合成 API 回應驗證競態、WebGL、切換與版面。不是對所有市場新聞品質的評估。

新增回歸覆蓋：跨模型重用、日期擴大只補缺、範圍外待辦隔離、校正分批去重、超過 500 節點上下文、舊快照 revision、背景／手動工作競態與讀模型目錄期間取消。
