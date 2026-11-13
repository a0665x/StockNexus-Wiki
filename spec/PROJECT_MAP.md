# StockNexus-Wiki — 專案入口

全圖原始碼查核：2026-11-06；2026-11-09 對 `8285c09` 核對 Wiki 分組／分類統計、研究恢復與空資料啟動契約（不是全庫重新查核）。這是目前工作目錄的實作地圖，不代表 GitHub main 或正在執行的 server 已同步。

真實新聞搜尋與可解釋關聯圖：Google RSS、Yahoo 地區新聞（經 Google RSS）、Massive → 標準化／規則關聯 → SQLite 快取 → 3D 星系及時間軸。Python 標準函式庫後端、原生 JavaScript 前端，支援 Docker／Compose、無前端建置程序。

展示名稱 **StockNexus-Wiki**；GitHub slug **stocknexus-wiki**。現有 runtime／DB／偏好識別沿用，改名邊界見 [WORKFLOWS.md](WORKFLOWS.md)。

空資料驗收入口：[SMOKE_TEST.md](SMOKE_TEST.md)。先核對 CURRENT_STATE 的最新本機交接；歷史主機與舊工作數字不是目前資料。

本輪年度資料／L1 更新及市場報告交接：[2026-11-14 批次](references/annual-research-batch-20261114.md)。讀取即時 private ledger 後再續作，不沿用歷史工作數字。

## 新 session 的最短閱讀路徑

1. 先讀本頁、[開發協作偏好](ai-dev-experience-preferences.md) 與 [目前功能狀態](CURRENT_STATE.md)，再讀相關領域。需要操作／啟動時讀 [標準流程](WORKFLOWS.md) 與 [RUNTIME.md](RUNTIME.md)。不要先掃描資料庫或大型 vendor bundle。
2. 依下表只讀相關 Level 2 文件；再按需要深入 references。延續本次 Wiki 討論時，先讀 CURRENT_STATE 的「有效交接」，再讀 RESEARCH_LAYERS 的「已確認產品意圖與取代關係」；舊工作數字與歷史需求不能覆蓋這兩處。
3. 編輯前回到文件列出的原始碼核對；文件不取代當下程式、測試或使用者指示。
4. 修改前查看 [變更紀錄](CHANGELOG.md) 及相關事故／避坑紀錄；依 [TESTING.md](TESTING.md) 選擇回歸檢查；有新行為時更新對應 spec。

`project-spec-graph-onboarding` 共用此入口：先確認 Git 現況，再選任務文件與核對原始碼。有 `.codegraph/` 時遵循 CodeGraph-first；否則可使用既有且可用的 Graphify 索引。沒有可用圖時使用範圍限定的 `rg`，不自動建立索引。已知能力缺口見 [文件盤點](references/DOCUMENT_INVENTORY.md)，驗收依據見 [TESTING.md](TESTING.md)。

| 任務／領域 | Level 2 入口 | 優先原始碼 |
| --- | --- | --- |
| 計算定義、輸入／顯示範圍、進度與目的 | [CALCULATION_METHODS.md](CALCULATION_METHODS.md) | model.py、exploration.py、price_lens.py、wiki/forest.py |
| 操作、設定、刷新、快照、開發交付 | [WORKFLOWS.md](WORKFLOWS.md) | run.sh、server.py、dist/app.js、dist/workspace.js、news_atlas/workspace.py |
| 整體架構、資料流、模組邊界 | [ARCHITECTURE.md](ARCHITECTURE.md) | server.py、news_atlas/、dist/app.js |
| API key、來源故障、歷史範圍、缺口補抓 | [SOURCES_AND_CACHE.md](SOURCES_AND_CACHE.md) | providers.py、regions.py、search.py、storage.py、graph_cache.py、credentials.py |
| 標準文章、去重、關聯、分類、快照 | [DATA_MODEL.md](DATA_MODEL.md) | model.py、graph_payload.py、relation_settings.py、channels.py、snapshots.py、schema/ |
| 滑鼠、星系、圖內搜尋、面板、輸入保存 | [UI.md](UI.md) | app.js、graph-view.js、interaction.js、glow.js、time-lens.js、explorer-ui.js、floating-resize.js |
| Swagger、REST、未來 MCP | [API.md](API.md) | server.py、api.py、openapi.py、exploration.py |
| 本機啟動、手機、重啟、版本不一致 | [RUNTIME.md](RUNTIME.md) | run.sh、scripts/docker_launch.py、scripts/launch.py、server.py、start-tailscale.sh |
| 驗證與修改風險 | [TESTING.md](TESTING.md) | tests/ |
| L1／Classifier／Lens／L2 的延續性需求、共用圖與研究邊界 | [RESEARCH_LAYERS.md](RESEARCH_LAYERS.md)／[CURRENT_STATE.md](CURRENT_STATE.md) | news_atlas/wiki/research.py、classifier.py、dist/research-view.js、dist/wiki-view.js |
| 單股 LLM Wiki、新圖、背景維護與研究設計 | [WIKI_RUNTIME.md](WIKI_RUNTIME.md)／[TEMPORAL_WIKI.md](TEMPORAL_WIKI.md) | news_atlas/wiki/、chat/wiki.mjs、dist/wiki-view.js、dist/wiki-layout.js |

股票分庫與路徑：[GRAPH_STORAGE.md](GRAPH_STORAGE.md)。

跨電腦資料搬移與去重：[DATA_MERGE.md](DATA_MERGE.md)（`merge_data.sh`）。

## 不可誤解的現況

- 正式資料只來自真實來源。測試可隔離 mock；不能把測試資料帶入正式 DB。
- 圖內 Search 在瀏覽器對當下全部已取得節點排名，不發 HTTP、不搜尋全部 DB、不重新抓新聞。
- 搜尋涵蓋標題／來源摘要及結構欄位，**沒有抓取新聞全文**。Yahoo 可選台灣等地區；不要把版區當成出版者國籍。
- News 的 edge、分類及 root 分數是規則證據；Wiki Classifier 另有模型 assignment。兩者都不是已證實因果或投資機率；不可混為同一分類來源。
- API 回應／SQLite／匯出不得含 Massive key；明確記住時保存於瀏覽器及主機獨立私有檔。
- 左側搜尋草稿不能被圖譜操作、還原快照覆寫；快照不是日期覆蓋憑證。
- REST/OpenAPI 已存在；Chat Agent 另有工作階段專用 MCP 工具，見 [CHAT_AGENT](CHAT_AGENT.md)。

- 文章快取、完整圖譜快取、快照與 GPU 預算是不同層。3D 預設 800／最高 2400，不裁切完整結果。
- Edge settings 成功套用後保存；圖譜快取必須匹配當前文章與規則。

## Level 3 與既有文件

- [語系、重連與多視窗教訓](references/lesson-20261106-language-runtime.md)：翻譯責任、晚回應、同來源偏好同步與入口／時序驗證。

- [互動、範圍與交付教訓](references/lesson-20261106-interaction-and-delivery.md)：root 概念演進、狀態耦合、初畫尺寸、手勢、測試本身及在線匯入。

- [references/lesson-20261102-rendering-cache-settings.md](references/lesson-20261102-rendering-cache-settings.md)：WebGL 診斷限制、AAPL 出線延遲、快取／設定與預算避坑。

- [references/bugfix-20261029-webgl-fallback.md](references/bugfix-20261029-webgl-fallback.md)：Chrome WebGL 停用的證據、初始化錯誤保留、自動時間軸降級與恢復。

- [references/bugfix-20261029-floating-regions-persistence.md](references/bugfix-20261029-floating-regions-persistence.md)：水平塑形、圓形控制點、精簡浮動面板、地區快取與金鑰／日期沿用。
- [CHANGELOG.md](CHANGELOG.md)：已驗證變更與部署限制的持續 log。
- [references/bugfix-20261029-frontend-asset-startup.md](references/bugfix-20261029-frontend-asset-startup.md)：新增 JS 漏路由導致整頁失去互動，以及測試繞過 HTTP 的盲點。
- [references/lesson-20261029-curve-sculpting.md](references/lesson-20261029-curve-sculpting.md)：曲線要能局部塑形，不能把拖曲線做成整體波峰調整。
- [references/BEHAVIOR_CONTRACTS.md](references/BEHAVIOR_CONTRACTS.md)：必須保留的互動行為、過往易回歸處。
- [references/SCHEMA_AND_RULES.md](references/SCHEMA_AND_RULES.md)：ID、欄位、關聯規則、排名／多樹演算法。
- [references/DOCUMENT_INVENTORY.md](references/DOCUMENT_INVENTORY.md)：文件分工與尚未完成項目。
- [scripts/verify_docs.py](scripts/verify_docs.py)：離線檢查 spec 本地連結。
- [使用者 README](../README.md)、[完整功能與 API 表](../docs/API.md)、[DB 操作說明](../data/README.md) 保留原位。

本 spec 不保存帳號憑證、新聞快取內容、機器固定 IP、暫存瀏覽器檔或未經驗證的部署狀態。

- `scripts/storage_paths.py`：掛載磁碟發現、互動／自訂資料路徑、SQLite/WAL 驗證搬移、data 符號連結及 `.atlas-storage.json`。

- [CHAT_AGENT.md](CHAT_AGENT.md)：右側聊天、主機登入橋接、runtime 情境與 MCP UI 操作。
- [PRICE_LENS.md](PRICE_LENS.md)：明確 ticker 的交易日平均報酬、混合大小、股價快取與快照。
- [TOOL_DOCK.md](TOOL_DOCK.md)：右側工具停靠、可調整分隔線、版面保存與拖曳邊界。

- [RESEARCH_LAYERS.md](RESEARCH_LAYERS.md)：L1／分類／Lens／L2 垂直流程、BDD 邊界、API、遷移與限制。

Chat L1／L2 證據整合與日期、MCP、表格驗收：[CHAT_RESEARCH_BDD.md](CHAT_RESEARCH_BDD.md)。
