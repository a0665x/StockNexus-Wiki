# 測試與驗收

入口：[PROJECT_MAP.md](PROJECT_MAP.md)。測試使用隔離 fixture／暫存 DB，不應改寫使用者的 data/news-atlas.sqlite3。

## 2026-11-07：Wiki 503／單一整理入口回歸

故障證據：正式服務 log 的 `GET /api/wiki/jobs?instrument=NASDAQ:TSM` 回 503，堆疊位於 WikiStore 初始化 executescript，錯誤 `database is locked`。隔離第二 SQLite 連線持有 BEGIN IMMEDIATE 時，舊路徑可重現失敗；修正後同一 HTTP jobs 讀取成功，不需釋放 writer。TSM 正式庫 read-only quick_check 為 ok；這不是歷史新聞內容正確性的保證。

| Given／When 邊界 | Then／自動驗證 |
| --- | --- |
| 已初始化庫正在由另一連線寫入；使用者查狀態 | GET jobs 200，開庫純讀；`test_wiki_responsiveness.py` |
| 重複讀同股票覆蓋；之後提交設定變更 | 未變更不重掃，提交後失效；同檔案的 coverage test |
| 沒有新新聞但觀點缺分類；明確按開始 | 仍排分類、重用舊 L1；`test_wiki_classifier.py` |
| 進頁或慢 poll；反覆點主按鈕 | 進頁零 plan、輪詢不疊加、準備態立即顯示、僅一份 jobs；`browser_wiki_layout.py` |
| 第一次 graph 503 後離開再進 | 錯誤可見、重進恢復且不啟動模型；`WIKI_RESPONSIVE_SCENARIO=retry` |
| 保存 Claim 篩選後重新掛載 | 控制與圖形一致，一次 graph GET；`WIKI_RESPONSIVE_SCENARIO=restore` |
| 新研究、查看來源、保存 live、切換頁面 | 真實 HTTP／Chrome 研究回歸；`browser_research.py` |

本輪瀏覽器：retry 31 checks PASS、restore 30 checks PASS；research real HTTP/Chrome PASS。瀏覽器使用隔離資料、可控 API 回應／模型 fixture，包含實際 pointer 點擊、桌面與 390px overflow，不等於對正式模型做付費驗收。新增 HTTP／cache 3 tests、classifier 6 tests 先各自通過；完整 `python3 -m unittest discover -s tests`：289 tests / 133.543s / OK（有既有測試連線 ResourceWarning；無失敗）。部署核對補記於本節。`node --check dist/wiki-view.js`、spec 路由驗證、diff whitespace 通過。一次 UI detector 無命中；獨立 reviewer 的兩項 findings 均 resolved，documenter 確認沒有新的設計系統規則。

原有 11 個 Wiki DB 已以 SQLite backup 保存到 gitignored `data/private/wiki-responsive-backup-20261107/`，舊執行 image tag 為 `news-atlas:pre-wiki-responsive-20261107`。本次沒有新 schema migration，不刪資料。回退優先使用舊程式/image 與現有 DB；如要還原備份需先停工作，確認接受備份之後新增成果的損失，不能自動覆蓋較新 DB。

## 命令

```bash
python3 -m unittest discover -s tests -v
for test in tests/*.cjs; do node "$test" || exit; done
node --check dist/app.js
python3 spec/scripts/verify_docs.py
```

一般單元測試不需網路／Massive key。部分 Python API parity 測試呼叫 Node，因此完整測試需要 Node。不要把通過 mock 測試宣稱為 Massive 帳號實際授權成功。

## 依改動選測試

| 變更 | 優先檔案 |
| --- | --- |
| 標準化／來源／快取／HTTP | [test_server.py](../tests/test_server.py)、[test_source_workflow.py](../tests/test_source_workflow.py) |
| Swagger／API／排名一致性 | [test_api.py](../tests/test_api.py) |
| 分類及快照欄位 | [test_channels.py](../tests/test_channels.py)、test_api.py |
| 混合／分組／來源切換 | [test_graph_view.cjs](../tests/test_graph_view.cjs)、[test_stream.cjs](../tests/test_stream.cjs) |
| 深度、排名、多樹 | [test_exploration.cjs](../tests/test_exploration.cjs)、test_api.py |
| 光暈／材質／同步 | [test_glow.cjs](../tests/test_glow.cjs)、[test_glow_sync.cjs](../tests/test_glow_sync.cjs)、[test_presentation.cjs](../tests/test_presentation.cjs) |
| 吸附／拖拉／Ctrl 平移 | [test_interaction.cjs](../tests/test_interaction.cjs)、[test_sticky.cjs](../tests/test_sticky.cjs) |
| 時間軸／日期 | [test_timeline.cjs](../tests/test_timeline.cjs)、[test_dates.cjs](../tests/test_dates.cjs) |
| 輸入與偏好保存 | [test_search_draft.cjs](../tests/test_search_draft.cjs)、test_stream.cjs |
| 篩選框拖曳／收合 | [test_source_panel.cjs](../tests/test_source_panel.cjs) |

## 真實快取瀏覽器回放

```bash
python3 tests/browser_runtime_search.py /tmp/graphnews-runtime-regression.html
```

[產生器](../tests/browser_runtime_search.py) 只讀目前本地 NVDA memberships，各來源最多取 800，再以真實快取建立離線 HTML；需要 DB 及已有 NVDA 資料，不自造替代資料。用 WebGL 瀏覽器開啟，檢查 `document.body.dataset.qa`。

目前腳本實際測 IPO、三來源、完整節點保留、spinner／成功提示、零筆命中、Enter 隔離、無網路／graphData 寫入及光暈像素、實際 WebGL 半徑變化、12 個月刻度、相機不變、密度格同步森林與縮放按鈕。腳本開頭部分描述可能仍寫 robot，應以實際測試程式為準。日期目前固定為 2025-10-28 至 2026-10-28；跨日期／資料環境需明確更新測試條件，不能無條件把它當 live search 驗證。

回放會在 /tmp 產生含真實新聞的檔案，不要提交這些 HTML 或 DB。先前 session 的 /tmp 其他 QA 腳本不是專案依賴，不保證存在。

## 互動驗收的判定

除了截圖，還要核對操作前後節點 ID／數量／物件、graphData setter 次數、來源選擇、相機、draft 值及網路請求。尤其圖內搜尋不能觸發左側取得搜尋。實際重整檢查 localStorage 還原，不能只用同一頁變數假裝 reload。

文件修改只需本地連結／結構及內容查核；不必為純 spec 更新跑 live provider、改 DB 或重啟服務。

日期大小與時間軸森林：`node tests/test_time_focus.cjs` 檢查 UTC 距離、未知日期、月刻度、跨分類 trace、兩種 SVG renderer 的深度漸層；`test_stream.cjs` 檢查 runtime 物件保留、開關及 hidden-root 快照還原；`test_source_workflow.py` 檢查日期設定 DB roundtrip 及非法輸入。

鐘形增益：`node tests/test_time_lens.cjs` 驗證舊 Gaussian 相容、局部塑形不改另一側、倍率界限、profile 還原、復原／重設、拖曳偏移／反向／取消／鍵盤、投影遠近補償及 geometry 保留。真實快取 browser replay 也測任意曲線段、localStorage 保存、已移除參數滑桿、快照 profile、畫面投影半徑一致及原 graph/camera 不變。

啟動器：`bash -n run.sh`、`python3 -m unittest discover -s tests -p test_launcher.py -v`。包含真實 PTY 左右鍵／Enter、模擬 port 占用、取消不綁定、競態重新選擇、Tailscale 狀態／巢狀 Serve／Funnel 解析、代理 URL 與失敗／中斷清理。單元測試不更改真實 tailnet；實際 TCP/Tailscale 連線需在允許監聽 socket 的主機驗證。

首頁初始化回歸：

```bash
python3 -m unittest discover -s tests -p test_server.py -k every_script -v
python3 tests/browser_startup.py /tmp/graphnews-startup.html
# 模擬時間曲線資源缺失，搜尋／語言／問號仍必須可用
python3 tests/browser_startup.py /tmp/graphnews-startup-degraded.html /time-lens.js
```

用 WebGL 瀏覽器開啟產物，檢查 body.dataset.qa。HTML／JS 由實際 HTTP Handler 取得（無需 socket）；搜尋供應商以空結果串流隔離，這是初始化／事件回歸，不代表即時上游新聞可用性。真實快取回放也使用相同 Handler 載入資源，不再從檔案直接嵌入 JS 繞過靜態路由。

測試不能只記「通過」：變更摘要寫入 [CHANGELOG.md](CHANGELOG.md)，事故的失敗證據、修復、實測與未驗證項目寫入 [啟動事故紀錄](references/bugfix-20261029-frontend-asset-startup.md) 等 references。新 JS 必須跑實際 Handler 資源檢查與正常／缺模組兩種瀏覽器啟動情境。

本輪追加：`test_regions.py` 測共享版區／cache key、同 URL 跨地區與併發 origins、SQLite 3→4 相容；`test_credentials.py` 測重啟沿用、權限、錯誤輸入、HTTP/DB 不洩漏；`test_key_persistence.cjs` 測在途保存與忘記順序。browser_startup 同時量測兩面板收合 36px、移動／展開、不同寬度下圓點比例、Quick range、地區標示／提交。真實快取 replay 包含純水平調寬且另一側不變，以及收合兩面板不改 graph。


Edge 定義回歸：`python3 -m unittest discover -s tests -p test_relation_settings.py -v`、`node tests/test_relation_settings.cjs`。實際 HTTP assets／API 回應的離線瀏覽器回放：`python3 tests/browser_relations.py /tmp/atlas-relations.html`，以 Chrome 開啟，body.dataset.qa 應 PASS。涵蓋單一套用／spinner／progress、孤立點、同一 3D node 物件、roots、快照 metadata、失敗保留及每條線的證據。所有 fixture 使用隔離測試資料，不寫正式 DB。


原生瀏覽器互動回歸：`python3 tests/browser_native_controls.py`（需 google-chrome 與測試用 websocket-client）。以 CDP Input 真正派送滑鼠／鍵盤，不使用 element.click() 代替：兩工具收合→點開→拖曳→再點開、單一套用、tooltip 顯示／靜止淡出／移動恢復必須全 true。舊 synthetic smoke 未涵蓋 pointer capture click retargeting 與 select input→change 順序，不能單靠它宣稱這些操作正確。

Docker 啟動器：`python3 -m unittest discover -s tests -p test_docker_launcher.py -v`，含固定專案／互斥鎖、重複 up、殘留清理、失敗清理、外部 port 衝突、不安裝 Tailscale 不問、已有 Serve 沿用／衝突不覆寫，以及 mock PTY 左右鍵確認＋雙 URL。實際部署驗證兩次 up 後容器 ID 不變，測試不得停止其他專案。

資料路徑：`python3 -m unittest discover -s tests -p test_storage_paths.py -v`；隔離資料驗證 WAL、私有檔權限、備份及連結、非空目標拒絕、啟用連結／保存設定失敗復原、缺席磁碟拒絕、其他磁碟篩選及自訂入口。磁碟候選測試模擬掛載，不代表實體外接磁碟已驗證。

跨年回歸：`python3 -m unittest discover -s tests -p test_year_boundary.py -v`，涵蓋來源 UTC 跨年格式、含尾日／排他上限、SQLite 覆蓋、Massive 分頁、RSS 日期參數、全年窗口先行以及完整圖譜保留跨年文章。`test_graph_view.cjs` 驗證前端保留全部 1600 筆多來源文章。原生瀏覽器新增固定密度格、無播放／呈現選單、Channel 右方縮放、完整年份與自訂分類入口。來源現況證據與未驗證範圍見 SOURCES_AND_CACHE。

完整資料與偏好回歸：API 1001 節點重算／快照、3003 筆分類；原生 Chrome 1201 節點時間軸／3D、來源調色盤保存與重設、forceRefresh 舊偏好不恢復。Docker 測試包含英文訊息、網路離線 WARN 與 storage write/fsync。

### Graph recovery and concurrent user journeys (2026-11-02)

Run `python3 tests/browser_user_journeys.py` (Chrome and websocket-client required).
Uses isolated fixtures served through the real handler, real pointer clicks and a real
WebGL renderer. It prints a verdict for each action and exits nonzero on failure.
Covers delayed search/edges, view/source switching while waiting, Apply cancellation,
stale responses, search cancellation and replacement, category/root isolation,
7,106 retained records with an 800-node GPU budget, offscreen article selection,
`WEBGL_lose_context`, reduced-budget reconstruction, failed retry then successful retry.
Screenshot: `/tmp/atlas-user-journeys.png`. No production DB writes or news-provider calls.

`node tests/test_render_budget.cjs` verifies deterministic slicing, retained full data,
priority selection and endpoint integrity. `tests/test_progressive_search.py` verifies
news before edge computation, heartbeat, requested settings and edge failure recovery.
These deterministic fault tests do not establish a universal safe GPU capacity.

`python3 tests/browser_user_journeys.py --no-webgl` disables WebGL in an isolated
Chrome profile. It verifies explicit failure, retained news, available retry and no
replacement renderer. The normal journey verifies cleanup exceptions do not block
3D reconstruction and recovery succeeds once the constructor is available again.

持久圖譜快取：`python3 -m unittest discover -s tests -p test_graph_cache.py -v`。
隔離 DB 驗證獨立 Python 程序重啟命中、完整結果一致、內容／順序／規則／版本失效、
同時請求合併、呼叫者物件隔離、損壞／不可寫快取回退及保留數量／payload 大小預算。
搜尋與 HTTP API 路由仍由完整 Python suite 驗證。快取不代表來源覆蓋已更新。

早期關聯：`test_progressive_search.py` 驗證第一事件已有 warm edges、provider 尚未開始、
來源完成不清空既有線、內容變更端點不沿用舊 evidence；`test_feature_cache.py` 驗證純特徵
內容／定義失效、結果物件隔離與 fetched_at 等 metadata 不被覆寫。

## Chat Agent

`npm run test:chat` verifies session isolation, cancellation, continuation/reset and UI acknowledgements.
`python3 tests/browser_chat.py` verifies the deployed UI in an isolated Chrome profile;
`--live` additionally uses the signed-in model and account usage. See [CHAT_AGENT](CHAT_AGENT.md).

股價混合及詳情語言：見 [PRICE_LENS.md](PRICE_LENS.md)。`python3 tests/browser_detail_language.py` 使用隔離 Chrome、現有快照及僅瀏覽器 fixture，無模型請求。

K 線／視窗分割：`node tests/price-chart.test.cjs`、`python3 tests/browser_price_dock.py`，後者在隔離 Chrome 用 CDP 滑鼠拖曳；使用現有快照及真實 Massive 行情／快取，不寫入正式新聞 DB；可能消耗行情 API 額度。另跑 `tests/browser_user_journeys.py` 檢查工具不遮擋導覽與來源控制。

2026-11-03 驗收：132 項 Python 測試、全部 CJS 測試、Chat session／取消／MCP acknowledgement 測試通過。實際 Chrome 驗證中英切換／紅框、標準化後正負完整報酬 16:1 的實際 mesh 比例、十字線／同步軸縮放不改 time_focus、雙擊還原、正負方向高亮、邊緣停留及巢狀拖出比例補位、保存重載；既有 2,400 節點、WebGL 遺失／重試流程亦通過。這些是隔離瀏覽器驗收，不代表所有主機 GPU 容量。socket 與瀏覽器測試須在允許建立本機 socket 的環境執行。

### 大量節點與重複計算回歸（2026-11-04）

`node tests/test_graph_performance.cjs` 檢查工作數量／cache失效與上限；`/usr/bin/python3 tests/browser_graph_performance.py` 使用隔離synthetic 10k–12k資料與真實WebGL，檢查實際GPU800預設／各預算、DOM100列分頁、Chat跨頁、分類、來源切換與匯出完整性。需Chromium及websocket-client，可指定CHROME_BIN；詳細結果寫在/tmp，不含正式新聞。量測與限制見 [效能紀錄](references/bugfix-20261104-large-graph-performance.md)。

視圖優先建圖：`python3 -m unittest discover -s tests -p test_view_relations.py`、`/usr/bin/python3 tests/browser_view_relations.py`。使用隔離fixture；後者需Chromium和websocket-client。詳見 [驗證與範圍](references/view-first-relations-20261104.md)。

增量配對：`tests/test_relation_cache.py` 驗證持久重用、負結果、內容失效及重選一致性；`tests/test_view_relations.py` 驗證HTTP新算／重用數及分組略過跨來源；`tests/browser_view_relations.py` 驗證完成範圍零請求、快照還原與先前完成組合。

## LLM Wiki

隔離 DB／引用／歷史／成本：`python3 -m unittest discover -s tests -p "test_wiki*.py"`（schema 測試需開發環境 jsonschema）。橋接：`npm run test:chat`。瀏覽器：`/usr/bin/python3 tests/browser_wiki.py`。實作邊界見 [WIKI_RUNTIME](WIKI_RUNTIME.md)。

## Wiki 成本與範圍回歸

`tests/test_wiki.py` 驗證跨模型重用、全局日期擴大補缺、已校正文章去重、舊快照與背景排程競態。`npm run test:chat` 覆蓋分頁模型目錄及讀目錄期間取消不啟動推論；`python3 tests/browser_wiki.py` 驗證動態模型選單、月份／滑桿、全局預覽及手動校正限制，使用合成 API，不消耗模型 token。

2026-11-05 Wiki 修復驗收：193 項 Python 回歸、6 項 Chat/Wiki Node 測試、19 項隔離瀏覽器檢查通過。真實 8765 GOOGL 讀取顯示 24/6814（0.35%），原有 v24 未改寫。經使用者明確核准，將原失敗 Angi/Google 新聞的 title/summary 與最多 12 個節點限定欄位交給 gpt-6.1-sol，在隔離 SQLite 副本完成一次呼叫（15,834 input / 700 output tokens），通過引用／型別驗證，生成兩項有理由的直接營運線索；重跑已完成工作不重算。此測試不是市場預測品質評估，也未消耗正式 Wiki 的工作列帳本。

Wiki 空工作修正驗收：194 項 Python 測試與 22 項瀏覽器檢查通過；包含空畫面恢復已存全局範圍、零待辦不寫設定、運行／額度暫停動畫、隱藏空工作、真實指標拖寬與保存。真實 8765 僅預覽驗證 6814 篇、重用 24 篇、待補 6790 篇；當日呼叫 25 次而目前上限 20，正確顯示未啟動，沒有為測試提高額度或新增模型呼叫。

Wiki 工作介面增補：`tests/test_wiki_workbench.py` 驗證批次逐篇引用、修訂鏈／版本區間、雙語、區間用量、取消與實際重複聯集合併；`tests/browser_wiki.py` 驗證自動核對不推論、完整中英切換、設定及圖表。

2026-11-06 Wiki 互動延伸：234 項 Python、7 項橋接、39 項隔離瀏覽器檢查通過。新增 20 篇批次、精確點選星河／跨股隔離、Apply 取消晚回覆競態、缺漏交易日報酬、圖表縮放拖移／日期綁定／分類明細／漸進式觀點樹。實際 8765 以 GOOGL v351 驗證；部署前後全部 Wiki 資料表內容雜湊一致，未啟動真實推論。

2026-11-06 互動回饋回歸：`PYTHONPATH=.:tests python tests/browser_feedback.py` 使用隔離 HTTP 資產／資料與真實滑鼠，檢查窄視窗展開、不重疊、聊天無複製按鈕、分類保留引用背景、Claim 讀目前 7 天與生成歷史分離。`tests/test_wiki_http.py` 在隔離 SQLite 驗證新快取成熟 3 天／7 天不足及原節點不被改寫。均不消耗模型用量。

本次驗收：235 項 Python、22 組 CJS、39 項既有 Wiki 瀏覽器檢查與 9 項新增回饋檢查通過。部署後 8765 重跑原先失敗的窄視窗／天數案例均通過：GOOGL v360 分類保留 179 個背景端點，共 402 節點／266 線；7 天詳情顯示 3/7 與 2026-11-05 股價日。經使用者確認更新並接續，已備份，重啟前後 11 張 Wiki 表內容一致；按已保存的 20 篇／組等設定接續 578 篇未完成新聞。測試本身沒有模型推論，正式接續為使用者已授權工作。


工作畫面回歸：`tests/browser_workspace.py` 啟動隔離真實 HTTP server 與兩個全新 Chrome profile，驗證 DB 回復、保存／重開、News roots/budget 與 Wiki 模型／日期獨立。`tests/test_workspace.py` 檢查欄位白名單、股票格式、十版選單及雙端引文。`test_wiki_workbench.py` 另驗證進行中的 lexical 20 篇切換 root 精確三篇、晚回覆不寫入、跨新聞索引實際發布與 canonical schema。全部使用假模型，不消耗帳號用量。


驗收與部署完成：241 項 Python、22 組 CJS、8 項 Chat/Wiki Node、48 項 Wiki 瀏覽器與 9 項先前互動回歸通過；兩個全新 Chrome profile 的真實 HTTP 恢復測試通過。已更新 8765 與主機 Chat bridge，備份 `data/private/wiki-workspace-20261106-150223`。兩個股票共 22 張 Wiki 資料表在部署及正式頁面驗收前後內容雜湊一致。GOOGL 保持 v369、gpt-6.1-sol high、lexical 20 篇，原工作已由使用者取消，因此維持停止。隔離正式頁面驗證恢復 89 篇最近七日 DB 新聞、10 個 selectable versions、10 節點星河與 Wiki Chat 連線；唯讀驗收不啟動模型、不保留測試偏好。第一次驗收的暫時偏好已核對後清除，正式控制值仍由原設定 high 恢復。

## 2026-11-06 完整 root 覆蓋與初始渲染回歸

- `test_wiki_forest.py`：沒有手動 root、810 個未渲染／孤立節點、日期外整樹脈絡、重疊去重、分段失敗與續跑、固定批次執行中改 Graph、同股票邊界、後端每棵樹對照 JS 點擊結果（混合／分來源）。使用隔離 DB／模型 runner。
- `browser_render_regressions.py`：隱藏畫布初畫→展開→縮窄、KeyD 後失焦、實體滑鼠左拖旋轉／Ctrl 左拖平移；已先重現 1200 寬燭體與殘留 keyState=2。
- `browser_wiki.py`：51 項檢查，加入無點選 Graph Apply、完整 universe 請求、動畫輪詢不中斷、減少動態效果偏好。
- 完整 Python／CJS／Node 回歸及實際 TSLA 隔離副本、正式 HTTP 瀏覽器檢查另於交付紀錄列出；不為驗收啟動真實推論。

交付驗證：247 項 Python、22 個 CJS 測試檔、8 項 Node 橋接、51 項 Wiki 瀏覽器、9 項先前回饋及兩個新瀏覽器設定檔恢復均通過。正式 TSLA 12 個月 2765 篇來源紀錄，Wiki 2026-10-06～2026-11-06 的 425 個目標由 48 棵樹涵蓋，含 49 篇區間外脈絡；逐棵與 JS 單 root 展開一致。正式 HTTP 預覽相同結果，238 根 K 線最大寬度 1.79 SVG 單位，曲線圓點不再覆蓋圖面。

已部署 8765，備份 `data/private/wiki-root-coverage-20261106-160609`。更新及瀏覽器驗收前後 22 張 Wiki 表與 news/wiki 工作區 payload 雜湊一致；GOOGL、TSLA 均保持停止，沒有真實模型驗收呼叫。

## 2026-11-06 Wiki 分隔版面與選取回歸

`python3 tests/browser_wiki_layout.py` 透過真實 HTTP 資產、隔離資料與 Chrome CDP 滑鼠事件，驗證 header 不重疊、三邊拖曳、圖表尺寸、節點物件／鏡頭不變、拖離再返回仍保留選取、空白點擊解除、飛機單次送出、中英及手機版面。聊天回應為 fixture，不呼叫模型。CDP 拖曳的 mouseMoved 須同時指定 button=left 及 buttons=1；零移動點擊不送多餘 move 事件，以免套件視為拖曳。

`browser_workspace.py` 另驗證全新 Chrome profile 從主機恢復 pane 尺寸；`test_workspace.py` 驗證尺寸白名單、有限數值與範圍。既有 Wiki 與互動回饋回歸仍須通過。

交付：248 項 Python、22 個 CJS 檔、8 項 Chat/Wiki Node、51 項 Wiki 瀏覽器、22 項新版面／實體互動與 9 項先前回饋檢查通過；兩個全新 Chrome profile 還原尺寸通過。正式 8765 以 GOOGL 800 個渲染節點驗證保留物件／鏡頭、798 個無關節點變暗、三個分隔線、滾輪／拖曳保留選取、空白點擊解除及紙飛機位置。模型與偏好寫入在 QA 瀏覽器攔截。

部署備份：`data/private/wiki-layout-20261106-163307`；重啟及正式頁面驗收前後 22 張 Wiki 表、兩個工作區 payload 一致，GOOGL／TSLA 保持停止。瀏覽器驗收的「空白點擊」需先確認密集圖譜未遮住該點；放大狀態下點到暗色節點仍屬節點選取。

## 2026-11-06 浮動尺寸、資料掃描與在線合併

- `python tests/browser_floating_resize.py`：14 項真實指標檢查，包含 SE／NW 角與單邊、固定對角、捲動不移動標題、失焦取消、圖譜資料／時間焦點保留、收合重開、停靠往返及重載。先重現無 resize handles，修正後通過。此測試使用隔離的內嵌前端 fixture。
- `PYTHONPATH=.:tests python tests/browser_live_merge.py`：隔離真實 HTTP／Chrome，執行實際 merge CLI 的 dry-run 與正式合併，確認新股票與原股票版本即時出現、既有選擇及空白新股票選項不被蓋過、News runtime 不變、SVG 外部 use 真的繪製、沒有模型呼叫。
- `browser_wiki.py` 的 51 項回歸檢查掃描／訊號 DOM 在輪詢間不重建，running／停止及減少動態偏好有效。
- `test_docker_launcher.py` 檢查成功 up 實際輸出合併提示，以及有空格 data 路徑的命令可正確解析。

本次 249 項 Python、22 個 CJS 檔、51 項 Wiki、22 項版面及 9 項先前回饋檢查通過；隱藏 K 線／首次展開／實體旋轉回歸通過。35 份 spec 本地連結與必要入口驗證通過；本機 onboarding skill 通過 quick_validate，盤點腳本實際執行成功。沒有為本次驗收呼叫模型或匯入使用者真實 USB。

正式 8765：映像 `85ae8666615f`，備份 `data/private/tools-learning-20261106-171159`。停止原本 GOOGL 工作後，重啟前後 22 張 Wiki 表內容一致；HTTP 新增 JS／SVG 及修改資產與本地逐位元相同，Chat bridge ready，唯一容器 healthy。按原設定接續 GOOGL 的剩餘新聞，TSLA 維持停止；接續會正常發布新版本，不能再要求之後所有 Wiki 表不變。

正式頁面在獨立 Chrome profile 驗證 4,764 篇 News 的浮動尺寸變化、捲動、節點物件／鏡頭／時間焦點不變；Wiki running 顯示已載入的向量圖與掃描動畫。導覽前攔截 workspace POST 與模型／來源寫入，驗收記錄確認 3 次工作區保存被攔截。備份與稍後 workspace 的差異位於選取／鏡頭與 News snapshot；QA 保存已攔截，而使用者原頁仍開啟。未將這些差異直接歸因於測試，未還原覆蓋目前畫面，也不宣稱整段期間 workspace 雜湊一致。

## 2026-11-06 語系、重連與多視窗回歸

```bash
PYTHONPATH=.:tests python tests/browser_chat_language.py
```

使用實際 HTTP 資產與隔離資料、兩個 Chrome profile、三個同 profile 的實際 URL 分頁。Chat transport 可控制連線／回覆／取消確認的完成順序，測初始掛載、sync、reset、中英來回、在途切語系、error、session 過期重連、隱藏頁面、雙向 storage 通知、reload 與冷啟動。斷言已知 UI 不殘留中文，原文、模型／生成設定、範圍、節點物件與鏡頭不變。fixture 三次 turn 均不觸及模型帳號。兩個 red 分別重現原始中文殘留與晚取消確認倒退狀態；同一斷言修正後通過。

保存／同步邊界及已知原因見 [事故紀錄](references/lesson-20261106-language-runtime.md)。這個測試不把獨立 profile 初始化英文誤稱為跨 profile 語言同步，也不以模擬 session 過期代替所有實體網路重連驗證。

驗收：新增生命週期測試通過；249 項 Python、22 個 CJS 檔、8 項 Chat/Wiki Node、51 項 Wiki 瀏覽器、22 項版面及 9 項既有回饋檢查通過；兩個全新 Chrome profile 的工作區恢復亦通過。文件本地連結檢查通過。

正式 8765 已更新至映像 `f0e6c8d97f93`；備份 `data/private/language-runtime-20261106-174752`。重啟前後 22 張 Wiki 表內容一致，五個修改資產與本地逐位元相同，Chat bridge ready、容器 healthy。部署時活動中的 GOOGL 按原設定接續，TSLA 維持停止；使用者之後的設定變更仍可正常生效。

正式服務使用兩個獨立 URL 分頁驗證英文冷啟動、實際 Chat 連線／sync、雙向語言切換、reload 後重新連線及 News／Wiki 返回；所有 UI 斷言通過且無 JS 錯誤。QA 在導覽前攔截 workspace 寫入與模型／來源／設定變更，不送出模型 turn。第一次正式測試沿用小 fixture 的限時等待，未等完整 Wiki 初始化便逾時；改為等待 `show()` 真正完成後再檢查，不改產品結果斷言。正式服務進行中的推論不是 QA 觸發，資料可因使用者既有工作持續更新。

## 多股票 Wiki 輪替

`python3 -m unittest discover -s tests -p test_wiki_fairness.py -v`：兩支股票都有三批待辦時，每輪各處理一批，再輪替；所有文章最終各呼叫一次。重審同工作已完成文章也不重送。`test_wiki_forest.py` 驗證大樹全部分段發布後才讓出，完成覆蓋與去重維持一致。測試使用隔離 DB／模型回覆，不代表正式模型品質或所有來源歷史完整。

## 2026-11-07 缺失 Wiki 端點回饋回歸

`python3 -m unittest discover -s tests -p 'test_wiki*.py' -q`：53 項通過。`test_missing_relation_target_feedback_repairs_only_the_bad_edge` 在舊訊息先失敗，修正後保留有效關聯、只記一次 coverage、兩次 usage 均計入；`test_unrepaired_missing_target_never_publishes_or_credits_coverage` 確認未修正仍有界失敗。真實拒絕提案僅離線重播，沒有為測試呼叫模型或寫正式圖；正式續跑是另行授權的批次操作。

同輪完整 Python 回歸：`python3 -m unittest discover -s tests -q`，254 項通過；文件連結檢查 36 份通過。

部署：在所有 Wiki 工作均無 running 的發布邊界停止舊容器，六股 queued／done 原值保留，無需重送活動推論；重建後 8765 healthy。容器與主機 `news_atlas/wiki/store.py` SHA-256 同為 `17eebe73754948a0a92eb108f829776054ff631304963753486878b8af931390`。TSM 續跑依私有批次紀錄的一次額度進行；此部署驗證不等於後續全部推論已通過。

## 雙層研究與合併邊界（2026-11-07）

- `python3 -W ignore::ResourceWarning -m unittest discover -s tests -p 'test_*.py'`：279 tests OK（新增 L2 inference 語意拒絕、live 重啟不付費重試、時間窗、撤回、候選詞、CAS、合併引用等）。
- `node --test tests/chat*.test.mjs`：9 個 Node 測試檔 OK；`tests/*.cjs` 全部通過。橋接為受控 fixture，不代表正式模型已成功推論。
- `PYTHONPATH=tests /usr/bin/python3 tests/browser_research.py`：真實 HTTP＋Chrome PASS；含建立研究、來源鏈、live 保存、離開在途工作、切股票、圖 tooltip 轉義及 1393／390px 無水平溢出。WebSocket dependency 使用主機已有系統 Python。
- `PYTHONPATH=tests /usr/bin/python3 tests/browser_live_merge.py`：真實 CLI 在 HTTP／Chrome 開啟下合併 PASS，新股票出現在選單、既有版本更新、使用者選擇及 News runtime 保留。
- `test_imported_source_not_known_before_import` 修正前為 FAIL，修正後通過。新版 schema 拒絕、損壞引用拒絕與備份／雙向合併仍通過。
- 新 UI detector 僅報既有 Wiki CSS 的舊 2px border；沒有修改該既有裝飾。獨立 review 的 6 個實質問題已修正，最後舊 await 回應 guard 已補。
- 未驗證：新 L2 正式模型品質、真實行情特徵、跨使用者登入（本版為單人 local owner）。第一版限制與未完長期驗收項詳見 RESEARCH_LAYERS。

部署驗證：11 個 Wiki SQLite 已以 SQLite backup 備份至 `data/private/research-migration-backup-20261107/`，舊映像保留為 `news-atlas:pre-research-20261107`。第一次部署在 AMD 完整提交邊界（version 24、done 371）停止，重啟後同一 job ID 正常 running，既有六個 failed 工作未復活；HTTP JS 與容器 research.py SHA-256 均和主機一致，容器 healthy，模型目錄可讀。沒有為新 L2 驗收呼叫正式模型。最後 UI guard 修正後再次執行隔離 Chrome PASS；關閉測試瀏覽器後的 BrokenPipe 是未完成輪詢連線被關閉，不是斷言失敗。

## 共用 L1／L2 工作區與模型分類（2026-11-07，第二輪）

- `python3 -m unittest discover -s tests -v`：285 tests OK；包含分類補足不重抽新聞、精確 taxonomy revision、未知標籤原子拒絕、queued/running 分類取消保留已發布成果，以及模型分類資料合併重用。
- `node --test tests/*.test.mjs`：9 tests OK；`tests/*.cjs` 全部通過。Chat 真實本機工具路由驗證 selected L2、DERIVED_FROM 與研究 metadata；使用 fixture，不消耗正式模型。
- `PYTHONPATH=tests /usr/bin/python3 tests/browser_research.py`：真實 HTTP／Chrome 驗證共用 3D 實例、實際進度分隔線拖曳、550ms 忙碌說明、L1 忙碌 API 拒絕、保存研究、同股票與跨股票重開接續同一 job、歷史版本隔離、Chat 清除隱藏選取與 1393／390px 溢出邊界。
- `browser_wiki_layout.py`：22 項實際互動 PASS；`browser_chat_language.py`：語言、多視窗同步、重載及發送生命週期 PASS。
- 文件檢查：37 份 Markdown 通過。UI 維持原工作區視覺；未建立另一套 3D／設計系統。獨立 review 發現的版本、選取、工作接續問題均追加行為測試。
- 未驗證：正式模型的新分類品質、巨大分類集合的手動探索及完整手機滾動旅程；本輪沒有為 QA 呼叫正式模型。Tailscale 網頁的 Chat 仍遵守既有本機來源限制，使用本機 `127.0.0.1:8765` 測試 Chat。

本輪部署：SQLite backup 保留 11 個股票資料庫於 `data/private/shared-workspace-backup-20261107/`；舊映像 `news-atlas:pre-shared-wiki-20261107`。同時確認 jobs／research_jobs 沒有 running 後重啟容器與 Chat bridge。8765 healthy；HTTP 的 wiki-view.js、research-view.js、wiki-view.css 與主機逐位元相同，容器 classifier.py、compiler.py、research.py 亦相同。模型目錄可讀取 8 個選項，沒有進行付費推論。11 個 Wiki version 與部署前一致；AMD job 保持 cancelled／done 467，沒有復活使用者停止的工作。

獨立審查最後 verdict 為 ship，範圍是已列出的版本、選取、研究接續與分類取消問題；不表示正式模型品質已驗收。最終 Chrome 回歸 PASS，結束後的 BrokenPipe 是已關閉瀏覽器的輪詢連線。開啟保存研究會保留真正選取的 L1 底圖版本，L2 來源另外明示固定快照，不把歷史底圖誤標最新版本。Documenter 確認普通工作區延伸沿用原設計，沒有新增 DESIGN.md 或另一套樣式規範。

回退：停止工作並保留最新 DB 備份後，可用 `ATLAS_IMAGE_TAG=pre-shared-wiki-20261107 docker compose up -d --no-build` 回到本輪前映像；Chat 主機程式需同步回到前次 commit `c6d3f66`。本輪分類資料為新增研究物件，沒有刪表或重寫既有 L1。不要直接覆寫目前 SQLite；需要還原舊備份時先保留本輪新增成果。
