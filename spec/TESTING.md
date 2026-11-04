# 測試與驗收

入口：[PROJECT_MAP.md](PROJECT_MAP.md)。測試使用隔離 fixture／暫存 DB，不應改寫使用者的 data/news-atlas.sqlite3。

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
