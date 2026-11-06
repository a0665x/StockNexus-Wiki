# 第一階段診斷

上層：[Temporal Wiki](../../TEMPORAL_WIKI.md)。查核日期 2026-11-04；程式基線 `ef4fd11`＋本機修改。這份報告區分目前能力與建議修改，不把設計當成已上線功能。

## 實際抽樣

執行 `python3 scripts/wiki_readiness.py`，使用 SQLite `mode=ro`、單一讀取 transaction，未呼叫 provider／LLM。結果：[readiness.json](readiness.json)。每 provider 依 ID 抽 30 篇，共 90 篇；不是隨機或代表性品質評估集，不能由此推算全文比例。

- 此次讀取共 33,017 筆來源文章（Google 7,205／Massive 9,325／Yahoo 16,487），35 個來源查詢。執行中服務可繼續新增，數字是查核快照。
- 90 篇都有 published_at、fetched_at、summary；未見 first_seen_at、ingested_at、available_at、revision_id、content_hash、full_text。fetched_at 是現存 payload 的取得時間，不能證明完整修訂歷史。
- `attempts` 有 41 次 limit、1 次 rate_limit；不能把成功 HTTP 回應或零篇等同完整歷史。
- `daily_prices` 有 13 個代碼共 3,048 筆，最晚 2026-10-28；另有 Massive `.prices.sqlite3` sidecar。兩套尚未統一成研究用版本化行情。
- 本機 Python 3.13；本機 jsonschema 4.26.0、scikit-learn 1.9.0 可用，exchange-calendars 未安裝。Docker 是 Python 3.12 標準庫，這些本機套件**不是正式 runtime 已有相依**。

## 逐項診斷與依據

| 項目 | 狀態／已核對依據 | 設計影響 |
| --- | --- | --- |
| 取得入口／排程 | 已確認：[server.py](../../../server.py) `search_events`、[search.py](../../../news_atlas/search.py) `search_source`；[providers.py](../../../news_atlas/providers.py) `acquire`、`massive_window`、`rss_window`。目前為請求驅動；查核 news_atlas/chat/scripts 未找到每日 scheduler | 附件「已有每日更新」不等於 repo 已提供排程；外部主機排程需驗證 |
| 去重／內容更新 | 已確認：[model.py](../../../news_atlas/model.py) `article` line 58、`deduplicate` line 110，以 canonical URL hash 得 id；[storage.py](../../../news_atlas/storage.py) `save` line 110 對 `(provider,id)` UPSERT payload | 同 URL 改內容會覆蓋；無不可變 revision／變更游標，需在覆寫前存版本 |
| 漏抓與來源狀態 | 已確認：`Store.coverage`、`record_attempt`、`cooldown`、`search_source` 的 errors/warnings/cache。RSS snapshot TTL 300 秒、舊 complete 86400 秒；批次有 request/time budget | 取得狀態可重用，但不是逐文章首次可用證據；成功零篇只代表查詢窗口零篇 |
| 單股隔離 | 已確認：`Store.DEFAULT_DB` 與 schema 共用 `data/news-atlas.sqlite3`，memberships 依 query_key 隔離而非每股實體 DB | 附件「每股已有獨立 DB」與目前不符；新研究庫按股獨立，保留 legacy 新聞來源 |
| 文章證據 | 已確認：`article` 只保留清理後 title/summary（長度上限 2000/12000）、URL、來源、published_at、fetched_at；provider 並未持久保存完整 HTTP payload | 引用只能針對保存的精確文字；RSS description 常接近標題，不能假裝全文 |
| Node／Edge | 已確認：`model.build_relations` line 136 起；edge 有 source/target/type/weight/method/evidence/days_apart，type 為 shared_entity/shared_topic/similar_title | 是候選相關性，不是 SUPPORTS／CONTRADICTS；weight 不能當勝率 |
| root／branch | 已確認：[exploration.py](../../../news_atlas/exploration.py) `rank_roots`、`trace`、`explore`；[graph-view.js](../../../dist/graph-view.js) `traceMany`、`rankRoots` | 重用候選集合，不重用 edge 語義；明定輸入是哪一份凍結圖與深度 |
| 前端圖 | 已確認：[app.js](../../../dist/app.js) `AtlasRuntime`、graph-view `renderSlice`；GPU 節點預算與全量載入資料不同 | 編譯不可只從 Three.js 可見點擷取；新圖 adapter 不傳回舊建邊規則 |
| 既有快照／快取 | 已確認：`Store.save_snapshot`／`load_snapshot`、[snapshots.py](../../../news_atlas/snapshots.py) `validate_snapshot`；[graph_cache.py](../../../news_atlas/graph_cache.py) `lookup_cached`／`build_cached` | 畫面快照不是當時可交易情境；規則圖快取不是 LLM／temporal cache |
| Embedding／檢索 | 已確認：目前查核到規則／文字排名、LRU 特徵快取；未找到 embedding 寫入或向量索引 | 第一版每股 FTS／實體／時間候選即可；向量檢索屬可選後續，不可假設已存在 |
| LLM | 已確認：[chat/service.mjs](../../../chat/service.mjs) `createService`／`main`、[chat/mcp.mjs](../../../chat/mcp.mjs)：每 session 的 Codex SDK thread，工具只讀新聞／邊與操作 UI；有取消／逾時，無 durable jobs、structured extraction retry／DLQ | 重用 SDK 與安全隔離經驗，但 compiler 應有不同工作協定，不能直接給聊天工具 DB 寫入權 |
| Yahoo 日線 | 已確認：[read_prices.py](../../../scripts/read_prices.py)、`daily_prices` 欄位 open/high/low/close/adjusted_close/volume/currency/exchange/fetched_at；PK provider/ticker/day | 僅現值，可被 INSERT OR REPLACE；無 corporate-action version、修訂歷史、session calendar／完結證據。不能直接宣稱嚴格歷史行情版本 |
| Massive 日線／報酬 | 已確認：[price_lens.py](../../../news_atlas/price_lens.py) `load` line 42、`measurements` line 26：ET 時區、日線、拆股調整、6h cache，最多64區間，OHLC但未保存 volume；從第一完整交易日收盤後 N 日取平均 | 與附件「下一可交易開盤→第N日收盤」不同；需另建 labeler，保留舊視覺公式 |
| 時區／交易日 | 已確認：price_lens ZoneInfo America/New_York、由有資料的日線當交易日；未見交易所日曆或停牌資料 | DST 可重用 ZoneInfo；不能把缺行情當休市，亦不能偷偷把持有期限延長 |
| 回測／洩漏 | 缺少資料：未找到 Forecast、Outcome、walk-forward 或持倉帳本。前端 price-lens 的 forward returns／全載入區間 P95 是事後視覺效果 | 絕不可作 as_of 特徵；需 outcome 隔離與反未來資訊測試 |
| 遷移／復原 | 已確認：`Store.__init__` CREATE IF NOT EXISTS、user_version=4；不是完整 migration framework；既有 snapshot 可保存當下 payload | 新 Wiki 自己的 schema_migrations；不要讓 legacy Store 開啟新 Wiki DB |
| 測試 | 已確認：現有 Python／CJS／Chat／browser fixtures；前一輪啟動器14項通過 | 未執行的 Wiki 20項驗收都仍 pending；結構驗證不能代替 LLM 語意評估 |

## 尚需驗證與前置阻礙

1. 正式股票、交易所與 pilot 來源範圍由使用者在互動啟動時明確指定，不從截圖或主題自動推斷。
2. 舊 `fetched_at` 沒有修訂 ledger，不能還原被覆寫版本；現在導入只能標 conservative bootstrap 或明示 replay。
3. 歷史完整交易日曆、停牌、拆股與股息版本、基準指數、借券可得性均未建立；目前不能交付可信空頭可執行績效。
4. 需確認實際模型 ID／revision、歷史模型知識截止與帳號用量；有登入不等於免費或無限制。第一階段 LLM 呼叫為 0。
5. 90篇抽樣未逐篇人工驗證內容與原網頁，也未驗證價格在交易所端的正確性；只驗證存在的結構與欄位。

## 外部依據

設計借用 [Karpathy LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) 的持久 Wiki ingest/query/lint 模式；金融時間、版本與回測是本案新增契約。

[TimeSeriesSplit](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html) 提醒時間順序及等間距限制，因此不把 gap 的資料列數當成不規則事件的交易日數。[Calibration](https://scikit-learn.org/stable/modules/calibration.html) 說明 Brier／log loss 也混合區辨能力，不能單一分數宣稱校準成功。[Backtest overfitting](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf) 支持記錄研究嘗試與防過度選模的必要性。

[Sarkar／Vafa](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4754678) 的預訓練 lookahead 風險另見 [OpenReview 論文](https://openreview.net/pdf?id=fn9cJkB86T)；SSRN 直接頁面本次 403，搜尋摘要可讀。此處未宣稱透過 prompt 已消除參數記憶污染。
