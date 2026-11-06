# 2026-11-06 — 範圍理解、交互狀態與交付的持續教訓

入口：[PROJECT_MAP](../PROJECT_MAP.md)。目前契約見 [CURRENT_STATE](../CURRENT_STATE.md)、[計算方法](../CALCULATION_METHODS.md)；可跨專案沿用的思考方式見 [ai-dev-experience-preferences](../ai-dev-experience-preferences.md)。

這是依本次完整需求澄清、程式與回歸證據整理的事故／決策紀錄。較早需求被後續擴充時，不能把舊行為當作現行規格，也不能把需求演進全部稱為實作錯誤。

## 範圍的語意先於批次與畫面

**過程。** 最初 Graph 分組使用畫面部分連線和固定篇數。使用者澄清 root 是點選新聞節點後依現有規則展開的星河樹，篇數可以不同。早期因此只取手動點選樹；後續又明確要求在完整 News 範圍採樣不同根，直到 Wiki 日期內新聞全部被涵蓋，不再依賴手動點選。後一項是現在的契約。

**現行規則。** 使用完整 provider/id universe 與同一套 root 展開規則；GPU 預算不裁切工作輸入。12 個月 News＋1 個月 Wiki，在 12 個月圖上取完整樹，只把 1 個月內唯一目標計入完成率，日期外內容可作脈絡。重疊樹跳過已覆蓋目標，孤立新聞也要處理；輸入分段後全部成功才記整樹完成。

**防重犯。** 在改方法前畫出資料集合與完成分母，核對「選取／顯示／工作輸入／持久資料」四個層級。以 [test_wiki_forest.py](../../tests/test_wiki_forest.py) 的 810 節點、無手動選取、日期外脈絡、分段失敗與 JS 對照驗證，不以畫面漂亮或批次成功代替全範圍完成。

## 設定、工作與顯示不共用同一生命週期

**症狀。** 執行中改 Graph 後，後續仍用舊方法；切 News/Wiki 或換 Chrome 設定檔，模型與節點遺失；兩處日期入口含義不清。

**修正方向。** 將草稿、已套用設定、執行中 job、已發布資料與顯示狀態分開。Apply 先驗證再取消舊 job，從已完成邊界接續；閒置 Apply 不啟動推論。News/Wiki 保持各自 runtime，主機 workspace 恢復圖譜與控制值；Wiki 日期只留 sidebar。純浮動工具位置／尺寸仍是瀏覽器偏好，不能宣稱所有 UI 已跨裝置同步。

**驗證。** [browser_workspace.py](../../tests/browser_workspace.py) 使用兩個全新 Chrome profile，測 News/Wiki 設定分離及恢復；[test_wiki_workbench.py](../../tests/test_wiki_workbench.py) 測執行中切換、取消晚回覆及已完成資料不重算。新功能必須核對同樣的狀態邊界。

## 圖形與手勢須觀察實際幾何／完整事件路徑

| 觸發／舊問題 | 原因與不變條件 | 修正／回歸依據 |
| --- | --- | --- |
| 初次展開 K 線出現巨大紅綠條；曲線控制點覆蓋圖面 | 隱藏時零寬度或錯誤 fallback 被帶入尺寸公式 | 有界初始幾何，展開／resize 再量測；[browser_render_regressions.py](../../tests/browser_render_regressions.py) 先重現 1200 寬燭體，再驗實際寬度 |
| 圖譜偶爾只能平移 | 套件 D 鍵狀態在失焦後殘留；初始化也可能與互動競爭 | 失焦清除修飾狀態；同測左拖旋轉、Ctrl 左拖平移，而非只看 controls flag |
| 展開時間工具立刻又收合 | 避讓在窄畫布找不到位置，撤銷最近一次使用者意圖 | 最近操作工具優先、其他工具讓位；[browser_feedback.py](../../tests/browser_feedback.py) 的窄窗實體點擊 |
| Wiki 選取只剩小團、要按返回，拖視角又失去選取 | 聚焦錯做成刪除／重建資料，click 與 drag 未分清 | 保留節點物件、鏡頭及完整渲染子集；無關變暗，只有空白點擊解除；拖出再返回仍算拖曳 |
| Wiki header 壓住語言／設定 | 固定 44px 偏移不能反映實際 header 高度 | ResizeObserver 量測實際底部；三分隔線與聊天輸入一起實測，見 [browser_wiki_layout.py](../../tests/browser_wiki_layout.py) |
| 調整浮動視窗高度時頂邊漂移 | 底部定位令新 height 自動改變 top，若只加位移會計算錯 | 設定新尺寸後讀新 rect，再補償期望位置；取消復原幾何，停靠另用分割樹 |

調整尺寸應保留圖譜資料與焦點；標題不隨 body 捲走。新 [browser_floating_resize.py](../../tests/browser_floating_resize.py) 用實體指標驗證四邊／角代表路徑、捲動、取消、保存及停靠往返。此測試用隔離前端 fixture；正式 HTTP 資產另由 HTTP 回歸／交付檢查驗證，不能混稱。

## 語意、證據與呈現要一致

- 疏散的 Wiki 不應以憑空連線「改善」。顯示類別曾隱藏引用端點，需保留實際引用背景；跨文章關係由模型提案、兩端引文及驗證後發布。類別數與可信度不是同一件事。
- 詳情的「3 天不足」曾容易與 News 的 7 天設定混淆。現在目前觀察跟隨當下天數與最新本機行情，生成時市場證據另列；不足 N 天要列已取得天數與最後行情日，不冒充零報酬，也不改寫舊推論。
- Chat 的中間訊息不需每段附複製按鈕；聊天行動由已授權 agent 流程推進。輸入送出使用欄位內飛機，不另占整列。省掉多餘操作不等於擴張模型寫入授權。
- 初版書堆／鎬子雖符合「挖掘」字面，視覺過於漫畫。改為細線文件→掃描→知識連線，資產 [knowledge-mining.svg](../../dist/knowledge-mining.svg)，CSS 控制動畫。只有真實 running 播放，停止／排隊靜止，減少動態效果偏好有效；輪詢不重建動畫 DOM。

## 在線匯入須驗證使用者看得到的下一步

原工具已有 SQLite 鎖、快照、預檢與逐庫交易，但文件仍要求停服，頁面也未定期重新讀取股票目錄。只驗證 DB rows 增加，不能證明「服務開著匯入後，下拉看得到」。

現在 `run.sh up` 印出對應實際 data 的預覽／合併命令；Web UI 可保持運行，欲合併股票的 active Wiki 工作／持續維護必須先暫停。工具在鎖內拒絕忙碌目標，不自行停工或啟動模型。目錄約 6 秒刷新，保留選中項、空白新股票選項、模型／日期與 News runtime；選定歷史版本不跳到最新。只匯入新聞不會虛構已建立 Wiki。

[browser_live_merge.py](../../tests/browser_live_merge.py) 在隔離真實 HTTP／Chrome 中實際執行 CLI dry-run／合併，檢查新增股票、原股票版本更新、選擇保留及無模型呼叫。這比 mock 一個新的下拉清單更接近使用者路徑。

## 驗收工具與部署也是錯誤來源

- 新 JS／SVG 必須加入 server 靜態白名單與 HTML 版本參數；file:// 注入測試不會發現漏 HTTP route。既有事故見 [frontend-asset-startup](bugfix-20261029-frontend-asset-startup.md)。
- CDP 按住拖曳的 mouseMoved 同時指定 `button=left` 和 `buttons=1`；零移動 click 不送多餘 move。圖很密時先確認點是空白，暗色節點仍是節點。
- 真實服務 QA 用獨立瀏覽器設定檔，導覽前 `Page.enable` 再裝攔截器；攔截 workspace 寫入與模型／來源呼叫，避免測試偏好或用量污染使用者。
- 更新服務前保存工作設定／一致備份；只接續原本已授權且未完成的工作，原本停止的保持停止。核對 healthy、實際 HTTP 資產及資料差異，不能把本地 source 修改說成部署完成。
- 各次歷史結果／限制保留在 [TESTING](../TESTING.md) 與 [CHANGELOG](../CHANGELOG.md)；若使用者同時改資料，不可把所有雜湊差異一概當成測試污染或無視它。

## 下次修改的最短檢查

先讀使用者當下意圖及通用偏好 → 找到狀態／資料集合的擁有者 → 定義這次動作不應改的相鄰狀態 → 建立能重現症狀的真實路徑 → 修正後檢查該路徑與必要相依項 → 同步目前規格與新教訓。只把有證據、可重用的思路升格到偏好文件，不加入與修改無關的批准或測試負擔。
