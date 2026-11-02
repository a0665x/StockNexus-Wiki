# WebGL、關聯快取與設定還原：2026-11-02 排錯紀錄

上層：[標準流程](../WORKFLOWS.md)、[來源與快取](../SOURCES_AND_CACHE.md)、[UI](../UI.md)。

## WebGL：同一網址不代表同一渲染環境

症狀：使用者 Chrome 回報 `THREE.WebGLRenderer: Error creating WebGL context`，重啟電腦後仍失敗；其他測試瀏覽器可正常顯示。

證據與限制：

- 容器 healthy，HTTP `app.js` 雜湊與工作區相同，排除該次測試的舊前端資源。
- 沙箱內 GPU 不可見及 Chrome 無法啟動，不是使用者主機驅動故障證據；主機 NVIDIA 驅動實測正常。
- headless Chrome 使用 SwiftShader，通過不代表硬體路徑通過。另開隔離桌面 Chrome 確認 RTX 2080 Ti／OpenGL，可載入真實 NVDA 快照。
- App 使用者分頁重新搜尋 NVDA 顯示 96 篇／277 edges，時間軸切回 3D 正常，捕捉日誌無錯誤。
- 使用者 Chrome 的原始訊息證實其 WebGL context 建立失敗；但未取得該瀏覽器完整 GPU 狀態，**底層設定／政策／程序／驅動原因未確定**。使用者後來表示可行，不能記成已由程式修復。

此輪診斷沒有以關閉瀏覽器保護或替換 2D renderer 解決問題。3D-only 保留原錯誤與重試，時間軸仍可使用。

下次先看：出問題的瀏覽器 Console、`chrome://gpu` 的 Feature Status／Problems Detected、圖形加速設定、同一組搜尋與規則。
不要只報「測試通過」，必須註明軟體／硬體渲染、隔離 profile／使用者分頁及實際資料範圍。

## Already in DB，但 edges 等待很久

預期：已存在的完整圖譜立即可見，新新聞補抓不應令既有線全部消失。

已證實原因：

1. 原本只有 8 組程序內 LRU，重啟後消失；任何完整輸入變動可能重算。
2. 第一版持久快取放在來源補抓完成後才讀，初始事件仍只有節點，即使命中也晚出線。
3. 初始 DB rows 與來源完成時的 deduplicate/enrich rows 表示不同，早期 lookup 需統一正規化。
4. AAPL 兩次搜尋來源紀錄 3932→4057，資料確實增加；不能強行把舊全圖當新版最終關聯。
5. 模組對既有文章反覆辨識實體、主題及分類；小型 profile 顯示文字規則比對占用顯著時間。

修正位置：

- [graph_cache.py](../../news_atlas/graph_cache.py)：完整輸入／分類／設定／版本鍵，SQLite 壓縮 sidecar、程序內相同請求共用 Future、結果物件隔離、32 組／256 MiB payload 預算與故障回退。
- [server.py](../../server.py)：`lookup_cached` 在首事件及來源更新時讀完整圖；`retain_known_edges` 僅保留兩端文章完全未變動的舊證據，帶 pending，最終整圖替換。
- [model.py](../../news_atlas/model.py)、[channels.py](../../news_atlas/channels.py)：各 8192 項純特徵 LRU，按實際文字／符號／定義失效，不覆寫目前來源或 fetched_at。
- [app.js](../../dist/app.js)：保留線時說明更新狀態；不把來源抓取 spinner 當成 GPU 初始化失敗。

量測不可混用：

| 場景 | 結果 | 限制 |
| --- | --- | --- |
| 真實 NVDA 8387 去重文章完整建圖 | 冷計算 42.308s，清空記憶體 LRU 後磁碟命中 1.809s，22948 全局 edges | 單次後端量測，不含來源／傳輸／GPU |
| AAPL 搜尋日誌 | 新增資料後全圖 miss，compute 約 15s | 不是快取失效 bug 的唯一證據 |
| 修正後容器 AAPL 第一事件 | 2.105s、3804 節點／10738 edges、pending=false | 禁止來源呼叫與 edge 重算的 generator 驗證，不是端到端時間 |

尚未實作持久 pair evidence、跨搜尋集合增量選線、閒置全 DB 背景補算或跨程序 single-flight。
完整快取不能代替最新來源覆蓋，也不能直接把全 DB 最終 edges 篩選成任意子集合結果：度數預算與自適應孤立點選線依當次集合而變。

## 預算與設定：不要混淆顯示、草稿與已套用規則

- GPU 預設 800，現可選至 2400；線最多為該預算三倍，只畫兩端都在切片內的線。完整新聞／快照／匯出不裁切。
- 新選項使單純除二可能得到不存在的 1000／600；故障退到不超過半數的既有選項，最低 100。
- Edge settings 必須成功套用才持久保存；未提交草稿、失敗或晚到回應不能取代已生效規則。
- 舊啟動遷移曾把明確保存的 original/general 改成 unified；已移除。新使用者才用 unified，刷新忠實讀取保存值。
- 快照還原、本機偏好與左側搜尋草稿分開。跨瀏覽器／origin 不共享 localStorage；新品牌名稱不可直接改掉 `graphnews.*` 鍵。

## 驗證與部署

```bash
python3 -m unittest discover -s tests -q
for test in tests/*.cjs; do node "$test" || exit; done
python3 tests/browser_user_journeys.py
python3 tests/browser_user_journeys.py --no-webgl
python3 spec/scripts/verify_docs.py
```

早期關聯／特徵修改後 124 Python tests、全部 CJS 與 Chrome journey 通過。
2400／偏好修改另跑 render-budget、relation-settings、graph-cache 回歸，以及含 2400 切換的 Chrome journey。
`--no-webgl` 在前段診斷通過，不能寫成每次修改後都有重跑。

執行中容器以 `./run.sh up --non-interactive` 更新並確認 healthy；前端刷新載入新資源。
這些是當時部署證據，不保證下一個 session 仍在同一版本；此紀錄未宣稱 GitHub 已推送。
