# 行為合約與回歸線索

上層：[UI.md](../UI.md)、[TESTING.md](../TESTING.md)。這是由現有程式／測試整理的持續合約，不是所有歷史問題都已在使用者環境完全重現的聲明。

## 搜尋不能互相混用

左側 `form` 是 acquisition；圖內 `rootSearch` 是本地搜尋控制區，不是會導航的 form。紙飛機 type=button、Enter preventDefault。圖內搜尋不得清 nodes/links、重設相機、換來源或跳模式；匹配失敗／零筆也保留圖。等待 paint 的期間用 ticket 防止 source filter／清 focus 後套用過期結果。轉圈、禁用按鈕、finally 恢復與明確訊息不能省略。

過往環境曾出現新版前端配舊後端，`/api/capabilities` 404；這不能證明所有「消失」都只有同一原因。UI 圖內排名已移到 JS，降低此功能對新 API 的依賴。API explore 繼續獨立供外部使用。

## 未命中不等於沒有相關新聞

曾以真實 NVDA 快取發現 robot 完整單字匹配召回不到 robots/robotics，故目前使用受限詞首匹配。改規則要維持 Python/JS parity。來源範圍、未取得全文與 query/date 都可能造成召回缺漏；GPU 預算只限制繪製，不應縮小圖內排名的完整資料範圍；不得以合成結果掩蓋。

## 焦點與互動

Hover 只能更新候選 hovered／candidateTrace，不建立 lockedRoots、不壓暗全局、不寫入快照 focus。候選以較淡光暈及提示顯示；離開約 140ms 後清除。點擊／輕觸（非拖拉、非取消）才在無 root 時確認 root；不能吸走既有樹。多 roots 成功後維持鎖定；空白點擊或非輸入欄內的 Esc 只清 focus，不清 graph。單 root 閒置可退場；按住 node／Ctrl-pan 不逾時。拖動和星系繪製使用同一批節點與相機，不能改成獨立圖片場景。

材質可能由 vendor 共用，光暈 adapter 必須 clone per-object、管理 dispose，避免調一節點影響其他材質。Canvas 依 WebGL render 同步投影，不建立會錯位的第二個物理迴圈。淡出同時恢復背景亮度，尊重 reduced-motion。

## 搜尋草稿與快照分離

query/ticker/source/date 的 input/change 即時存草稿；不等待 submit。故意清空／全取消來源也要保存。快速模式重算今天但保留自訂日期草稿。恢復 snapshot 不覆寫左側 query/ticker/dates；exportMeta 則應反映快照的歷史資料。

設定在同 origin；不保證手機／別網址共享 localStorage。key 與草稿分開，禁止把整張表單／localStorage dump 成 payload 或文件。

## 面板不應影響資料

收合只隱藏 body，展開還原 DOM，不重新建立表單或清除 input。拖曳只由標題 handle 啟動，避免搜尋輸入和 checkbox 被當成拖曳。位置應限制在 stage 並能歸位；resize/expand 後操作仍可觸及。面板狀態是偏好，不是圖譜 evidence。

## 變更後要維護的面

- 排名：JS + Python + parity tests + method／docs。
- schema：canonical JSON + OpenAPI + snapshot validator + backward defaults。
- 新來源或地區：provider + query_key version + progress／filters + docs／tests。
- 新 UI 文案：i18n；真實新聞與證據維持 raw。
- 新跨模組 JS 合約：index 資源版本與瀏覽器 reload 驗證。

## 共用森林與日期大小

3D、密度格、逐篇時間軸使用同一 activeTrace；分類／cutoff 不移除 hidden roots，來源取消才可修剪 roots。密度格不可把全部格內文章都說成匹配，必須顯示命中比例。時間大小滑桿不得寫 graphData、改相機、重新抓取或清選取；吸附使用 nodeVal × mesh scale 的實際半徑投影。保存快照包含時間／分類隱藏的路徑節點。

鐘形增益：拖曳不能在按下時跳值、不能重建 geometry 或清 roots；任意曲線段局部塑形持續跟手，遠離筆觸的日期不應改變，取消／失去 pointer capture 要解除 busy。完整透視補償應讓相同日期的投影半徑一致。設定與 schema／快照驗證範圍一致。

## 2026-10-29：時間曲線模組缺少 HTTP 路由

新增 time-lens.js 時只改 HTML，漏掉 server.Handler 的靜態路由表。正式頁面 /time-lens.js 回 404，app.js 在註冊搜尋、語言與 API 問號事件前因 AtlasTimeLens 未定義而中止。舊的瀏覽器回放直接從磁碟嵌入 JS，因此測試通過也無法代表 HTTP 載入完整。

修正：補路由；缺少可選曲線模組時顯示提示並停用該控制，基本搜尋／語言／說明仍初始化。新增 test_every_script_referenced_by_homepage_is_served，自動讀首頁全部 script src（含版本 query）逐一檢查 HTTP 200、JavaScript MIME 與非空內容。browser_startup.py 和真實快取 browser_runtime_search.py 都經實際 Handler 取得 HTML／JS，不能繞過路由讀 JS。前者驗證搜尋送出、語言、問號對話框與 Dashboard 連結，並可模擬缺模組降級。路由修正需要重啟 Python server；只重新整理會繼續使用舊路由。

完整事故證據與交付檢查見 [2026-10-29 前端資源事故](bugfix-20261029-frontend-asset-startup.md)；曲線直接塑形與舊快照相容見 [塑形紀錄](lesson-20261029-curve-sculpting.md)。

跨地區同 URL 保存不可改寫其他查詢的 source 背景，舊缺欄位不能補成新搜尋的國家；金鑰保存／忘記需依序執行，主機回應不包含金鑰。浮動面板收成小圖示後仍可操作，圓點以畫面尺寸驗收。詳見 [本輪紀錄](bugfix-20261029-floating-regions-persistence.md)。


## 現行快取與設定合約

見 [標準流程](../WORKFLOWS.md) 與 [2026-11-02 紀錄](lesson-20261102-rendering-cache-settings.md)：快取鍵包含內容／規則，首事件優先完整快取；暫存線只能沿用未變動端點並明示 pending；已套用偏好不可在刷新時自動改為預設；GPU 預算預設 800、上限 2400。
