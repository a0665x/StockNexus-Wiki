# 目前功能與實作邊界

查核日期：2026-11-07；以目前本地工作區原始碼為準。部署驗收記在 [TESTING](TESTING.md)，不以本頁推斷遠端分支或任意正在執行的服務已同步。

## 當前交接：多股票 Wiki

- 變更位置：`news_atlas/wiki/compiler.py`，背景每股每輪完成一棵 root 樹或一組證據後讓出；分段完整性及已完成內容重用不變。
- 驗證：`python3 -m unittest discover -s tests -q`，252 項通過；`tests/test_wiki_fairness.py`／`test_wiki_forest.py` 鎖住公平輪替、review 去重及大樹分段。文件連結檢查通過。
- Runtime：本次已重建容器並核對 compiler SHA-256 與原始碼相同。七股年度整理的活動狀態應查 jobs/coverage；動畫、排隊與完整發布不同。來源 RSS 缺口不等於 Wiki 已取得內容尚未處理。
- 後續：沿用已確認範圍觀察發布版本與待辦；失敗先查 job.error／拒絕紀錄，不能無限付費重試。Git 同步狀態仍以當下 Git 為準。

## 已完成

| 範圍 | 現在的行為 | 詳細規格 |
| --- | --- | --- |
| 搜尋／儲存 | 必填 EXCHANGE:SYMBOL，先股票再逗號關鍵字；Google／Yahoo RSS、Massive；明確 UTC 區間與來源；股票新聞分庫、完整資料快取 | [來源](SOURCES_AND_CACHE.md)、[儲存](GRAPH_STORAGE.md) |
| 圖譜 | 規則關聯、自適應補合格孤立點、來源分組／混合、星河多 root、3D／時間軸；完整資料與 GPU 預算分離 | [UI](UI.md)、[計算](CALCULATION_METHODS.md) |
| 時間／行情 | 可塑形時間大小、1／3／5／7 後續交易日平均報酬、共同日期軸、K 線／十字線／縮放、缺資料提示 | [PRICE_LENS](PRICE_LENS.md) |
| 工具版面 | 時間與來源工具可拖動、收合、四邊／角落縮放、內容捲動、邊緣停靠分割，尺寸與位置保存 | [TOOL_DOCK](TOOL_DOCK.md) |
| LLM Wiki | 每股票版本化文章／陳述／事件／觀點，逐字引用驗證、增量處理、重審、相依索引、跨文章 RELATED_TO；最後 10 個版本可選，舊引用證據保留 | [WIKI_RUNTIME](WIKI_RUNTIME.md) |
| Wiki 分組／進度 | 詞彙／時間／融合 5、10、15、20 篇；Graph 從完整 News 圖自動採樣樹，直到 Wiki 日期內目標皆涵蓋；Apply 可取消舊工作後按新設定接續 | [WIKI_RUNTIME](WIKI_RUNTIME.md) |
| Wiki 閱讀 | 側欄唯一日期入口；互動分類時間圖、按大類／主題漸進展開；星河選取保留全圖並調暗背景；左右及上下分隔可調 | [WIKI_RUNTIME](WIKI_RUNTIME.md) |
| Chat | News 與 Wiki 各自 session／runtime，共用 UI 語系；重連、晚回應與同來源多視窗同步。模型以允許工具讀目前範圍、引用與操作；輸入框內紙飛機，沒有逐則複製按鈕 | [CHAT_AGENT](CHAT_AGENT.md) |
| 工作區恢復 | News 與 Wiki 獨立保存於主機工作區；新瀏覽器可恢復資料／控制值，切頁不互相重設；浮動工具位置／大小為同瀏覽器偏好 | [WORKFLOWS](WORKFLOWS.md) |
| 啟動／合併 | run.sh 管理單一服務、資料位置、橋接與可選代理；啟動後列 USB 合併範例；留服務開啟、先停止被合併 Wiki 的工作／維護；清單約 6 秒內刷新 | [RUNTIME](RUNTIME.md)、[DATA_MERGE](DATA_MERGE.md) |

## 不應誤認為已完成

- 新聞主要是來源提供的標題／摘要及欄位，沒有普遍抓全文；歷史可用性受來源與帳號限制。
- News 的規則邊不是 LLM 支持關係。Wiki 模型提案通過引用／結構驗證，不代表事實、因果、預測能力已證實。
- 無關群不造線；未成熟行情不補值。四種分類描述影響管道／證據狀態，不構成校準過的可信度排序。
- 情境快照、無前視研究預測、事件階段樣本及完整回測屬 [研究設計](TEMPORAL_WIKI.md)，不是現有可交易系統。
- 合併為逐庫原子、非跨庫全域交易；衝突另存，尚無 GUI 衝突解決器。新增來源資料不會擅自取代使用者正在看的 News 圖或觸發模型。
- 正式驗收使用現有資料且攔截模型呼叫／測試偏好寫入；隔離測試不能證明所有硬體 GPU 或所有上游授權均正常。

## 維護入口

開始修改先讀 [協作偏好](ai-dev-experience-preferences.md)，再讀任務規格與 [互動事故經驗](references/lesson-20261106-interaction-and-delivery.md)。所有公式、範圍與完成條件從 [CALCULATION_METHODS](CALCULATION_METHODS.md) 查找；不要從截圖推測運算定義。
