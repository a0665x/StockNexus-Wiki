# 來源、搜尋與日期覆蓋

入口：[PROJECT_MAP.md](PROJECT_MAP.md)。原始碼：[providers.py](../news_atlas/providers.py)、[search.py](../news_atlas/search.py)、[storage.py](../news_atlas/storage.py)。

## 來源合約

| provider | 取得方式 | 實際限制 |
| --- | --- | --- |
| google | Google News RSS，可選 TW／US／HK／JP／GB | 搜尋索引快照，不保證完整歷史 |
| yahoo | Google RSS，與 Google 共用所選地區，限制當地 Yahoo 網站 | 不是 Yahoo 官方 API；TW 使用 `tw.news.yahoo.com` |
| massive | `api.massive.com/v2/reference/news` | 明確 ticker、帳號 key／授權；歷史範圍依帳號 |

取得 `description` 作 summary；不另抓文章全文、不依操作者所在地自動切換新聞語系。NVDA 的查詢不能保證召回每篇 NVIDIA 產品報導。

`normalize_request`：query 最長 200、ticker 最長 20，ticker upper-case；query 空白時用 ticker。Massive 不從任意 query 推測 ticker。單選 Massive 無 ticker 會拒絕；混合來源缺 ticker 時以該來源錯誤事件略過，其他來源仍可工作。

## 時間與預算

UI/API 請求 end 含當日，內部正規化為 UTC `[start, end_exclusive)`。預設最近 7 日，每次最多 366 日、不得超過今天。快速 3/6/9/12 月依日曆月回推；不是來源保證的歷史長度。

每來源單次補抓最多 12 requests／約 90 秒 budget；每次網路讀取 timeout 15 秒，回應上限 8,000,000 bytes。不是一次保證抓完全年。Massive 頁面最多 1000、next_url 驗證目的地及 path；不得把 key 轉送任意網址。RSS 長區間先拆成最多 31 天窗口，以佇列先走訪整段期間，再細分 ≥100 篇的窗口；一天仍達上限則不標覆蓋。未達 100 也只是索引 snapshot，不能推定歷史完整。

## 快取與缺口

UI 明確傳送 `rss_region`（預設 TW），API 省略時保留舊版 Google TW／Yahoo US Finance 行為。鍵包含 provider、adapter／locale version、query：Google TW 沿用 `rss-v2:zh-TW:`，其餘明確地區使用 `rss-v4:<國別>:<語系>:`，舊版未指定 Yahoo 沿用 `rss-v3:en-US:`，Massive `massive-v2:` 不受地區影響。改來源範圍／語系要考慮換版本，不可把舊覆蓋用作新來源已讀完的證明。

- `membership_origins` 以 `(provider,query_key,article_id)` 保存取得時的 source JSON；相同 URL 不同國別不互相覆寫。文章 `origins` 累積全部觀測來源，save 用 BEGIN IMMEDIATE 保護並行合併。
- `memberships` 決定查詢有哪些文章；不能把同 provider 的全部 DB 混當查詢命中。
- `coverage` 按 UTC 日保存 `complete` 或 `snapshot`，依成功請求的窗口建立，**不能從文章日期推算覆蓋**。
- Massive 當時可存取分頁讀完，包括零篇，才可標 complete；不是世界上所有新聞完整。
- RSS 是 snapshot；最新日／RSS 新鮮度 300 秒，較早 complete 日 86400 秒。
- 過期日或未知日形成 missing_ranges；只補缺口。force_refresh 覆寫補抓範圍，但不繞過限流。
- 分頁／預算／授權錯誤仍保存已取得的好資料與已完成窗口。attempts 記錄錯誤碼／retry_until。
- 手動 save snapshot 不修改 acquisition coverage。

`./run.sh local --offline`（`NEWS_ATLAS_CACHE_ONLY=1`）使搜尋只讀目前 DB，包括過期快取；即使 force_refresh 也不呼叫 provider。回應保留 missing_ranges 並附離線警告，不能把離線結果當成完整覆蓋。查詢仍依精確 query_key 配對，例如 TSM 與 TSMC 是不同查詢。一般啟動保留原有自動補抓行為。

## 搜不到新聞的排查順序

1. 查看左側 query／ticker、來源語系和日期；區分 Yahoo Finance 與台灣 Yahoo。
2. 查看各來源 error、warnings、missing_ranges、cached/new，而非只看 HTTP 200 或完成比例。
3. 區分各來源筆數、總 DB 筆數與目前圖上全部已取得節點。
4. 確認文章是否已取得，關鍵字是否在標題／摘要；未抓取的全文不能被本地匹配。
5. 需要特定產品時可用左側產品名稱搜尋取得資料；圖內 Search 不補搜。

Microduck 案例（2026-10-28 查核）：提供的新聞屬台灣 Yahoo；當時本地標題／摘要沒有 Microduck／機器鴨。這是歷史觀察，不是永遠零筆的系統規則。目前已支援台灣 Yahoo 地區搜尋；全文擷取仍未實作。

國別對照的單一後端定義：[regions.py](../news_atlas/regions.py)。`source.country/language/sites` 描述索引版本及網域限制，不能當成出版者國籍或文章實際語言；舊快取不捏造缺失欄位。Google News 的[官方語言／地區說明](https://support.google.com/googlenews/answer/7688469?hl=en) 描述選擇概念，但不保證 RSS 的日期完整性或所有國家的可用性。

## 2026-11-02 跨年查核

- 正式 SQLite 唯讀統計：2025 年來源紀錄 google 454、yahoo 1047、massive 1455，共 2956；不是跨來源去重文章數。
- NVDA／2025-11-03～2026-11-02／Google TW、Yahoo TW、Massive 的現有快取：舊最新優先 800 個全為 2026；修正後前後端月份取樣共 800 個，其中 2025 年 97、2026 年 703。取樣不改 acquisition DB。
- 實際 RSS，NVDA/TW：單次全年 Google 72 筆，窄查 2025 年末 47 筆；Yahoo 全年第一批 100 筆全為 2026，窄查 2025 年末 33 筆。因此跨年有資料，但寬區間召回偏差不能當成沒有舊新聞。
- 新分段策略實測各 12 requests：Google 379 個去重 URL、Yahoo 835 個，均含 2025-11 到 2026-11；分別 11／4 個 snapshot 窗口，均仍有 limit／待補窗口，未宣稱全年完整。僅讀來源，不寫正式 DB。
- Massive 未另外使用使用者金鑰發請求；正式快取已有 2025 紀錄，測試涵蓋跨年 published_utc.gte/lt、asc 與 next_url。官方 [News](https://massive.com/docs/rest/stocks/news)／[歷史範圍](https://massive.com/knowledge-base/article/how-far-back-does-massives-news-and-sentiment-data-go) 列出 Basic 兩年、Starter 以上全歷史；本次不宣稱重新驗證帳號授權。

### 最終行為：完整呈現，取消取樣

使用者要求如實顯示後，已移除原 800 裁切及中途測試的月份取樣。相同 NVDA 快取驗證：Google TW 558、Yahoo TW 558、Massive 5990，混合圖共 7106 個唯一節點，2025 年 1009、2026 年 6097，後端／前端全部保留。上述 97／703 是中途取樣方案的診斷對照，不是最終行為。來源仍有自身索引／授權／請求預算限制；完整呈現指全部已取得資料，未完成來源區間會明確標示。

關聯計算預先解析時間與詞集合，利用日期索引排除不可能符合時間窗的配對，只在選定連線時建立 evidence；自適應只枚舉仍需補線的孤立端點。240 組隨機對照與原規則完整一致。沒有以節點抽樣替代效能改善。

## 持久圖譜計算快取（2026-11-02）

`news_atlas/graph_cache.py` 包住搜尋最後建圖及 HTTP `/api/graph/build`、`/api/cache/graph`。
完整的有序文章內容、分類定義、正規化關聯設定與 `graph-v1` 演算法版本共同產生 SHA-256 鍵；
不使用 query 字串作為圖譜正確性的憑證。內容、順序、分類或設定變動皆 miss。
修改標準化／分類／關聯語義時必須提高 VERSION。

壓縮後完整圖譜保存於 `<NEWS_ATLAS_DB>.graphs.sqlite3`，獨立於新聞／coverage／快照表。
這是可丟棄的衍生資料；快取讀寫／損壞失敗回到正常計算。保留最近使用的至多 32 組、
合計至多 256 MiB 壓縮 payload；SQLite 檔案可保留空閒頁供重用，這不是實體檔案硬上限。
超過預算的單一圖譜不保存。服務重啟仍可命中。資料搬移時此檔隨 data 一起保留。

同程序、同 DB、同 key 的在途請求共用一個 Future；各呼叫者的結果物件獨立，
計算失敗會通知等候者並解除登記，後續可重試。跨程序只共享持久結果，不宣稱跨程序合併。
搜尋仍先送文章，再補來源缺口，最後命中／計算完整關聯；不跳過來源新鮮度檢查。
尚未實作文章配對增量快取、閒置預算佇列或前端排列優化。

服務日誌 `graph_cache` 含 hit/miss/shared/uncached、文章數、鍵計算／讀取／計算／編碼／寫入／總耗時。
`graph_compute_ms` 記錄各來源、來源配對與全局的關聯耗時；均不輸出文章或憑證。

### 優先送出完整快取圖譜

搜尋初始讀取與來源完成輸入皆以每來源 `deduplicate` 正規化，避免初始 raw DB rows 與
`search_source` 回傳的 enriched rows 使用不同快取鍵。第一個 cache event 先 `lookup_cached`：
只讀已完成圖譜，不等在途計算、不在 miss 時計算 edges。命中便立即送出既有節點及線，
再做來源新鮮度補抓；來源完成時也優先讀取相同輸入的快取。

新文章使完整快取失效時，`retain_known_edges` 只保留兩端文章內容完全相同的舊證據，
新節點照常出現。暫存線仍帶 `relations_pending=true`，不是新版度數預算的最終選線；
最後完整計算替換，失敗則保留可用資料。前端明示既有關聯保留、新資料仍在更新。

實體／主題與分類各使用 8192 項記憶體 LRU，按實際依賴的 title/summary/symbols 或分類定義
快取純衍生特徵；每次回傳複製，來源、fetched_at 等 metadata 沿用當下文章，不被快取覆寫。
這不是持久文章配對快取，也不是閒置全 DB 預算服務。

配對評分快取：主DB旁的 `.pairs.sqlite3` 保存內容／規則版本對應分數及無關聯結果，與文章取得快取、完整圖譜快取分開。縮小／擴大視圖可重用；淘汰策略與快照攜帶範圍見[增量重用說明](references/view-first-relations-20261104.md)。
