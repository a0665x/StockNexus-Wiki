# 大量節點的 DOM、關聯樹與搜尋開銷

入口：[UI](../UI.md)、[測試](../TESTING.md)。日期：2026-11-04。工作分支 `llm_wiki`；保留既有探索／光暈偏好修改。本紀錄不宣稱修復使用者瀏覽器的所有 GPU 問題。

## 重現與診斷

隔離 Chromium profile，從實際 HTTP Handler 取得前端資源，使用 synthetic 10,000篇／39,990條關聯；沒有新聞 provider、LLM 或正式 DB 寫入。WebGL backend 為 ANGLE／Vulkan SwiftShader（軟體渲染）。

修正前：3D 確實只接收800節點／2400線，但 `rebuild` 仍為全部10,000篇建立新聞按鈕。`/tmp/stocknexus-perf-repro.py` 當時的 assertion `list_buttons<=200` 失敗；縮到1,000篇仍失敗。新永久測試見 [browser_graph_performance.py](../../tests/browser_graph_performance.py)。

另驗證：固定root時20次hover重建20次相同tree；10個roots各自重建全部adjacency；單點guide投影整個GPU切片；相同slice仍重設graphData/physics；關鍵字regex在每篇每欄位重建。這些可在乾淨profile重現，不是Chrome舊cache的證據。

## 修正與資源界線

- `explorer-ui.pagedRows`：新聞清單、密集時間桶的詳情每頁最多100列。上一頁／下一頁及頁碼均可抵達完整結果；Chat select_article先切到所屬頁，再走原點選流程。不是下載上限、刪資料或只搜尋第一頁。
- `graph-view.traceMany`：每個forest共用一次adjacency。`createTraceCache`每實例只保留目前edge-array revision的索引、最多16組森林；邊集合更換即釋放舊索引／結果，設定變更清除結果。app有focus與preview兩個實例，不跨搜尋無限累積。結果視為唯讀；日後變更edge／weight必須替換array，不能原地改後期待cache自動感知。
- `renderSlice`：預設800點、2400線，所有入口走同一硬上限（最大可選2400點／7200線）。線滿額即停止，避免先配置全部eligible edges再slice。priority去重保留第一次出現，避免巨大分類覆蓋選取項目的優先權；兩端必須在rendered IDs內。
- `app.renderNetwork`：同graph、相同節點／關聯引用順序且無待還原位置時，跳過graphData setter，不重啟物理模擬。只保留最近一份slice；dispose清除。
- `interaction.guide`：仍使用目前相機／實際mesh尺寸，但只投影要求的節點。一般滑鼠尋找候選仍需檢查GPU切片，不宣稱O(1)全圖點選。
- `rankRoots`：regex每query/term建立，欄位只正規化一次；掃描全部資料，僅保留Top N候選與總命中數，不配置／排序所有命中的結果陣列。沒有新增完整新聞文字快取。
- 更新已變更JS的asset version。現有靜態HTTP `Cache-Control: no-cache`、API `no-store`維持；不清使用者localStorage或新聞DB cache。

## 量測（本機樣本，非 FPS／延遲保證）

| 路徑 | 修正前 | 修正後 |
| --- | --- | --- |
| 10k資料重建，GPU800／2400 | 805–839 ms；10,000個新聞按鈕 | 165–194 ms；100個新聞按鈕 |
| 同root，20次hover（10k／40k） | 226 ms，0次tree重用 | 3.6–3.7 ms，20次tree重用 |
| 單點吸附guide（800 GPU點） | 1,600次向量clone（1k fixture實測） | 2次（10k fixture實測） |
| Node純關鍵字排名，10k篇＋三詞 | 427–522 ms（三次） | 72–73 ms（三次） |

排名使用8組中／英文、符號、重複詞與零命中query與修正前函式逐項比對roots／分數／evidence／count，全部相同。純排名數字不含80ms UI讓畫面更新、DOM、WebGL或CDP排隊。最終軟體WebGL整合測試的search總時間仍約619ms，不能將純排名72ms說成整個互動完成時間，也沒有量到使用者硬體Chrome的實際FPS。

## 驗證

- 22個CJS測試檔全部通過，含 [test_graph_performance.cjs](../../tests/test_graph_performance.cjs) 的共享索引、cache失效／上限、priority、edge早停、regex數量與原資料不變。
- `/usr/bin/python3 tests/browser_graph_performance.py`：真實WebGL 10k／12k資料；100/400/800/1200/2400預算、相同slice不重設、分頁／Chat跨頁、offscreen選取、keyword、10k分類、時間桶、來源合併／分組／篩選、匯出與browser errors全部通過。測試斷言結構與工作數量，不拿硬體依賴的毫秒當pass門檻。詳細本機輸出 `/tmp/stocknexus-graph-performance.json`。
- `/usr/bin/python3 tests/browser_user_journeys.py`：27項原生點選／搜尋競態／取消／來源切換／7,106筆資料／WebGL context loss與恢復全部通過。
- Python API parity 8項、實際首頁script路由1項通過。沒有因前端修改重跑全部Python後端測試。

本主機用 `/usr/bin/python3` 的 websocket-client與`chromium`。瀏覽器測試也支援 `CHROME_BIN`；不要求全域安裝新的Python套件。

## 保留的限制

800是同時渲染的上限，不是總新聞數，也不是任意GPU都能60FPS。原始結果、時間軸摘要、首次來源合併及索引仍需讀取完整已載入資料；沒有為加速截掉新聞或改後端關聯語意。Backend graph build／快取未在本輪更改，冷建圖或上游等待可能仍慢，應與前端卡頓分開量測。

重建部署後需重新整理既有分頁；只換image不會改已載入分頁裡的JavaScript。普通刷新即可取得新asset URL，不需刪除瀏覽器資料。部署狀態以本次最終驗證為準。

## 本次部署驗證

2026-11-04：`./run.sh up --non-interactive --tailscale off` build成功，既有容器更新為healthy，未改Tailscale routes。由HTTP逐檔核對app／graph-view／explorer-ui／interaction／i18n與工作區SHA-256一致；Tailscale HTTPS首頁200且含 `20261104-performance1` asset版本。Chat仍running。未commit或push。
