# LLM Wiki 執行與維護

入口：[PROJECT_MAP](PROJECT_MAP.md)／[研究設計](TEMPORAL_WIKI.md)。原始碼核對：2026-11-06。

## 使用流程

新聞圖與 Wiki 為獨立視圖，返回連結保留新聞節點／鏡頭。品牌圖片使用 `dist/stocknexus-wiki.png`，來源為根目錄使用者提供的同名 PNG。

覆蓋進度下只有一個「開始整理／繼續整理」主要入口，依目前顯示的日期與設定執行，不暗中延伸日期。進頁、切換設定或輪詢不建立 plan；按下後立即顯示準備狀態，依序 `POST plan` 核對快取範圍、`POST jobs` 排入未完成新聞與缺漏分類。重複點擊不重複排入。正在整理時按設定 Apply 會中斷舊工作並以新設定接續；閒置 Apply 只保存，不啟動模型。開始按鈕 hover/focus 550ms 顯示說明，離開或 Escape 關閉。

整理日期上方輸入是滑桿的固定全局邊界；兩個 thumb 共用一條軌道，在邊界內選取包含起訖日的 UTC 日期。下方顯示所選新聞的抽取覆蓋與待辦。全局來源是目前查詢 memberships＋已載入文章；重新開啟時可用已存查詢與文章，不是所有股票的全 DB。日期先過濾再套 10000 篇單次選取安全上限；不是每日限制。

固定即時區每兩秒同步 queued/running、編譯／修正／發布階段、文章日期、標題、工作進度及停止。動畫只隨真實工作狀態；離線顯示狀態未知。歷史 jobs/calls/rejected_proposals 留 DB/log，不在頁面列出。兩側／下方邊界支援拖拉及方向鍵調整，儲存於本地與主機 Wiki 工作區。

## 維護方式與證據選取

- **補新證據並檢視相依觀點**：跨模型重用已抽取 article revision；僅處理缺少／變更內容。每組取得最多 12 個相關 Wiki 節點的 title、scope、summary、assessment，包含最多 4 個直接相依 Thesis；要求模型檢視新證據是否改變舊論點，必要時新增節點以 UPDATES 指向舊節點。
- **重新檢視既有觀點**：只針對已抽取且支撐既有知識節點的新聞；每次明確開始都可重評。新節點必須以 UPDATES 指向檢索到的既有節點，否則提案拒絕；無需變更回傳空提案。不可持續自動循環。同一工作透過 reviews 防重送；不同次明確開始不再被舊 evidence_epoch 略過。未產生任何知識節點的文章不列入重新檢視。

這是**有界相關／直接相依檢索**，不是全圖遞迴重評、全文擷取、經驗因果或股票預測。模型可以判定不需變更；不以 UI 名稱假裝一定產生新觀點。

Wiki 頂部設定獨立於新聞 edge 設定。每次推論選項為 5／10／15／20 篇新聞（UI 預設 5，API 為相容舊工作仍接受 1–20），這是單次上下文大小，工作會一直處理待辦到完成或使用者停止。每組節點上限為 min(60,max(8,篇數×3))，提案關係上限為節點上限兩倍，引用可跨本組新聞；每個引用核對自己的 revision、hash、field 與逐字位置。主機自動建立來源支持連線，分組連線本身不是證據。

| 方法 | 實作 |
| --- | --- |
| 詞彙相關 | 日期最早為種子，其餘按標題／摘要詞彙重疊選取 |
| 時間順序 | 依新聞日期由早至晚的相鄰批次 |
| Graph 強關聯 root | 從同股票完整 News 圖譜自動採樣 root，依相同深度／分支／權重規則展開，直到涵蓋 Wiki 日期內全部新聞；不依賴手動點選或 GPU 渲染數，固定篇數停用 |
| 多來源融合 | 優先詞彙相關，再選不同 provider 與 graph 關聯；要求保留相反命題與引用邊界 |

所有方法都以確認的新聞範圍為準。2026-11-06 最新需求將 Graph 改為完整範圍的自動 root 覆蓋，取代先前「只用點選星河」規格。`graph_universe` 凍結當前 News 圖譜啟用來源的全部 provider/id、ticker 與 separate 模式，`graph_settings` 凍結關聯與探索規則；後端從同股票 DB 讀取並使用共用 `graph_payload`／圖譜快取重建完整關係。這是已載入的 News 查詢範圍，不是無條件掃整個股票 DB。單純 3D 渲染上限、手動 root 或 Wiki 日期不縮小取樹用圖。

`forest.py` 從 Wiki 日期內目標節點按連線權重／ID 確定性排序取 root，沿相同瀏覽器單 root 探索規則展開。若 root 的目標新聞已被前樹覆蓋便略過；仍有未覆蓋節點就繼續，包括未渲染節點與孤立新聞。各樹可以重疊，但每篇目標只計一次。整棵樹保留日期外及已處理成員作為推論脈絡；只有 Wiki 日期內尚未完成的 revision 計入工作與覆蓋。12 個月 News + 1 個月 Wiki 表示在 12 個月圖上取樹，分母僅為該 1 個月新聞。既有已處理 revision 延用，需重審時仍由使用者明確選擇。

新設定不必點選 root；有同股票完整圖譜即可 Apply。保存 universe／規則可供重開、續跑；新搜尋範圍須重新 Apply。舊版只有 graph_selection 的工作仍按原範圍續跑，不自動擴大；重新 Apply Graph 後採用全範圍模式。

Graph 每組大小由自動採樣樹決定；內容超過約 65000 個 JSON 字元的輸入預算時自動分段，不截斷文章，runtime 顯示組別／段數。每棵樹全部分段發布成功後才將其目標記入 extractions／done；中斷時保留已發布知識，但不把未完成整樹計為完成，續跑會重新處理該樹。區間外脈絡不記 extractions。單次模型總輸入仍受橋接的 200000 字元上限保護，內部 `_covered_articles` 記帳資料不送入模型。

設定順序為語系、分組方法、篇數；draft 不影響正在跑的工作。Apply 與已套用值不同時才出現。後端先驗證新範圍，再取消舊 job、停止 bridge、保留已發布版本、排入剩餘證據。舊回覆只能在 job 仍 running 時發布；被取消的舊錯誤不能停用新 config。重審續跑會略過舊工作已重審的 revision。settings_version 與完整設定保存在 config/job，切換記錄留 log。

## 模型、語系與用量

模型及 reasoning 選項來自 Codex `model/list` 的 supportedReasoningEfforts；同一下拉列出 model＋effort，主機再驗證支援度，SDK `modelReasoningEffort` 實際接收選值。無工具、唯讀 thread；不得執行新聞中的指令。一般 120 秒，高思考深度 600 秒，取消可中斷。背景只有一個模型槽；2026-11-07 起每支股票完成一棵 root 樹（含其全部分段）或一般一組證據後，即保存進度、排回 queued 並輪到下一支。queued 是等待輪替，不是停滯；running 才表示目前正在推論。重用已完成 revision／本工作 review 記錄，已凍結工作的每次輪替不重建圖譜。驗證失敗最多修正一次；缺失關聯端點會明確指出關聯序號、source／target 與原始 ID，要求只使用已提供端點或刪除該無依據關聯，保留其他有效內容。不能把缺失 target 誤報為 source 方向錯誤，也不自動猜測／補造節點。修正仍失敗則停用該股補足。重啟中斷不自動重試已開始的付費呼叫。

預設在同一次結構輸出保存 zh-Hant＋en 的 title/summary/assessment rationale、關係 rationale；設定可只保存其中一種。它們是同一命題的語言版本，不是重複節點。引用原文永不翻譯。介面語言只切換顯示，不觸發推論或翻譯。舊節點沒有翻譯時顯示原內容並註明，不能虛構已完成翻譯。`data-own-i18n` 避開主頁片段替換，避免混合「News／新增／articles」。Wiki Chat 因此必須自行完整翻譯其控制、情境與連線／回覆狀態，不能依賴主頁掃描。News／Wiki runtime 共用 `AtlasI18n.language()` 作介面語言，但 session、圖譜狀態及生成保存語系仍獨立；重連、晚回應和多視窗同步見 [CHAT_AGENT](CHAT_AGENT.md)。

jobs.payload.receipts 保留每次成功／驗證拒絕的新聞日期、usage、狀態；last_usage 顯示最近一組回報，jobs.usage 為整個工作累計。模型未回報時顯示等待回報，不估算成真實 token。區間累計計入與所選新聞日期相交的完整呼叫，每個呼叫只計一次，不按篇數分攤；跨區間數字不可相加。舊工作沒有逐批 receipts，明示未納入區間統計；逾時／網路中斷沒有 usage 時未知，不等於零消耗。不是帳號 weekly limit 剩餘額度。

## 版本、修訂與統計

版本選單與明確 version 查詢只提供最近 10 版。底層版本帳本及既有引用節點仍保留，供來源追溯、修訂鏈與資料合併使用；不刪除最新圖仍依賴的證據。as_of 保留為歷史稽核接口。每次成功的證據組發布一個版本；摘要由實際新增節點／連線、UPDATES 數量及標題產生，可查該版到底加入什麼。舊版單篇發布紀錄照常讀取。

日期唯一入口是 sidebar；其 start/end 與 version 同時有效，按來源／引用新聞日期選取，包含起迄日；先過濾再限制 2400 個載入節點，圖內再依 800/1600/2400 預算顯示。舊 as_of API 保留，UI 改為區間。新增引用影響多個日期時，節點符合任一引用日期便可納入。畫面篩選不重新呼叫模型。

UPDATES 由新節點指向舊節點，原文與既有節點不可覆寫。詳情以連通修訂鏈顯示最早原始觀點與最新三個發布 batch 的觀點；分支保留，不假裝所有修訂都是單線。無 UPDATES 的節點只顯示自己，不根據相似標題亂接歷史。Markdown 包含原文引用、語系欄位與原始／最新三批歷史。

圖下統計為所選版本／新聞區間的 Thesis 數量，以最新引用新聞日期計一次，按 direct/indirect/low/uncertain 色彩堆疊，最多 60 個時間桶；包含保留的歷史修訂，不聲稱代表當下共識。無日期資料不繪製日期柱。圖與觀點分類統計來自 DB，與 GPU budget 分開，工作發新版時更新。圖表與樹狀觀點清單共用完整 Thesis 索引，不再把所有 Claim/Event 計入觀點數。統計另受左側雙滑桿選取日期約束；滾輪縮放、拖移、鍵盤左右／加減／Home 均不能超出此區間。日期改變重設視窗。滑鼠停在色條顯示日期及數量，點擊後右側列出完全對應的觀點；清單分頁，每次展開 20 筆，詳情以 node API 讀取指定版本，不受 GPU 2400 節點上限截斷。

觀點樹依「影響管道大分類 → 主題 → 個別觀點」逐層展開。新模型輸出增加 topic（營收、營運、成本、市場、交易、其他）與 evidence（引用支持、分歧、不足）。舊節點主題暫用標題／摘要詞彙規則歸類，畫面明示，待使用者重審更新；不冒充既有模型曾做此標記。

分類、證據程度及市場反應是不同維度。2026-11-07 起，L1／L2 模型輸入不再包含未來交易日報酬，避免 outcome 洩漏；`current_market` 仍為獨立事後檢視，舊 `market_evidence` 保留供追溯，不重寫歷史。研究用價格動能需要帶可知時間的行情版本；既有快取不符合時為 unavailable。雙層研究契約見 [RESEARCH_LAYERS.md](RESEARCH_LAYERS.md)。

## 儲存、搬移與 API

`data/llm_wiki/<ticker>/wiki.sqlite3`，metadata.instrument 保留 EXCHANGE:TICKER 並拒絕同 ticker 不同交易所衝突。舊 `research/<hash>` 啟動時整個目錄 rename，含 WAL/SHM；兩份同時存在拒絕覆蓋。[GRAPH_STORAGE](GRAPH_STORAGE.md) 與 [DATA_MERGE](DATA_MERGE.md) 說明新聞分庫與聯集。

本次延伸使用既有 nodes/edges/jobs JSON payload，沒有改 SQLite 表格或版本號；雙語、batch_id、receipts 均隨原合併機制保存。版本號在匯入時映射，批次識別保持不變。不得直接覆蓋同名 DB；一致性備份使用 SQLite backup，或停服後正確複製 WAL。data/private 金鑰/socket/log 不搬進別台知識庫。

`GET status/models/graph/jobs/article/node/markdown`；graph 接 instrument、version/as_of、start/end。`POST plan` 接 instrument/model/reasoning_effort、languages、evidence_size、strategy、graph_edges、graph_settings、graph_selection、price_horizon、scope、date_range、operation 與 articles/search/sources；回傳範圍覆蓋、有效 10 分鐘 plan_id、區間 usage。`POST apply` 接與 plan 相同的範圍與設定及 continuous，閒置儲存、活動工作中斷續跑；`POST jobs {plan_id,continuous,classify_missing?}` 明確開始；`resume {instrument}` 沿用設定延伸到 UTC 今天；`cancel {instrument,job_id}` 同時停止工作及後續維護。所有寫入維持同源 Origin/Host/local-peer 防護。

原始碼：`store.py` 原子版本與引用驗證；`compiler.py` 工作與授權範圍；`workbench.py` 分組／版本摘要／歷史／用量；`forest.py` 完整圖譜自動取樹與目標／脈絡分離；`evidence.py` 舊星河相容、輸入分段、股價快取觀察；`chat/wiki.mjs` 結構化推論；`chat/service.mjs` SDK；`dist/wiki-view.js/css` 工作介面。

驗證：`test_wiki*.py`、`test_merge_data.py`、`chat-wiki.test.mjs`、`browser_wiki.py`。使用隔離 SQLite 與確定性模型回覆；實際聯集合併兩次確認冪等。正式 GOOGL 只做讀取／免費範圍核對，不因 UI 測試啟動模型。

2026-11-06 驗證：229 項完整 Python 回歸、7 項 Node Chat/Wiki、28 項隔離瀏覽器檢查通過。正式 GOOGL 實際頁面確認品牌、設定、滑桿、550ms 提示、統計及雙語；部署前後 articles/versions/nodes/edges/extractions/jobs/calls/rejected_proposals 雜湊一致（6814 新聞、324 版本、607 節點、316 連線），未呼叫真實模型。

互動延伸驗收：234 項 Python、7 項橋接、39 項瀏覽器檢查；正式 GOOGL v351 有 18 個 Thesis，圖表與分類樹只統計 Thesis（原先 300 個分類數含 Claim/Event，並非遺失資料）。實際頁面可從色條點進右側再讀取觀點及股價觀察；所有正式 Wiki 表在部署與驗收前後雜湊一致。該次提案 prompt_version 為 wiki-extract-v4。

## 2026-11-06 引用可見性與股價觀察

- 分類篩選以前移除所有 ArticleRevision，連帶使大多數 SUPPORTS 消失。現在保留符合分類的節點及實際一跳引用／相依端點，背景節點為灰色，共用渲染上限；明確的節點種類篩選仍嚴格只顯示該種類。只呈現資料中既有關係，不製造相似性邊。
- 更緊密的布局／可見連線、首次載入或切換篩選自動取景，不再提供置中／全圖按鈕；背景新版本不每次重設使用者鏡頭。獨立群數據只是當前可見圖的連通分量，並非強制分類。
- Wiki 的目前行情不再因新頁面尚未搜尋 ticker 而被上次工作 N 覆蓋。每個非新聞節點均讀取目前股價；已確認工作仍使用其原先 N，變更顯示不會暗中啟動模型重算。
- HTTP current_market 與生成時 market_evidence 分離。available_sessions / required_sessions、基準與最後價格日期讓缺資料可辨識；不將未完成窗口當零，也不宣稱必然只是尚未到期。無行情時引導回新聞圖譜更新，讀詳情本身不呼叫行情提供者或模型。

## 2026-11-06 工作畫面與跨新聞關係

- News Graph、Wiki 維持各自 renderer/runtime。Wiki show 不再用後端已套用設定覆寫使用者尚未套用的模型／日期選擇；頁面切換保存現有選取與鏡頭。Apply 先驗證新設定，才取消舊工作並接續未完成範圍。Graph 現在僅缺少同股票完整新聞圖時停用 Apply，無需點選星河；不能偷偷退回固定篇數。
- `dist/workspace.js`／`news_atlas/workspace.py` 保存兩個獨立主機紀錄，路徑 `data/private/workspace.sqlite3`。News 保存搜尋草稿、清理過的圖譜快照及鏡頭；Wiki 保存股票、控制值、星河、選取與左右欄／下方圖表尺寸。更換瀏覽器設定檔可從同一主機恢復。恢復不搜尋來源、不啟動模型。首次升級尚無快照時，先選最近使用 Wiki 的股票，從其新聞 DB 讀取現有資料；從未存入 DB 的舊記憶體畫面無法補回。
- 新聞表單股票先、關鍵字後；股票必填 `EXCHANGE:SYMBOL`，以裸 symbol 呼叫 Massive。股票變更自動置入首個查詢字詞，其餘逗號分隔文字保留可改。既有 REST 裸 ticker 仍相容。
- `wiki-extract-v5` 支援 ArticleRevision → ArticleRevision 的 RELATED_TO。每批另讀最多四篇相關已存原文，整體 context 仍最多 12 項；關係須有兩端可逐字核對引用與具體理由。Graph 模式的證據檢索限於當次樹／分段；v6 提示說明完整樹、日期外脈絡與分段覆蓋的區別。新連線由後續整理／手動重審累積，不根據同股票或畫面密度造線。
- 點選 Wiki 節點高亮實際關係三跳內、最多 150 節點的星河，其餘已渲染節點／連線變暗；不裁切資料、不重排位置、不自動縮放。僅未超過 4px 移動門檻的左鍵空白點擊解除選取；拖離再返回起點仍算拖曳，旋轉／平移保留選取。模型關係與規則 News Graph 分開，未有關係的獨立群仍保留。
- Wiki 右側獨立 Chat Agent 以目前股票、版本、sidebar 日期、選取節點、引用、關係及修訂歷史建立上下文。與 News Chat 分開 session，不自動開始推論；模型呼叫僅由使用者送出訊息或啟動整理觸發。

## 2026-11-06 執行狀態動畫

Wiki 使用與深色圖譜一致的細線文件、掃描光條與知識連線，取代早期書堆／鎬子的漫畫造型。向量資產位於 `dist/knowledge-mining.svg`，HTTP `/knowledge-mining.svg`，由 wiki-view.js 引用 base/scan/signal 分層；動畫在 wiki-view.css。輪詢保留同一 DOM，避免刷新重播；只在 running 播放掃描與訊號，排隊／停止靜止。`prefers-reduced-motion` 使用靜態圖。空圖提示位於圖譜容器內，不覆蓋較高的工作狀態欄。

## 2026-11-06 版面分隔與輸入

`dist/wiki-layout.js` 以 ResizeObserver 讀取全局 header 的實際底部，避免 Wiki 覆蓋語言／設定。桌面左右分隔線可拖寬，圖譜與下方時間圖表／分類清單的分隔線可上下拖曳；pointer capture 支援移出把手，取消／失焦恢復本次拖曳前尺寸。分隔線提供鍵盤方向鍵／Home、ARIA 數值，保留至少 260px 中央寬度與 140px 圖譜高度。800px 以下使用直向排列並隱藏把手。

尺寸存於本地及 Wiki 工作區 `layout={left,right,bottom}`，與 News 分開；新瀏覽器設定檔可還原，視窗縮小只夾住實際顯示尺寸。圖表依實際 SVG 寬高重繪軸線／色條，不拉伸文字。調整版面只更新 renderer 尺寸，不重建節點、變更選取或啟動推論。

## 外部合併與目錄刷新

顯示 Wiki 時約每 6 秒（2 秒 poll、5 秒間隔門檻）讀 status/instruments；視窗或選單 focus 立即刷新。只更新已建立 Wiki 選項，不重套模型／日期／工作設定；保留空白「建立新的股票」選項。最新版本由既有 jobs/version 輪詢載入，歷史版本維持固定。API 直接發現股票目錄，新庫不需重啟 Python。完整在線合併契約見 [DATA_MERGE](DATA_MERGE.md)。

## 2026-11-07 狀態讀取與頁面響應

- 已初始化的 WikiStore 只驗證 schema 與股票，不執行 DDL、user_version 或 metadata 寫入。新庫／不完整 schema 仍遷移，較新版 schema 仍拒絕；沒有本次破壞性 migration。
- coverage 以股票、Wiki／新聞主檔與 WAL 的檔案簽章及 UTC 日期識別快取，最長 5 秒、最多 64 股票；提交變動後失效。回傳深複本避免呼叫者污染快取；狀態不得重跑未使用的完整 review pending 查詢。
- 輪詢至多一筆在途；同條件 graph 請求合併。重進保留既有圖譜，僅版本／分類變更重讀；首載先取保存日期再讀 graph。首次 503 後重進可重試，恢復篩選值必須同步 render，晚回應仍核對股票與 request。
- 進頁及明確啟動均立即提供 aria-busy／spinner／階段文字。閒置不轉圈；poll 恢復只清掉自身的錯誤，不覆蓋其他操作錯誤。
- `classify_missing:true` 是使用者明確開始時的選項：增量 L1 沒有新新聞但舊觀點缺分類時仍可排分類；重啟、唯讀 API 或舊呼叫者不隱含啟動補分類。

## 資料先行與一個月維護驗收（2026-11-07）

使用者允許必要時重建 LLM Wiki，但先核對可救回的資料，不把舊格式缺欄位視為損壞或先清空。`python3 scripts/wiki_data_audit.py --instrument NASDAQ:GOOGL` 以唯讀交易檢查 SQLite/schema/股票識別、文章 hash、引用 span/hash、關聯端點、版本與 extraction。結果 `ready` 只代表結構／引用預檢，不代表新聞或觀點事實已確認。未來 schema、缺庫、壞引用應阻擋；舊 opinion_metadata／翻譯未記錄列 legacy，不補造、不改歷史 ID。先備份與完成正式資料預檢，才執行本輪 BDD 與模型維護。

正式驗收目標固定為 GOOGL，最近一個日曆月（本輪 UTC 2026-10-07 至 2026-11-07，含起訖日）。本輪從既有 News DB 選 2760 篇，root universe 也僅含這個月，不擴成全年、不重新抓新聞。舊成果重用；其他使用者已取消的股票工作不復活。後續換日期需明記 cutoff，不能把一次固定日期寫成永久「最近」。

`classify_missing` 將 plan.date_range 傳給 classifier。只對依賴鏈含區間內來源的舊觀點群補分類，日期以來源發布 UTC 日為準；未知日期不符合有限窗口。區間外節點可保留為該群的既有脈絡，但不因此全庫重新分類。分類仍是 exact opinion/taxonomy revision 的共享成果，不依方法另開 DB；相同 revision 已分類即重用。活動分類工作若日期不同必須停止舊工作，不能靜默沿用。僅剩分類時也保存新維護範圍，避免畫面仍顯示年度分母。

月範圍實測也暴露 root 準備成本：同一圖的每個 root 都重建／排序全部鄰接資料。`exploration.adjacency_index` 現在由 `forest.prepare` 每次只建立一次，傳給各次 trace；索引只屬於此準備請求，不跨股票或設定共用。排序、barrier、depth、branch／node budget 及覆蓋記帳不變。正式月圖的 793 棵樹與原計畫完全相同；實測邊界與數字見 TESTING。

## 舊 revision 與終止交易（2026-11-07）

GOOGL 月維護的正式模型結果揭露：相似上下文包含已有 UPDATES 後繼的舊節點，導致正確的發布 CAS 拒絕。現在候選排序與相依 Thesis 展開均排除被取代版本；歷史 ID／revision／引用不刪改，時間快照照常保留。這是「目前更新基底」的讀取規則，不是把歷史快照偷偷改成最新。模型在途仍可能遇到並行修訂，publish CAS 不放寬；拒絕時保存 proposal、usage 與 rejected receipt，保留最後完整圖且停止工作，不以舊 context 自動重試。

終止失敗與 config.enabled/catch_up=false 必須在同一 BEGIN IMMEDIATE 交易提交。原來兩次提交在停止／重啟邊界會留下 failed＋catch_up=true，讓啟動誤排第二次付費工作。本輪已取消誤建工作，沒有自動復活其他股票；後續只允許修正驗證後以原月範圍有界續跑一次，次數持久記在 private 批次紀錄。早期未記錄的模型回應／用量不能追溯補造。
