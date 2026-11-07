# 變更與驗證 log

## 2026-11-07 — Wiki 缺失端點的精確修正回饋

- 年度 root 工作中，模型連續兩次引用不存在的既有節點 ID；舊訊息合併未知端點與方向錯誤，導致修正仍保留真正的壞連線。
- 驗證先指出關聯序號及缺失 source／target ID，再處理方向、種類與引用限制；拒絕規則及最多一次模型修正不變，不默默丟棄模型內容。
- BDD 先重現整批 failed，再驗證針對性回饋可保留有效連線並完成；未修正的提案仍兩次後失敗、零發布與零 coverage。254 項 Python 回歸（含 53 項 Wiki）及文件連結檢查通過；原始拒絕提案離線重播確認唯一缺失 target。
- 正式續跑保持原 graph_universe、模型與一年日期；既有成果重用，同原因最多一次外部續跑，操作記錄放私有批次檔。

## 2026-11-07 — 多股票 Wiki 公平輪替

- 修正單股整份待辦長時間佔用模型槽：完整 root 樹發布後讓出，其餘股票每輪各前進一次；大樹分段不拆開重送。
- queued 工作重用凍結圖譜；review 續跑略過同工作已複查文章。
- BDD 回歸先重現 AMD 三批全部完成才輪到 NVDA，再驗證逐股前進、去重及大樹完整分段。
- 252 項 Python 回歸（含 51 項 Wiki）通過；文件路由驗證通過。
- 七個標的一年範圍補抓與實際處理狀態另以執行中 DB 為準；來源缺口與 Wiki 整理覆蓋分開。

## 2026-11-06 — Chat 語系生命週期與多視窗

- 修正 Wiki Chat 重連／sync 後狀態與情境卡仍為中文；所有介面文字由 canonical 狀態和完整模板按目前語系呈現，保留訊息／引用原文。
- News／Wiki runtime 共用 UI 語言；同來源同 profile 的不同視窗透過 storage 同步，切換入口與冷啟動使用同一契約。生成語系與工作範圍保持獨立。
- 修正取消確認晚到造成「已停止」倒退成「正在停止」。
- 新增真實 HTTP／多分頁／獨立 profile 的隔離生命週期回歸；補充 [通用開發偏好](ai-dev-experience-preferences.md) 與 [事故證據](references/lesson-20261106-language-runtime.md)，不以單張正常畫面宣稱所有入口正常。

交付：新增生命週期與相關回歸通過；已更新 8765，正式雙 URL 分頁／重連／語言切換驗證完成，備份與用量邊界見 [TESTING](TESTING.md)。

## 2026-11-06 — 浮動尺寸、資料挖掘視覺與可持續維護

- 時間／來源工具新增八個邊緣／角落把手，固定標題、內容捲動；收合／重載保存尺寸，取消／失焦回復，停靠由原分割樹接管。
- 漫畫書堆／鎬子改為原生細線文件、掃描光條與知識訊號；資產 `dist/knowledge-mining.svg`，只有 running 播放且遵守減少動態偏好。
- `run.sh up` 印出實際 data 路徑的 USB 合併預覽／正式命令。Wiki 目錄約 6 秒更新，保留選取／模型／日期；新增股票與既有最新版本可在服務不中斷時看到。
- 新增 CURRENT_STATE、CALCULATION_METHODS、跨專案 ai-dev-experience-preferences 與互動事故紀錄；同步入口、UI／runtime／合併等過時規格。另依使用者授權更新本機 project-spec-onboarding skill 的持續學習／規格維護流程與可執行盤點腳本。
- 249 項 Python、22 個 CJS、51 項 Wiki、22 項版面、14 項浮動檢查與既有渲染／互動回歸通過；真實 CLI＋HTTP＋Chrome 在線匯入通過。測試使用隔離資料與假模型。
- 已更新唯一 healthy 8765 服務並核對資產；重啟前後 22 張 Wiki 表一致。原本 GOOGL 工作按保存設定接續，TSLA 保持停止。詳見 [TESTING](TESTING.md)。

## 2026-11-06 — Wiki 分隔版面與持續星河選取

- 固定 44px 頂部改讀實際全局 header 高度，語言／Wiki 設定不再被遮住。
- 兩側與時間圖表新增可拖曳／鍵盤調整的分隔線；尺寸隨 Wiki 工作區保存及新視窗恢復。
- Chat 改用輸入欄內紙飛機，保留鍵盤送出、空白／忙碌停用及無障礙名稱。
- Wiki 選取由裁切重排改為保留全圖並調暗無關節點，不變更鏡頭；移除置中／全圖按鈕，僅空白點擊解除，拖曳旋轉保留。
- 回歸：先重現六項 UI 症狀，再用真實瀏覽器滑鼠測試三個分隔線、鏡頭、往返拖曳、空白點擊及飛機送出。

## 2026-11-06 — 全範圍 root 覆蓋、K 線與旋轉

- Graph 模式由「手動點選星河」改成完整 News 圖自動採樣，同一棵樹對照瀏覽器規則；Wiki 日期只限制目標與完成分母，樹的日期外成員保留脈絡。無需點 node 才能 Apply。
- 分段樹全部成功才增加覆蓋，中斷保留已發布版本並可續跑；既有已確認工作不擅自擴大範圍。
- 修正隱藏 SVG 寬度 0 造成滿版紅綠燭體；停用殘留的 Trackball A/S/D 狀態，避免首次自動取景干擾手勢。
- 當時加入書堆挖礦／金色火花循環；後續同日依風格回饋改為資料掃描視覺，見上方最新項目。
- 詳細契約與驗收見 WIKI_RUNTIME、PRICE_LENS、UI 與 TESTING。

## 2026-11-06 — 時間工具、Wiki 引用與目前行情修正

- 窄視窗點開工具後不再被碰撞處理收回；目前操作的工具優先，剩餘內容捲動。
- Chat 移除逐則複製按鈕；保留模型工具決策及來源連結。
- 分類篩選保留實際引用／相依端點、灰色標示背景；緊密布局、置中縮放與獨立群數量，未新增虛構關係。
- 修正工作舊 N 蓋過目前選擇；所有非新聞節點顯示最新快取行情、已具備交易日數，生成時行情另行保存。
- 詳見 TOOL_DOCK、CHAT_AGENT、WIKI_RUNTIME 與 TESTING；回歸均使用隔離資料，不呼叫真實模型。

## 2026-11-06 — Wiki 工作介面與有界觀點更新

- 自動範圍核對、單軌雙端日期滑桿、區間覆蓋、開始提示與真實工作動畫；歷史工作紀錄仍只保留 DB/log。
- 版本摘要、版內新聞區間、原始＋最新三批修訂、即時觀點時間圖。
- Wiki 獨立設定：雙語保存、模型思考深度、每次 1–5 篇與詞彙／時間／root／融合分組；實際引用驗證不放寬。
- 相依檢視限制為最多 12 個相關節點、含最多 4 個直接相依 Thesis，不是全圖遞迴推論。
- token 使用實際回報與逐批日期歸屬；舊工作缺少逐批記錄明示不納入。
- 套用使用者品牌 PNG，Wiki 中英以完整字串切換，避免全局逐詞翻譯污染內容。
- 行為與限制以 [WIKI_RUNTIME](WIKI_RUNTIME.md) 為準。

## 2026-11-05 — Wiki 模型目錄與範圍增量

- 模型下拉改讀 Codex model/list，預設 gpt-6.1-sol；目錄讀取不推論，取消期間不誤啟動模型。
- 全局目前查詢／日期滑桿與預設月份；主頁渲染及 edge 設定不觸發 Wiki 維護。
- 跨模型沿用已抽取 revision，延長日期只補缺；手動局部校正有證據世代去重，不可自動循環。
- 修正舊快照排除新 revision、背景排程與手動授權競態；上下文由全股知識節點選取有界摘要。
- 189 項 Python、22 個 CJS 檔、6 項 Chat/Wiki 測試與 16 項 Wiki 瀏覽器檢查通過；文件連結驗證通過。服務重啟後 localhost／HTTPS 均讀得實際 8 個模型及 Sol 預設；此輪不額外呼叫模型推論。

## 2026-11-05 — LLM Wiki 增量知識圖

- 新增每股獨立 SQLite、凍結引用、節點／連線版本、預覽後啟動、每日嘗試配額、指定查詢背景維護及取消。
- 頂部 LLM Wiki 獨立視圖，提供版本／UTC 時點、引用詳情、節點及關係篩選與 Markdown 匯出；新聞圖維持原狀。
- 主機登入橋接新增無工具 JSON compiler。已用一篇隔離合成資料實際呼叫設定模型，完成 2 節點／1 線、引用驗證及寫入；正式新聞與 Wiki DB 未放測試資料。
- 兩軸程式／規格複查修正舊預覽競態、股票與匯出錯配、重啟自動重試成本，以及全歷史 edges 解碼。新增測試核對正式 Relation schema；限制見 [WIKI_RUNTIME](WIKI_RUNTIME.md)。
- 181 項 Python、22 個 CJS 檔、4 項 Node Chat/Wiki 測試通過；隔離瀏覽器 Wiki 13 項、關聯／快照／說明 35 項、大圖 22 項、完整互動 27 項及無 WebGL 4 項通過。Chat 操作、中英／股價比例、十字線／縮放、四邊停靠／拖出／比例及重載保存亦通過。舊測試已對齊分頁新聞按鈕、view preview 端點及 Chromium 偵測。
- localhost 與受信任 HTTPS 實際資產 hash 一致，Wiki bridge ready、同源寫入可用。未以此宣稱模型抽取品質、因果、預測效益或全量依賴重評已驗收。

## 2026-11-04 — 大量節點效能

- 保持800點／2400線預設上限；清單與密集時間桶分頁100篇，完整資料仍可搜尋／匯出。
- 關聯索引共用與有界cache、相同切片跳過graphData、單點投影及query級regex，減少重複計算。
- 22個CJS、10k–12k真實WebGL壓力案例、27項既有使用流程及9項API／資源路由檢查通過；使用SwiftShader，不宣稱硬體FPS。
- [重現、量測與限制](references/bugfix-20261104-large-graph-performance.md)。


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

## 2026-11-04 視圖優先關聯

搜尋可先取得完整新聞，3D僅計算目前budget內節點；strict先呈現、閒置再補adaptive。新增配對／節點／連線／狀態計數、650ms停留說明與局部關聯快照標記。見 [設計與驗證](references/view-first-relations-20261104.md)。

## 2026-11-04 README示範與分支狀態確認

確認目前為 `llm_wiki`，尚未提交的News Graph效能／互動修改已部署；Temporal LLM Wiki維持設計階段，尚無compiler、Wiki轉換UI或回測runtime。README新增明確實作狀態表、研究版影片動畫預覽與完整影片連結；已依使用者提供的v3目錄確認影片C為Research Desk（stocknexus-research.webm），SHA-256與既有轉檔來源一致；媒體來源註記已更新。15項離線Wiki設計檢查及spec本地連結檢查通過。

## 2026-11-04 跨視圖重用與快照還原

配對分數與負結果持久保存，視圖變更只補缺少評分並重選連線；前端重用12組完成視圖。快照保存原始關聯、渲染預算及完成視圖，還原順序避免中間狀態重算。詳細規則與邊界見[視圖優先關聯](references/view-first-relations-20261104.md)。

## 2026-11-04 搜尋後關聯卡在停止狀態

修正acceptSearchGraph誤設restoringRelations=true且未解除，導致搜尋有節點但不發preview請求。快照還原旗標現在只由restoreSnapshot管理。瀏覽器測試改由實際搜尋接收入口進入，並新增還原快照後再搜尋的驗收；避免僅測rebuild而漏掉前置生命週期。

## 2026-11-05 Wiki 錯誤恢復與可見進度

補全 Event→Event 時序規則與一次受配額限制的拒絕修正；保存拒絕紀錄、補計回報用量。單股持久路徑／查詢範圍覆蓋／校正覆蓋／每日呼叫／每批狀態可見。新增沿用既有設定的「補足到今天」及質性觀點分類、局部關係說明與跨版本觀點彙整；詳見 WIKI_RUNTIME。

- 修正重新整理後全局 0 篇覆寫 Wiki 追蹤設定；空工作改為 noop。新增真實工作狀態動畫、每日額度阻擋提示、隱藏 0/0 紀錄、可拖拉的 Wiki 左側邊界。

### 2026-11-05 手動控制 Wiki 用量

移除每批篇數與每日呼叫上限；plan 舊 batch_size/daily_limit 欄位忽略，next_batch 相容欄位代表全部待辦。coverage 保留 daily_calls 記帳但不回傳 daily_limit；不提供帳號週用量百分比。確認後逐篇補足，可由停止按鈕取消，已完成版本不重做。預覽／閱讀頁面不自動啟動推論。

### 2026-11-05 跨電腦資料聯集

新增 merge_data.sh --from/--to/--dry-run：新聞與 Wiki 穩定 ID 去重、Wiki 版本重映射、衝突另存、快照 ID 碰撞隔離、備份與提交報告。新匯入維護設定停用，不呼叫模型；活躍目標拒絕合併。詳見 [DATA_MERGE.md](DATA_MERGE.md)。

### 2026-11-05 Wiki 股票目錄

Wiki 改存 data/llm_wiki/<ticker>/wiki.sqlite3；重啟新版時自動遷移舊 hash 目錄。merge_data.sh 支援單股／整個 llm_wiki／整個 data 分層聯集，保留跨交易所識別檢查。

### 2026-11-05 圖譜按股票分庫與完整路徑檢查

GraphRepository 以每次請求 ticker 路由搜尋、關聯快取、股價、快照及 Wiki 訂閱；不改全域當前股票。新增 graph/<ticker> 與 _unassigned，舊主 DB 備份後依明確查詢／快照／Wiki 訂閱分配。Chat／金鑰仍用 data/private。合併支援全層／分類／單股層級；歷史工作不顯示，帳本保留。


## 2026-11-06 — Wiki 星河範圍、互動統計與設定續跑

- 批次 UI 改 5／10／15／20；Graph 僅讀取滑鼠點選後的星河成員，固定篇數停用。禁止自動找其他 root 或擴大到股票全部 DB。
- 設定 draft／Apply 分離；取消舊呼叫後續跑，已完成版本保留，防止晚回覆發布及舊錯誤停掉新工作。
- 觀點圖表綁定左側日期，加入縮放平移、提示與右側分類明細；清單由分類→主題→觀點逐層展開，統一使用完整 Thesis 索引。
- 引入已快取交易日報酬作為觀察資料；主題、引用充分程度與影響管道分開，不把漲跌當可信度或因果。


### 2026-11-06 — 跨視窗狀態、Graph 切換及 Wiki Chat

修正 Wiki 切頁以後端 config 覆蓋控制值、新聞圖僅存在記憶體的問題；主機 workspace 分別保存 News/Wiki，初次升級可從股票 DB 恢復。Graph Apply 明示缺少同股星河，活動卡顯示實際方法；執行中切換只處理點選成員。股票欄前置且必填 EXCHANGE:SYMBOL，種入可編輯查詢字詞。Wiki 只使用 sidebar 日期，提供最近十個版本、獨立 Chat Agent 及實際關係星河聚焦。跨新聞 RELATED_TO 必須雙端引用，Graph 原文檢索亦受選取範圍約束。新 workspace 必須由實際 HTTP 靜態路由載入；新增跨 Chrome profile 測試避免只測 DOM 漏掉伺服器接口相容性。


驗收與部署完成：241 項 Python、22 組 CJS、8 項 Chat/Wiki Node、48 項 Wiki 瀏覽器與 9 項先前互動回歸通過；兩個全新 Chrome profile 的真實 HTTP 恢復測試通過。已更新 8765 與主機 Chat bridge，備份 `data/private/wiki-workspace-20261106-150223`。兩個股票共 22 張 Wiki 資料表在部署及正式頁面驗收前後內容雜湊一致。GOOGL 保持 v369、gpt-6.1-sol high、lexical 20 篇，原工作已由使用者取消，因此維持停止。隔離正式頁面驗證恢復 89 篇最近七日 DB 新聞、10 個 selectable versions、10 節點星河與 Wiki Chat 連線；唯讀驗收不啟動模型、不保留測試偏好。第一次驗收的暫時偏好已核對後清除，正式控制值仍由原設定 high 恢復。

## 2026-11-07：共享 L1 與 Lens／L2 垂直流程

新增分類版本、Research Lens、固定證據快照、L2 claim registry、來源圖與 live/pinned。沿用單模型槽與資料庫；新推論有界語意核對，失敗保留前版。移除 L1 輸入的未來報酬。合併修正取得時間污染並嚴格驗證引用與 schema。真實修改／BDD／遷移／限制見 [RESEARCH_LAYERS](RESEARCH_LAYERS.md)，測試見 [TESTING](TESTING.md)。
