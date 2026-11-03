# 變更與驗證 log


## 2026-11-03 — Contextual Chat Agent

- 右側新聞／Chat 滑動面板、連續對話、新對話、取消、複製與錯誤狀態。
- 主機 SDK 登入橋接、Unix socket 代理與 session 專用 stdio MCP。
- 結構化 runtime、新聞／關聯分頁、版本檢查及既有 UI 控制項操作回報。
- 不改寫新聞 DB；詳見 [CHAT_AGENT](CHAT_AGENT.md)。

入口：[PROJECT_MAP.md](PROJECT_MAP.md)。只記錄已完成的工作區變更；不表示執行中的 server 或 GitHub main 已同步。新增紀錄置頂，事故證據放 references；不記錄金鑰、完整 localStorage 或新聞 DB 內容。

## 2026-10-29 — WebGL 錯誤診斷與時間軸降級

- 使用者 Console／chrome://gpu 確認 WebGL 初始化失敗；底層 GPU 停用原因仍需用戶端排查。
- 修正吞掉初始化錯誤、將錯誤覆寫成「無新聞」；新增中英診斷與 context lost／restored 處理。
- 無 WebGL 時自動切換 SVG／DOM 時間軸並保留資料、關聯搜尋；恢復後可手動返回 3D。
- 77 Python tests、16 CJS 檔及實際 Handler browser startup 通過；782 篇真實快照在正常／停用 WebGL 瀏覽器驗證，降級後仍能召回 3 roots。
- 前端刷新即生效，已比對線上 app.js；未推送 GitHub，未宣稱使用者 GPU 已恢復。
- [證據、回歸與排查紀錄](references/bugfix-20261029-webgl-fallback.md)。

## 2026-10-29 — main 發布整理

- 以遠端 `6b156ef` 為基準，整理曲線塑形／寬度與透視補償、浮動小圖示、RSS 版區與 SQLite 4 來源背景、獨立本機金鑰、互動式 run.sh，以及首頁初始化修復。
- 在乾淨 checkout 驗證：77 個 Python tests、15 個 CJS 檔、spec 本地連結、run.sh 語法與 diff whitespace 檢查通過。
- 發布內容僅包含程式、測試、README、schema 與 spec；不包含新聞 DB、私有金鑰、瀏覽器回放／截圖或暫存產物。
- 下載更新後須重啟 Python 並刷新頁面，才會載入新增 API 與 DB 遷移；遠端發布狀態以 GitHub commit 歷史為準。

## 2026-10-29 — 水平調寬、可搬動小圖示、RSS 地區與常駐金鑰

- 曲線增加水平單側／雙側寬度操作，控制點以畫面尺寸保持圓形；保留局部塑形、復原及原圖狀態。
- 來源與時間焦點都支援 36px 小圖示、拖動、點擊展開、▽ 收合、↺ 歸位。
- Google/Yahoo 共用地區下拉，TW／US／HK／JP／GB；國別／語系／網站背景進 source JSON、快照與 SQLite query context。SQLite 4 自動新增表及索引，舊資料不刪、不硬補國別。
- key 由瀏覽器與主機私有檔沿用；新增兩個 write-only 設定 API，OpenAPI 共 22 操作。Quick range 立即同步起訖，重複點選也更新。
- 驗證：77 Python tests、15 CJS 測試檔、正常／缺模組 browser startup 及真實快取 800 節點回放通過，已檢視精簡面板截圖；台灣 Yahoo RSS 實測回傳 82 個真實索引 item。完整證據與未驗證範圍見下方紀錄。
- 新後端與 DB migration 需要重啟 `./run.sh`；本次未推送 GitHub。
- [本輪 red→green、遷移與避坑紀錄](references/bugfix-20261029-floating-regions-persistence.md)。

## 2026-10-29 — 直接塑形曲線、補齊事故紀錄

- 移除波峰／波寬滑桿，改成抓取曲線任意段上下拖曳，局部平滑塑形；提供日期／倍率提示、鍵盤、復原與重設。
- 自訂曲線跟隨日期焦點，保存於瀏覽器、JSON 與分來源圖譜快照的 `view.time_focus.profile`；舊 Gaussian 快照相容。
- 同步前後端驗證、標準 schema、API capabilities、i18n、README 與 spec。
- 檢查：70 Python tests、14 CJS 檔、正常／缺模組瀏覽器初始化、真實快取 800 節點回放與截圖通過。測試不改正式 DB，不以 mock 通過宣稱上游來源可用。
- 部署：新 snapshot validator 需要重啟 Python，前端刷新；本次未推送 GitHub，也未代替使用者重啟現有 server。最後由本執行環境探測預設 `127.0.0.1:8765/time-lens.js` 得到 curl exit 7（無法連線）；不能推斷使用者是否改用其他 port，亦不宣稱 live 驗收通過。
- 詳細：[曲線塑形的設計修正與驗證](references/lesson-20261029-curve-sculpting.md)。

## 2026-10-29 — 修正首頁全部互動失效

- 根因：新增 time-lens.js 漏登記 HTTP 路由，app 初始化在事件註冊前中止，連帶讓搜尋／語言／Massive 說明失效。
- 修復：補靜態路由、缺可選模組時保留基本功能；首頁資源自動遍歷及瀏覽器 smoke 改走實際 Handler。
- 避坑：直接從磁碟嵌入 JS 的測試無法驗證部署資源路由；只刷新頁面不會更新 Python 記憶體中的路由。
- 詳細：[失敗證據、修復、測試及部署注意事項](references/bugfix-20261029-frontend-asset-startup.md)。

## 2026-11-02 — 容器部署與浮動面板避讓

- 加入 Dockerfile、compose.yaml、.dockerignore、.env.example；run.sh 新增 up/down/build/restart/logs/status 並保留原本 Python／Tailscale 參數。單一 SQLite 服務、既有 data bind mount、健康檢查、非 root、唯讀程式目錄、日誌輪替；server.py 接收 SIGTERM。尚未實作多副本擴容。
- 面板非互動空白可拖曳；同 stage 的兩面板保持 8px 間距，包含折疊、展開、歸位及尺寸重算。空間不足時先收另一面板，再視需要收目前面板。控制項不觸發面板拖曳，位置與收合狀態持續保存。
- `node tests/test_floating_panels.cjs` 先以缺少面板 pointerdown 失敗，修正後通過；原本只綁 handle 且未協調兩工具位置是原因。完整 17 個 CJS、77 個 Python 測試通過。browser_startup 增加空白拖曳、輸入框隔離、展開／收合碰撞驗證。
- Docker 實際建置成功；隔離 Compose 專案通過健康檢查，首頁、JS、status、OpenAPI、docs 均 HTTP 200；獨立測試 SQLite application_id 重啟後保留。測試容器及網路已移除，未啟動或修改正式資料庫。主機 Snap Docker 的 no-new-privileges 選項會令 python --version 回 operation not permitted，故不預設該選項。
- 右上角設定區與 edge 算法僅提出概念，等待使用者同意，未變更規則或加入 embedding。


## 2026-11-02 — 可解釋、可切換的 edge 定義

使用者確認所有孤立點保留，需求是能理解及切換 edge 的定義方式。

- 右上角事實標語改為關聯設定；原始／同一實體／共同主題／相似標題預設與自訂開關、窗口、Jaccard、連線預算、可選時間半衰期。列出目前與待套用規則、公式、優先順序；A/B 比較新增／移除／重新定義或計分的連線。
- 後端同一 build_relations 核心支援 relation_settings，預設完整維持 rules-v1，自訂標示 rules-v2；不加入 embedding 或產業加權。每條線保留規則、原始分數、時間係數。API `/api/graph/build` 支援來源分區輸入，純重算、不抓新聞或寫入 acquisition DB。
- 前端只替換連線與設定 metadata，保留文章陣列、3D node 身分、位置及 roots。全部規則關閉也保留孤立節點。新資料／快照會作廢舊請求；錯誤保留舊圖與正確的已套用標示。快照／匯出保存設定，舊快照以預設讀取而不重算凍結連線。
- 已套用設定與 B 草稿分開保存；設定 dialog 開啟時暫停單 root 閒置退出，Esc 關閉不清 root。英文與繁中介面同步支援。
- 驗證：82 個 Python tests、18 個 CJS 檔通過；browser_relations 透過實際 Handler 取得 11 個 assets 及 graph/build 回應，確認 A/B、孤立點、node identity、roots、快照設定、錯誤保留、每條線證據，全部 PASS／零 JS errors。browser_startup 搜尋、地區、語言、面板避讓亦 PASS。測試資料隔離，未改正式新聞 DB。
- 更新須重啟 Python；Docker 使用 `./run.sh up` 重建，再刷新瀏覽器。


## 2026-11-02 — Docker 互動與單實例、原生圖示點擊、通用 B

- `run.sh up` 委派主機標準函式庫的 docker_launch.py：固定 project news-atlas 與 HTTP 8765、主機 flock、驗證資料／port／專案來源目錄，異常殘留 scoped cleanup，健康單例沿用或更新，--scale atlas=1，健康檢查及 URL。其他 port owner 不終止；build 失敗不停止舊服務。安裝且登入 Tailscale 才詢問 HTTPS，沒有安裝不詢問；非互動默認不新增路由。自己建立的背景 Serve 有所有權記錄，down 不全域 reset。
- 真正 Chromium Input 重現兩個圖示點擊都不能展開：pointer capture 使 click target 變為 panel，原程式僅 handle.onclick。新增 panel 的 collapsed click；保留拖曳抑制，避讓可移開另一小圖示以優先展開正在操作的工具。
- 原生 select 的 input 冒泡會先執行 draft()，把新選項改回舊值，再讓 change 讀到錯誤選項，造成 B 未套用、A 看似無變化。select input 不再重寫草稿，由 change 套用預設。A/B 可取消在途舊請求後切換。
- 30 天為原始規則的人為限制，不是模型能力上限。自訂窗口及 schema days_apart 放寬到 366；A 的 30／7／3 天及計分保持不變。通用 B：entity 180 天、topic 60 天／.10、title 30 天／.25／至少3詞、coverage_first。先以合格候選匹配尚無連線者，再補邊；不刪新聞、不硬造邊，沒有 embedding 或產業分類加權。
- 唯讀本機快取，最新 1200 rows 去重取 800 篇、按實際來源內及跨來源圖合併：A 1797 edges／348 isolates，B 1941 edges／256 isolates；同批文章不變、少92孤立點。此數字僅代表這批樣本，非所有搜尋的承諾。
- 原生瀏覽器：兩工具 restore、drag-stays-compact、restore-after-drag，select、B→A→B 全 PASS。startup 搜尋／地區／語言／避讓亦 PASS。新增 9 個 Docker launcher tests（含 PTY）。實際更新既有 news-atlas 後再次 up，單一容器 ID 0f786780a0d5 不變、healthy、固定 127.0.0.1:8765；未新增／修改實際 Tailscale 路由，未停止其他專案。

## 2026-11-02 — 單一自適應關聯與資料磁碟選擇

- UI 移除 A/B、教學段落及成功統計，改單一套用、spinner／progress、靜止 2 秒淡出的欄位 tooltip；清楚區分重新抓取與圖譜快照。
- adaptive 保留嚴格邊，再以寬條件補有證據的孤立點，保留所有文章與連線預算；舊 API 預設及凍結快照相容。
- run.sh 預設 Docker up，啟動檢查其他已掛載硬碟與可用容量，保留自訂入口；確認後驗證複製 SQLite/WAL 與檔案、data 符號連結及路徑保存。原資料備份保留，缺席磁碟不回退系統碟。
- 原生 Chrome 驗證工具圖示展開／拖曳、單一套用及 tooltip 時序；HTTP fixture 回放驗證節點身分／roots／快照與錯誤保留。正式資料未搬移；額外硬碟採模擬掛載測試。

- 最終驗證：103 個 Python tests、18 個 CJS 測試檔、spec 連結與 shell 語法通過；新版映像部署後恰好一個 healthy 容器，127.0.0.1:8765，實際 HTTP 首頁確認 unified 控制與 progress。正式 data 路徑維持原位置。

## 2026-11-02 — 時間軸簡化與跨年資料查核

- 移除呈現方式／播放，固定密度格；Channel 右側 −／滑桿／＋與倍率，保留可視時間中心。密度格刻度由 MM-DD 改完整 YYYY-MM-DD，避免跨年混淆。自訂分類入口直接定位表單。
- 重現最新 800 筆裁切漏掉舊年的問題，後端與前端改按月份分配／月內分散取樣，保留資料庫與已存快照。現有 NVDA 快取重播：舊 800 全為 2026，修正後 97 個 2025／703 個 2026。
- RSS 每段最多 31 天，佇列先走訪整段再細分滿額區間，維持每來源 12 requests／90 秒及不完整覆蓋語意。實測與來源限制詳見 SOURCES_AND_CACHE。
- 跨年回歸先捕捉 2025 節點遺失及深度優先耗盡預算，再修正；UTC／RSS／Massive／SQLite 邊界驗證，原生 Chrome 完整年份、縮放與分類入口驗證。

## 2026-11-02 — 完整呈現、來源調色盤、英文啟動檢查

- 依最新需求移除 800 節點限制與中途月份取樣；前後端、重算／分類／探索／快照／OpenAPI 同步取消文章數裁切，256 MiB HTTP body 超過則報錯。完整現有 NVDA 快取為 7106 節點（2025:1009、2026:6097）。
- 日期索引與延後建立 evidence 改善全量關聯成本；240 組隨機對照原始／自訂／自適應／跨來源規則結果一致。
- 搜尋來源新增個別調色盤與重設，保存瀏覽器偏好並同步各視圖色標；forceRefresh 初始化 false，不持久保存。
- run.sh／Docker／local／storage 選單與訊息英文，加入明確 runtime／Docker／port／storage write/fsync／DNS-TLS-HTTPS 及 Tailscale 檢查，保留 scoped cleanup 與資料。

- 最終檢查：全量 API／瀏覽器及來源配色回歸通過；正式 NVDA 快取 7106 節點、20602 條全局自適應邊的冷計算約 80 秒（本機測得，不是效能保證）。相同輸入關聯快取最多 8 組並以 deepcopy 隔離，關聯等待上限 5 分鐘／搜尋等待 10 分鐘；不藉由抽樣縮短計算。

- 交付驗證：111 個完整 Python 測試及新增快取隔離回歸通過、18 個 CJS 檔通過，原生 Chrome 全量節點／調色盤／預設刷新與時間軸操作全通過，HTTP 首頁初始化零 JS 錯誤。正式容器 healthy、127.0.0.1:8765，capabilities 的 articles／relations 上限為 null；未搬移正式 DB。

## 2026-11-02 — Recoverable 3D and observable asynchronous actions

Fixed permanently disabled Graph after renderer failure. Split news streaming from
final relation calculation so first news does not wait for edges. Preserve view during
search/apply, expose progress and cancel, reject late cancelled responses. Add independent
root/channel constellation modes. Default GPU-only budget 800 nodes/2400 edges with
100-node floor on progressive failure reduction and manual renderer reconstruction.
Complete search/timeline/export data remains intact. Added real Chromium user journeys
including actual context loss; see TESTING.md.

### Follow-up — persistent failure fallback and mode switch

Reproduced that persistent WebGL failure still prevented entering Graph despite a retry
button. Added a real Canvas 2D graph fallback and visible error reason; hardened renderer
cleanup against exceptions. Verified both injected failures and Chrome with WebGL disabled
at startup. Replaced root/category buttons with the requested sliding switch labels.
This does not claim to repair the user's browser/GPU configuration; 3D retries remain
available while graph data can be explored independently of WebGL.

### User correction — remove unsolicited 2D fallback

Removed the Canvas renderer, asset route and fallback behavior. Keep graph 3D-only,
raw error reporting, retry cleanup fixes and Single selection / Group rendering switch.
Actual failure cause in the user's browser is not established by generic status text.

## 2026-11-02 — 持久圖譜快取與相同計算合併

- 新增獨立 SQLite 壓縮圖譜快取，完整輸入／分類／規則／版本雜湊；重啟可重用。
- 搜尋最終建圖與 HTTP 建圖／快取 API 共用入口；程序內相同計算合併，結果物件隔離。
- 32 組／256 MiB 壓縮 payload 預算，快取故障回退正常計算，不改新聞 coverage 或既有 edge 規則。
- 新增來源／跨來源／全局計算及快取階段耗時日誌。
- 本階段尚無背景配對補算或前端物理排列改動。
- 驗證：120 個 Python tests、spec 本地連結通過。唯讀最新真實 NVDA 快照，於隔離暫存快取計算：8,388 來源紀錄／8,387 去重文章、22,948 全局 edges，cold 42.308 秒；清空既有記憶體 LRU 後 disk hit 1.809 秒（約 23 倍）。此為單次本機後端建圖量測，不含來源抓取、HTTP 傳輸及瀏覽器渲染，也不保證所有搜尋相同比例。
- 已透過 `./run.sh up --non-interactive` 建置更新現有 news-atlas，單容器 healthy，原 data 與 Tailscale 路由沿用。正式 `/api/cache/graph` 以既有 Google NVDA 七日資料驗證：98 篇／283 edges，首次 HTTP 0.194 秒、再次 0.023 秒，完整兩份回應相同；日誌確認 miss→hit，供應商請求數為 0。

## 2026-11-02 — AAPL 首屏關聯提前與特徵重用

- 使用者重複搜尋已有 DB 文章，但 edges 仍等待。日誌顯示兩次來源數 3932→4057，完整圖快取 miss，建圖約 15 秒；原串流即使命中也等來源補抓後才讀關聯快取。
- 新增早期只讀 lookup：初始輸入與來源完成統一每來源正規化，第一個 cache event 即可帶完整 edges。來源補抓不中斷既有圖譜；只有兩端文章內容完全相同才保留舊證據，標記 pending 並於最終計算替換。
- 重用實體／主題／分類純特徵，保留目前文章 metadata 並隔離可變結果；兩個 8192 項 LRU。
- 回歸先重現 warm edges 首事件為空，再通過；新增變動端點不沿用舊證據與特徵／定義失效測試。124 Python tests、全部 CJS、真實 Chrome 搜尋／取消／3D 恢復流程通過。
- AAPL 現有快取複製到暫存 DB，禁止 provider 與關聯計算，首事件約 2.25 秒帶回 4057 來源紀錄／3804 去重文章／10738 全局 edges。此為本機 generator 時間，不含 HTTP 傳輸及瀏覽器渲染。正式 DB 未作測試寫入。
- 已更新現有容器，單實例 healthy。容器內以正式 AAPL 的最新儲存設定驗證首個事件，強制禁止 provider 呼叫及 edge 重算：2.105 秒、3804 nodes／10738 edges、pending=false。這是 generator 驗證，未自動重新抓取新聞；前端更新需刷新頁面。

## 2026-11-02 — 2400 渲染預算與偏好忠實還原

- 新增 1200/1600/2000/2400 節點選項，預設仍 800；GPU-only 顯示切片上限同步，完整資料不裁切。
- 故障減半選擇現有下拉選項，避免 2000→1000 或 1200→600 產生不存在的選項。
- 移除會將明確保存的 original/general 偏好改寫成 unified 的舊遷移；只有無保存值才用 unified。
- 渲染預算／設定保存及後端規則快取回歸通過；瀏覽器 journey 增加 2400 節點再回 800 的實際圖譜驗證。

## 2026-11-02 — StockNexus-Wiki 文件整理

- README 改為簡潔專案介紹與操作入口，展示名稱 StockNexus-Wiki／repository slug stocknexus-wiki。
- 新增 WORKFLOWS 與渲染／快取／設定 lesson，更新架構圖及索引，修正 Yahoo、來源配色、forceRefresh、GPU 預算與偏好遷移的過時描述。
- 命名只作用於文件；未改既有容器／DB／localStorage 識別，也未宣稱 GitHub 儲存庫已改名或推送。
- 文件修改不需重建服務；以本地 Markdown 連結與原始碼核對驗證。

## 2026-11-03 選中新聞、語言與股價大小

- 選中新聞置頂紅框；右側 Chat 控制文字與輸入提示隨中英文切換，原新聞／對話不翻譯。
- 新增 1/3/5/7 交易日平均報酬與時間混合大小，預設時間 100%；股價來自明確 Massive ticker，缺失沿用時間大小。
- 日線快取與快照證據獨立於新聞關聯計算；方法、限制、回歸見 [PRICE_LENS.md](PRICE_LENS.md)。

## 2026-11-03 股價對齊與工具停靠

- 新增真實 OHLC K 線、未來 N 日累計平均線與後續遮罩；與時間曲線共用垂直游標，點新聞同步定位日期。
- 配色可選美股／台股慣例；快照保存 OHLC，舊快照不偽造 K 線。
- 兩工具可拖到右側停靠或拖回，工具／新聞區域及兩工具邊界可調整；版面偏好保存。
- 修正工具收合圖示與上方導航互相遮擋。設計與限制見 [PRICE_LENS.md](PRICE_LENS.md)、[TOOL_DOCK.md](TOOL_DOCK.md)。

## 2026-11-03 行情空白與吸附修正

- 修正有新聞與 ticker 卻不觸發行情請求；自動載入、圖內錯誤提示、K 線疊收盤價線。
- 配色改由實際行情市場 metadata 決定，刪除配色選單。
- 以邊緣 12px／650ms 停留取代整個右側區域吸附，採自適應分割樹，移除文字按鈕。
- 收合圖示放大一倍，短視窗精簡非必要說明以顯示股價。

## 2026-11-03 股價動能與可分割工作區

新增股價十字線、同步軸縮放／雙擊還原、N 日方向高亮、P95 標準化與鐘形內實際成份占比。修正巢狀分割拖出後剩餘視窗未恢復比例；保留邊緣 650ms 停留門檻。run.sh 新增 chat setup 與整合／獨立範例啟動說明。詳見 PRICE_LENS、TOOL_DOCK、CHAT_AGENT。
