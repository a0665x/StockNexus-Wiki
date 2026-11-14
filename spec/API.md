# REST、Swagger 與 MCP 邊界

入口：[PROJECT_MAP.md](PROJECT_MAP.md)。完整操作表與 request 示意保留於 [docs/API.md](../docs/API.md)，此處只提供開發定位，避免兩份巨型 API 清單漂移。

## 文件與路由

- `/docs`：本地 Swagger UI，資源在 dist/vendor，不依賴 CDN。
- `/openapi.json`：由 [openapi.py](../news_atlas/openapi.py) 即時計算 OpenAPI 3.1。
- `/api/schema` 與 `/schema/news-atlas.schema.json`：canonical JSON Schema。
- `/api/status` 與 `/api/capabilities`：DB／功能資訊，不回傳 key。

目前 29 個 API 操作（含 6 個本機 Chat 操作），分為新聞（串流／單 JSON 搜尋、唯讀快取、article observations）、純圖譜轉換（normalize/build/filter/explore/timeline）、channels/classify、snapshots/view validate。實際 dispatch 在 [server.py](../server.py)、[api.py](../news_atlas/api.py)。

## 合約要點

POST 需 application/json。一般 body 上限 16384 bytes；snapshots、classify 及 api.POST_PATHS 接受最多 268435456 bytes（256 MiB；超過明確拒絕，不截斷）。驗證錯誤 400，找不到資源 404，Content-Type 錯誤 415，建立快照 201。HTTP 200 不等於來源成功或歷史完整。

`/api/search` 是 NDJSON：cache/status/source/heartbeat/done，一行一物件。`/api/search/result` 聚合成單一 JSON，檢查 partial 及每來源 warnings/error/cache。兩者會外連並寫 acquisition cache。

`/api/cache/graph` 不外連；normalize/build/filter/explore/timeline/classify/view validate 不保存傳入文章。圖譜輸入通常全部已提供 節點、6000 邊；classify 可 2400 篇。快照按來源分區驗證，不可把 merged IDs 直接當每來源儲存格式。

`/api/graph/explore` 接 graph + query/limit，或 graph + root_ids（二選一）；結果帶 roots/evidence、各樹、shared_nodes、method。Python 排名與 JS 排名必須保持一致。當前 method：weighted_prefix_v2。這個 REST 操作供外部 client 用；瀏覽器圖內搜尋直接在本地計算，不依賴它。

## 未來 MCP

OpenAPI operationId 與 x-mcp annotations 提供候選 tools 提示，一般新聞 API 尚未包裝成 MCP；Chat 的 stdio MCP 已實作，見 [CHAT_AGENT](CHAT_AGENT.md)。包裝時保留只讀、寫 DB、刪自訂分類及外連的差異；單 JSON 搜尋適合不處理 NDJSON 的 client。REST 不遠端控制已開頁面的 DOM／相機／瀏覽器 localStorage。公開 gateway 需另有認證與授權設計。

增加 API 時同步 server 路由、api dispatch、OpenAPI request/response、驗證測試；涉及 schema 改動再更新 canonical schema 與舊快照相容性。不要只改 Swagger 畫面而未實作路由。

`POST /api/settings/massive-key`（key writeOnly）與 DELETE 用於主機明確記住／忘記，僅回 configured。SearchRequest／快照 metadata 支援 rss_region；`/api/capabilities` 提供 regions 對照。完整 OpenAPI 現有 29 個 operationId。

`POST /api/graph/build` 可傳 `articles`（全部已提供）或 `source_graphs`（google/yahoo/massive，各全部已提供，二選一），並帶可選 relation_settings。重算只讀傳入文章，不外連／不寫 DB；未知日期 null 保留為孤立點。返回 GraphPayload.relation_settings，預設 rules-v1，自訂 rules-v2，schema 同時接受兩者。快照 view.relation_settings 經同一驗證器清理並持久化；省略時 defaults。具體欄位見 OpenAPI 的 relation_settings schema。

圖譜、normalize、classify、探索與快照移除文章／連線數量的固定裁切與驗證上限；GraphPayload.display_limit 為 null，capabilities.limits.articles／relations 為 null。每條連線的規則／鄰居預算與探索樹的 roots／depth 等仍受設定約束，與文章是否保留分開。

Search stream update (2026-11-02): SearchRequest accepts `relation_settings`. `cache`
and `source` graph payloads have `relations_pending: true` and empty edges. After sources,
`phase: relations` and heartbeat events precede the final `graph` event with
`relations_pending: false`. On computation failure `graph_error` retains the prior news,
then `done` closes the stream. `/api/search/result` reports `partial: true` for incomplete
relations as well as provider coverage errors. GPU budgets are client-only.

Chat 同源代理：GET `/api/chat/status`；POST `/api/chat/session|sync|turn|cancel|reset`。
`turn` 為 NDJSON；其他為 JSON。工作階段 capability 保存在記憶體，以 Authorization bearer 傳遞。
詳細 runtime 與安全邊界見 [CHAT_AGENT](CHAT_AGENT.md)。

股價大小證據：`POST /api/prices/lens`；交易日公式、ticker 邊界與六小時快取見 [PRICE_LENS.md](PRICE_LENS.md)。

新增 `POST /api/graph/preview`（NDJSON、最多2400不同節點），搜尋可指定 `defer_relations:true`。範圍、配對計數及局部快照契約見 [視圖關聯流程](references/view-first-relations-20261104.md)。

`POST /api/graph/preview` 新增 `include_cross`（預設true）；分組畫面送false。progress/result的 `pairs_computed`／`pairs_reused` 區分新評分與快取命中，`pairs_checked`仍是掃描數。快照view新增 `render_budget`、`relation_cache_version`、`relation_scope_sources`、`relation_views`（最多12組）；細節見OpenAPI及[增量重用說明](references/view-first-relations-20261104.md)。


### Wiki 新建股票來源（2026-11-14）
`GET /api/wiki/status` 新增 `news_databases: [{instrument,ticker,articles}]`。`POST /api/wiki/plan` 與 `/apply` 支援 `news_db:true`（global scope），以已存在的對應股票新聞 DB 為唯一輸入，遵守 date_range 與 10,000 篇界限。此路徑不擷取外部新聞。

`POST /api/wiki/configure` 可在沒有活動 extraction/classification 工作時保存 `model`／`reasoning_effort`，保留日期、凍結範圍與成果，不重新建立 plan；有活動工作時拒絕。

## 情境式唯讀查詢（2026-11-14）
新增 `/api/context/catalog|news|related|prices|l1|l2`，不受畫面節點預算限制、不外連、不建立 DB／研究工作。實作 [context_api.py](../news_atlas/context_api.py)；完整使用契約與情境路由在 [獨立 Skill](../skills/stocknexus-research-api/SKILL.md) 及其 [API 表](../skills/stocknexus-research-api/references/routes.md)。Chat 新增 `read_database` 經原 session/tool capability 與瀏覽器同源取用；回應時股票切換會拒絕過期結果。既有文章／graph／Wiki 路由保留。操作總數以實際 OpenAPI 為準，本文歷史 29 個數字不代表目前總數。
