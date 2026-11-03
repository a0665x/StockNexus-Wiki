# GraphNews 可視化與 API 功能表

啟動 `python3 server.py` 後開啟 `/docs`（Swagger UI）、`/openapi.json`（OpenAPI 3.1）、`/api/schema`（統一 JSON Schema）。Swagger 靜態資源隨專案提供，不依賴 CDN。修改 Python 後需重啟 server；瀏覽器重新整理即可載入新前端。

## 可視化功能

| 範圍 | 目前功能 |
| --- | --- |
| 真實新聞 | Google／Yahoo 同步選 TW／US／HK／JP／GB 的 RSS、Massive 新聞 API；明確股票代碼、API key 說明及瀏覽器／主機獨立記憶 |
| 搜尋日期與進度 | 自訂 UTC 日期、3/6/9/12 個月快速區間；逐來源狀態、數量、完成比例及 DB 既有／新增組成色條 |
| 來源與關聯 | Google 綠、Yahoo 紫、Massive 藍；checkbox 即時篩選、混合來源或分組、來源內關聯與跨來源補充線；較弱跨來源彈簧及原有位置／距離保留 |
| 3D 操作 | 力導向佈局、滑鼠旋轉／滾輪縮放、節點拖動牽引鄰居、Ctrl＋左鍵平移相機、視角重設 |
| 探索樹 | 靠近只預覽、點擊才確認 root；Esc／空白可取消。root 鎖定後，滑過或點其他節點只預覽／查看文章，不能改 root；回到全局才能重新選取 |
| 多星系 | 圖內關鍵字搜尋 Top 1–10 roots；所有 roots 同時高亮，持續鎖定直到明確取消；各樹可共享節點，不複製新聞或創造關聯 |
| 延伸條件 | 來源內／跨來源最低 edge 分數、1–6 層深度、每節點 1–12 分支、累積路徑分數門檻；每棵樹最多 150 節點，整張圖最多 800 節點 |
| 即時光暈 | 同一 WebGL 幀投影的 Canvas 漸層；root 最亮，越深越淡；亮度／範圍／衰減／背景明暗可調；平滑退回全局；隨縮放調整吸附、拖動不丟失效果 |
| 時間 × Channel | 發布日期排序、密度格／逐篇節點切換、密度格展開文章、3D／時間軸共用 roots 與深度漸層、分類命中計數、時間大小焦點、時間軸縮放、截止日期與播放、多分類篩選、預設及自訂文字分類規則 |
| 證據與結構 | 懸停新聞預覽、詳情及原文、各 edge 的共同實體／主題／標題證據、分類命中依據、逐層展開 JSON 與標準 schema |
| 儲存與介面 | SQLite 按來源快取與日期缺口補抓、手動圖譜快照及還原（含位置／設定／多 roots）、JSON 匯出、繁中／英文、面板拖曳調寬、行動裝置面板 |

節點預設使用日期焦點：半徑依 UTC 日距離套用鐘形增益，直接上下塑形及左右調寬，profile 倍率 1–12（預設 Gaussian 最高 2）；最大倍率超過 2 後漸進補償透視，8 起完整補償，幾何固定 `nodeVal(3)`，每幀更新 mesh scale；可關閉恢復 `nodeVal(3)`，未知日期維持基準。不以重要性、報導數或關聯數決定大小。視角遠近與 root 光暈會讓它看起來大小不同。單 root 閒置 5.5 秒回到全局，按住拖拉／平移時不逾時；關鍵字多 roots 不受此計時影響。

關鍵字搜尋只查目前已載入且勾選來源的圖譜；搜尋沿用當下的來源、分類、時間截止及呈現模式，不切換模式或重建節點。它不呼叫新聞來源，也不搜尋整個 DB。每個字詞在標題／摘要／代碼／實體／主題／分類中的命中，分別加 8／2／10／6／3／3 分；英文單字有起始邊界；標題／摘要／主題／分類中的四個字母以上查詢支援詞首匹配（如 robot 命中 robots、robotics），代碼與實體仍精確匹配；中文採文字匹配，支援 NFKC 字元正規化。這是可解釋的字詞排序，沒有向量語意模型。沒命中就不選 root，不以不相關新聞湊滿 N。

各樹以廣度優先、較高分 edge 優先探索；其他已選 root 是邊界，不能被當作另一樹的分支。共享節點採離任一 root 最近的層級亮度並保留各樹父節點資訊。分數及路徑不是機率或因果。來源 checkbox 隱藏節點時，會移除不再可見的 roots，不會自動另選新的 roots。

## Schema 產生流程

1. 來源提供原始新聞；標準化標題／摘要、URL、UTC 發布時間、來源與股票代碼。清除追蹤參數後，以 URL 的 SHA-256 前 24 字元作 canonical `id`。
2. 同 URL 去重並保留 `origins`。相同標題而 URL 不同不會自行合併。
3. 明確股票代碼或文章名稱命中產生 `entities`；文字規則產生 `topics`；保留方法、欄位與命中文字。
4. 共同實體、共同主題或相似標題產生 `relations`。記錄兩端 ID、類型、權重、日期差及證據；來源內獨立建立，再補充跨來源關聯。
5. Channel 規則比對標題／摘要，加入 `channels`、`primary_channel` 及分類證據，凍結分類版本。
6. 可視化用 `view` 存來源勾選、分組、位置、時間軸、延伸門檻、光暈與 `focus`。探索 API 回傳每棵樹的父節點、深度、累積分數及共享節點。

主要結構如下（為欄位示意，非新聞資料）：

```text
schema_version
articles[]
  id / title / summary / url / published_at / fetched_at
  source { provider, publisher, via?, country?, language?, sites? } / origins[]
  symbols[] / language / analysis_version
  entities[] { id, label, method, field?, evidence }
  topics[] { id, label, evidence[] }
  channels[] / primary_channel
relations[] { id, source, target, type, weight, days_apart, evidence[] }
source_graphs { google, yahoo, massive }
cross_relations[]
channel_definitions[] / channel_version
view
  sources[] / separate / positions[] / mode
  channel_filter / cutoff / timeline_zoom / timeline_style
  exploration { internalMin, crossMin, depth, branchLimit, pathMin, maxNodes }
  glow { enabled, brightness, radius, decay, background }
  time_focus { enabled, date: UTC YYYY-MM-DD|null, peak: 1..12, width: 0.01..0.5, profile?: [129 gains] }
  focus { mode: overview|single|keyword, root_ids[], query, limit }
```

完整定義以 [news-atlas.schema.json](../schema/news-atlas.schema.json) 為準。OpenAPI 的文章／關聯／視圖元件由同一份 schema 產生。`/api/normalize` 與 `/api/graph/build` 可獨立呼叫，不必先透過 UI 搜尋，也不會抓取傳入 URL 或寫入 DB。

## 22 個 API 操作

| 方法與路徑 | operationId | 用途／副作用 |
| --- | --- | --- |
| GET `/api/status` | `get_status` | DB 統計及伺服器是否設定 key，不回傳 key |
| POST `/api/settings/massive-key` | `remember_massive_key` | 明確保存主機私有金鑰；只回 configured，不回 key |
| DELETE `/api/settings/massive-key` | `forget_massive_key` | 清除主機保存；保留環境變數設定 |
| GET `/api/capabilities` | `get_capabilities` | 可視化、來源地區及限制 |
| GET `/api/schema` | `get_data_schema` | 統一 JSON Schema |
| POST `/api/search` | `search_news_stream` | 真實來源搜尋、NDJSON 進度；更新快取 |
| POST `/api/search/result` | `search_news_result` | 相同搜尋，等完成後回單一 JSON；更新快取 |
| POST `/api/cache/graph` | `read_cached_graph` | 只讀指定來源／條件／日期快取、覆蓋及缺口；不連來源 |
| GET `/api/articles/{id}` | `get_article_observations` | canonical ID 對應的各來源原始快取記錄 |
| POST `/api/normalize` | `normalize_articles` | 原始欄位標準化、去重、實體／主題及分類；不存檔 |
| POST `/api/graph/build` | `build_graph` | 從標準文章建立來源內／跨來源圖譜；不存檔 |
| POST `/api/graph/filter` | `filter_graph` | 對傳入圖譜套來源、分類、日期、edge 門檻 |
| POST `/api/graph/explore` | `explore_graph` | 關鍵字 Top N 或指定 roots，回多棵探索樹及證據 |
| POST `/api/timeline` | `aggregate_timeline` | UTC 日期 × Channel 分桶、文章 ID／來源數量 |
| GET `/api/channels` | `list_channels` | 預設與自訂分類 |
| POST `/api/channels` | `save_channel` | 寫入自訂分類，帶 custom id 更新 |
| DELETE `/api/channels/{id}` | `delete_channel` | 刪除自訂分類；快照的凍結規則不變 |
| POST `/api/classify` | `classify_articles` | 文字分類與命中依據，不存檔 |
| POST `/api/view/validate` | `validate_view` | 驗證並清理完整快照內容，不存檔 |
| GET `/api/snapshots` | `list_snapshots` | 最近 50 份快照摘要 |
| POST `/api/snapshots` | `save_snapshot` | 按來源保存文章、關聯與視圖／roots；不更改抓取覆蓋 |
| GET `/api/snapshots/{id}` | `get_snapshot` | 還原快照 |

POST 使用 `Content-Type: application/json`。輸入錯誤為 400，未知資源 404，錯誤 Content-Type 415。API 的範例與欄位限制可在 Swagger 展開。新聞搜尋的來源錯誤可能在 HTTP 200 中回傳，務必檢查 `partial`、各來源 `error`、`warnings` 和 `cache.missing_ranges`，不能把 200 或零篇新聞當作歷史資料完整。請求 `end` 含當日；回傳 coverage 的 `end_exclusive` 不含當日。Google／Yahoo RSS 不保證完整歷史。

多 roots 請求格式：

```json
{
  "graph": {"articles": [], "relations": []},
  "query": "NVIDIA",
  "limit": 3,
  "exploration": {"depth": 3, "branchLimit": 4, "pathMin": 0.25}
}
```

將 `graph` 換成實際圖譜；或省略 `query`、改傳 `root_ids`。空圖會回傳零 roots，不合成資料。`graph/filter`、`timeline` 的篩選放在 `filters`。

## 後續 MCP 包裝

目前是 REST/OpenAPI，尚未提供 MCP transport。每個操作都有固定 `operationId` 及 `x-mcp` 的讀寫／破壞性／外部存取提示，可對映成 MCP tools。建議讀取與轉換直接包裝，搜尋明確標為會連線並寫快取，儲存／分類修改標為寫入工具。一般 MCP client 可用單一 JSON 的 `search_news_result`，不必先實作 NDJSON。

相機、滑鼠、面板寬度和瀏覽器記住 key 屬於瀏覽器工作階段；API 可處理資料與視圖快照，並不遠端控制已開啟頁面的 DOM。服務目前沒有認證，預設 `0.0.0.0` 供本機／受信任網路使用；公開部署或 MCP gateway 應在外層加入認證與存取控制。

圖內 Search 直接在瀏覽器對當下 runtime 新聞做文字排名並疊加星系，不發出 HTTP 請求、不提交表單、不重新抓新聞或清空節點。Search 與輸入框 Enter 都使用同一路徑，零筆命中保留現有圖譜與星系；點圖中空白處回到全局。獨立的 `/api/graph/explore` 仍供 API／MCP 客戶端使用。

圖內 Search v3 提供轉圈等待、掃描／命中／roots／高亮節點數量，以及空白查詢、無節點、Top N 不合法、零筆命中、錯誤、光暈關閉／零亮度、無延伸邊、視野外 roots 等提示。來源數字是各來源可用文章數；搜尋範圍是目前顯示圖譜（最多 800 節點），不是三個來源數字相加或全部 SQLite 資料。

`view.time_focus` 由 `/api/view/validate` 驗證，`/api/snapshots` 存取並由 OpenAPI 引用 canonical schema。滑動本身在瀏覽器 runtime 完成；REST 不遠端操控滑桿。快照保留來源／edge 門檻篩選後的圖，時間／channel 只保存為顯示設定，避免丟失隱藏 roots 的完整路徑。

搜尋與 cache graph 支援 rss_region：TW／US／HK／JP／GB；UI 預設 TW、Google/Yahoo 同步。API 省略時保留舊版 Google TW／Yahoo US Finance 行為。country/language/sites 為 source 的可選取得背景，快取依地區隔離且保存每個 query 的 source JSON，詳見 schema。新增地區與 key endpoints 後需重啟 server。


### 可調整的 edge 定義

`POST /api/graph/build` 現在接受 `relation_settings`：entity/topic/title 三種 boolean 開關；entity_days/topic_days/title_days（1–366）；topic_similarity/title_similarity（0–1）；internal_neighbors（0–6）；cross_neighbors（0–2）；half_life（0–366，0 關閉時間衰減）。可傳原有 articles，或 source_graphs（google/yahoo/massive，各最多 800 篇），二選一。所有孤立新聞保留；不使用 embedding／產業加權。預設完整維持 rules-v1，自訂方法標示 rules-v2，evidence 附設定、基礎分數及時間係數。半衰期使用 `2^(-相隔天數/half_life)`。回傳 relation_settings；快照與匯出 view 也保存該欄位。詳細結構由 `/openapi.json` 提供。


通用探索 B 參數：entity_days=180、topic_days=60、title_days=30、topic_similarity=.10、title_similarity=.25、title_terms_min=3、coverage_first=true，其他沿用 A。新增 title_terms_min（2–6，預設4）與 coverage_first（boolean，預設false）。覆蓋優先先匹配兩端尚無連線的合格候選，再補一端孤立者，最後按原排序填滿剩餘預算；不為缺乏證據的 pair 造邊。最大天數及 days_apart schema 上限 366，A 的原始 30／7／3 天行為不變。

## Contextual Chat

右側 Chat 的 6 個本機 HTTP 端點、工作階段 bearer 與 NDJSON 事件已列入 OpenAPI。
實際 SDK／MCP、畫面狀態、允許的 UI 操作與限制見 [Chat 合約](../spec/CHAT_AGENT.md)。

股價大小：`POST /api/prices/lens`，明確 ticker 與文章日期換算未來 1/3/5/7 交易日平均報酬，日線快取六小時。見 [股價大小規格](../spec/PRICE_LENS.md)。
