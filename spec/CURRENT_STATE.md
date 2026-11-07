# 目前狀態

2026-11-07 分類一致性：選單、柱狀圖與群列表共用模型分類群索引，原財務影響只留詳細屬性。新增噪聲／查核更正詞彙與相容舊 assignment 的增量升級；尚未分類明示，不以舊分類猜補。實作／升級見 RESEARCH_LAYERS，測試及部署見 TESTING。

2026-11-07 GOOGL 正式月驗收發現舊 context revision 導致 CAS 衝突，及失敗／停用旗標分次提交導致重啟誤續跑。已保留 421 個原版本並取消誤建工作；修正當前 context 篩選、原子終止與拒絕用量紀錄。修正後正式續跑已發布至 v422、月覆蓋 921/2760；其餘仍在背景整理。驗證以 TESTING 最新記錄為準，首批成功不是整月完成。

2026-11-07 最新資料前置：GOOGL 正式庫唯讀預檢通過（13943 article revisions、421 versions、2164 nodes、1373 edges），保留歷史、不清空。維護測試改為 UTC 2026-10-07→2026-11-07，2760 篇中 921 可重用、1839 待整理，694 舊觀點群可補分類。已修正補分類未遵守日期的問題；來源與實際部署／執行證據見 WIKI_RUNTIME／TESTING。預檢是結構與引用核對，不等於事實審查。

2026-11-07 最新修正：Wiki 狀態 GET 重跑初始化造成 SQLite 寫鎖／503，已改為已初始化 schema 純讀；coverage 有界快取、輪詢單飛、重進重用圖。整理入口合併為單一開始／繼續，明確點擊才 plan/jobs，含缺漏分類。首次錯誤重試、保存篩選同步圖形均有瀏覽器回歸。來源：`news_atlas/wiki/store.py`、`compiler.py`、`dist/wiki-view.js`；測試與部署以 [TESTING](TESTING.md) 本次紀錄為準。無資料刪除或破壞性 migration。 已部署 8765 且原 TSM 佇列接續；程式修正 commit `1457de8` 已推送 llm_wiki，實際延遲與保留設定核對見 TESTING。

2026-11-07 本輪：依使用者十項畫面回饋，整合共用 L1/L2 圖譜與 Chat、模型分類與舊群補足、唯讀分類定位、進度區尺寸保存、L1 忙碌守門。原始碼與邊界見 [RESEARCH_LAYERS](RESEARCH_LAYERS.md)，測試／部署證據見 [TESTING](TESTING.md)。既有資料保留；新 L1 prompt 為 wiki-extract-v8。

# 目前功能與實作邊界

查核日期：2026-11-07；以目前本地工作區原始碼為準。部署驗收記在 [TESTING](TESTING.md)，不以本頁推斷遠端分支或任意正在執行的服務已同步。

## 當前交接：雙層研究與合併資料驗證

- 主契約：[RESEARCH_LAYERS.md](RESEARCH_LAYERS.md)，完整使用者架構來源位於 `L2_Archirecture/`。已接到既有 SQLite／單模型槽／API／Wiki，沒有另建 mock 平台。舊 L1 保留，新 L1 加入條件與修訂原因；分組方式共用同一資料庫。
- 新入口：Wiki → 我的研究 · L2。分類／全文 → 固定 snapshot → L2 → live/pinned → 增量刷新與來源圖。分類、模型推論、價格及事後 outcome 分開；新 inference 另做一次有界語意審核。
- merge_data 修正匯入 captured_at 前視污染，增加引用 span/hash 與版本檢查；未知未來 schema 不得被開庫降級。來源／目標備份與衝突保存沿用。
- 驗證：279 Python tests；Node chat suites；真實隔離 Chrome 研究與 live CLI merge。實際數量及部署結果見 [TESTING](TESTING.md)。正式資料不作付費模型測試。
- 舊七股 heartbeat 因本次架構工作已暫停；背景 AMD 保留並等發布空檔更新。其他額度失敗工作不自行復活。
- 邊界：確定性 Lens parser、詞彙分類、單人 local owner、無合格歷史價格特徵。模型語意審核不等於證明，來源抓取缺口另計；不能把第一條垂直流程說成完整長期研究平台。

## 已完成

| 範圍 | 現在的行為 | 詳細規格 |
| --- | --- | --- |
| 搜尋／儲存 | 必填 EXCHANGE:SYMBOL，先股票再逗號關鍵字；Google／Yahoo RSS、Massive；明確 UTC 區間與來源；股票新聞分庫、完整資料快取 | [來源](SOURCES_AND_CACHE.md)、[儲存](GRAPH_STORAGE.md) |
| 圖譜 | 規則關聯、自適應補合格孤立點、來源分組／混合、星河多 root、3D／時間軸；完整資料與 GPU 預算分離 | [UI](UI.md)、[計算](CALCULATION_METHODS.md) |
| 時間／行情 | 可塑形時間大小、1／3／5／7 後續交易日平均報酬、共同日期軸、K 線／十字線／縮放、缺資料提示 | [PRICE_LENS](PRICE_LENS.md) |
| 工具版面 | 時間與來源工具可拖動、收合、四邊／角落縮放、內容捲動、邊緣停靠分割，尺寸與位置保存 | [TOOL_DOCK](TOOL_DOCK.md) |
| 雙層研究 | 分類／全文檢索、Lens、快照、L2 與 live/pinned、來源圖；第一版限制見契約 | [RESEARCH_LAYERS](RESEARCH_LAYERS.md) |
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
