# 目前狀態

## 已部署：Tailscale Chat（2026-11-14）

0b069a5 已在使用者明確同意暫停 L1 後部署。exact HTTPS Origin＋Tailscale Serve 使用者 allowlist 已啟用；正式 Chromium 經 Tailscale 顯示已連線並完成情境同步，未發送付費模型提問。7 Python／13 Node／Chromium 拒絕連線測試先前通過，見 CHAT_AGENT。年度 L1 保留成果，依部署前工作紀錄接續 medium；即時進度以 private ledger 為準。


## 最新交接：股票身分綁定（2026-11-14）

既有 Wiki 股票鎖定；新建改由非空新聞 DB 下拉選取。伺服器 news_db 模式不使用主頁別股輸入；過期／錯股 graph 回應不得覆寫選取。見 WIKI_RUNTIME、API。新增 configure 閒置模型設定路徑避免單改 reasoning 重建全年圖譜；有活動 extraction/classification 時拒絕。

本輪驗證：87 項 Wiki Python、9 項 Graph storage、9 項 Chromium 身分切換檢查通過；新增資料範圍、快照身分、空庫與模型設定邊界測試。舊 browser_wiki.py 因假設自動預覽而在 planRelease 步驟失敗，未宣稱全套舊 UI 驗收通過。本輪以 browser_wiki_identity.py 測實際 DOM 互動、即時回饋及晚回應。

正式確認 14 個非空新聞 DB；一年來源取得仍有供應商缺口。年度批次於 2026-11-13T17:20Z 因模型用量上限停止，既有成果保留；本次使用者指定後續 gpt-6.1-sol/medium，取代下方 high 歷史設定。即時結果以 private l1-batch.json 為準，不依歷史行列重送工作。程式 04f79b8 已部署並推送 llm_wiki；HTTP JS SHA256 相符。正式 Chromium 切換 SNDK 鎖定與新建 14 DB 選項通過。14 股 medium 設定已由公開 API 保存；使用者再次要求啟動且舊額度重試時間已過後，執行一次有界接續，先 NVDA、成功新發布後放行其餘，並保留之前失敗歷史；詳見本批 references。


## 最新本機交接：年度資料與研究（2026-11-14）

本次新授權更新既存有效股票與指定研究名單，共 14 個：NVDA、AMD、AAPL、TSLA、SpaceX/SPCX、META、VIX、QQQ、ASML、AMZN、RDW、SNDK、GOOGL、TSM。固定 UTC 2025-11-14→2026-11-13，行情至美國 11/12 完整交易日；gpt-6.1-sol/high、Graph root、增量 update。保留既有資料與 revisions，不恢復舊七股 heartbeat。先讀 `data/private/annual-research-20261114/l1-batch.json` 與取得紀錄；不要依舊進度重送工作。

Git 已從 8285c09 fast-forward 到 f63e896 並部署，24 Python + 12 Node 測試通過，HTTP 靜態資產核對成功。AMD 已實際由 v27 發布到 v28；14 股來源取得與有界補抓已完成一輪（仍有來源缺口）；年度 L1 尚在處理，不宣稱全部完成。市場研究、來源身分、BDD 邊界、報告與續作見 [本輪交接](references/annual-research-batch-20261114.md)。以下「待部署」與其他主機的空庫觀察是歷史狀態，不能覆蓋此處的本輪實測；下次仍須查即時 runtime。

## 最新待部署修正（2026-11-10）

已補上已發布成果入口、被篩選隱藏的空圖說明、首次載入失敗後恢復，以及版本變更上邊界拖曳。正式查核時 GOOGL 有 611 個節點紀錄／v47，工作 running，保存的分類篩選為 __pending；沒有清庫或重送模型。隔離 Chrome 11 項新檢查與 48 項既有布局檢查通過；連同下方 root 閱讀功能建置待部署，目前正式服務仍未重啟。

## 待部署：工作樹閱讀入口（2026-11-09）

目前 root 可跳回 News 並高亮凍結成員的功能已實作，15 項隔離瀏覽器檢查與 11 項相關後端測試通過（低預算補強另重跑 8 項 forest 測試），容器映像已建置。正式工作仍 running（查核時 root 12/100、done270），為避免中斷與重做，尚未重啟部署；使用者需選擇更新時機。這個入口不改去重／工作／模型設定；快照成員與目前連線的差異會明示。

## 最新本機觀察：smoke test 後（2026-11-09）

使用者已重新建立 GOOGL 新聞／Wiki；下方空資料起點僅為先前清庫當時紀錄。兩次 Graph medium 工作第一段 12 篇都在約 120 秒失敗；已修正橋接為統一 600 秒上限並區分取消／逾時，11 項隔離 Node 測試通過。未清除這次新資料，也未自動重送模型。詳見 TESTING 的 medium root 紀錄。

## 有效交接：本機 smoke test 起點（2026-11-09）

- 本機實際專案為 `/home/nvidia/Desktop/AI_WS/stocknexus-wiki`，分支 `llm_wiki`，程式版本 `8285c09`；本輪只整理文件與重置資料，未修改產品程式。環境提示中的 `news-atlas` 路徑已過時。
- 已核對共享 L1／Classifier／Taxonomy／Lens L2、研究進度與既有結果讀取恢復。修正文件中過時的四分類／純 Thesis 統計描述，以及漏寫的 root 每段 12 篇限制；目前契約見 CALCULATION_METHODS、WIKI_RUNTIME、RESEARCH_LAYERS。
- **使用者明確要求刪除全部 DB 供 smoke test**：停止服務後刪除 58 個專案資料庫及 WAL／SHM 等檔案，共 1,642,643,456 bytes，包含舊備份、新聞／價格／關聯、Wiki／研究與 workspace；清除衍生圖布局。保留登入憑證與非 DB 紀錄，不另留 DB 備份。舊工作與舊成果不再接續。
- 已重新啟動 localhost:8765，Chat bridge ready。實測新聞、coverage、attempts、snapshots 均 0；Wiki instruments 為空陣列，workspace 為空物件。啟動會建立空 schema DB，不能用「有 DB 檔」判定舊資料殘留。
- 24 項研究／健康後端測試，以及隔離真實 HTTP／Chrome 研究流程測試通過；沒有啟動正式模型工作。實際來源搜尋與模型品質 smoke test 留待使用者操作，見 [SMOKE_TEST](SMOKE_TEST.md)。
- 瀏覽器記憶體與偏好獨立於 DB；先關閉舊分頁，以無痕視窗或新 profile 開始。不要讓舊頁把記憶中的 workspace 再存回。這次新測試不沿用下方歷史主機的日期、股票與工作進度。

## 歷史交接：其他主機的 2026-11-08 紀錄（非本機即時狀態）

以下是保留的歷史證據；本機資料與下一步以最上方 2026-11-09 交接為準。

- **最新交付**：README.md／README.en.md 分開中英文、頂端互連，各自嵌入最新有明確輸出與箭頭的流程圖；移除影片介紹，聚焦問題與操作。研究進度／目錄不再掃描匯入整份新聞；L2 中央同步顯示排隊／整合／載入與等待秒數，讀取暫時失敗保留 job 並恢復，不重跑模型。隔離 Chromium 回歸及 23 項研究測試通過；2026-11-07 16:09:48 UTC 更新部署 healthy，HTTP JS/CSS 與原始碼相同。正式 HTTPS 瀏覽器已驗證 GOOGL 5 個既有 L2 節點可載入；詳細證據見 TESTING。
- **本輪正式研究觀察**：GOOGL「動能」既有工作於 15:52:50 UTC 完成（約 67 秒），含 5 個 L2 claims／20 筆入選 L1 claims；唯讀瀏覽器可載入全部 5 個 L2 節點。截圖期間中央缺進度已重現；無法由截圖證明該正式工作曾永久卡住。額外驗證並修正已完成結果 GET 失敗會遺失追蹤的路徑。本輪沒有新增付費模型工作，也未清理資料；停止的 L1／年度工作保持停止。

- **前次文件交付**：README 已加入中／英三層概念圖，對應 News→共享 L1→客製 L2；修正舊預覽／確認整理描述。2026-11-07 本輪從 `4e7ce10` 核對原始碼與限制，只改媒體／文件，未部署、未重跑 UI 或模型；圖不是完整能力驗收。見 RESEARCH_LAYERS 三層視覺模型及 TESTING。

- **產品目的**：累積同股票、與 query 無關的共享 L1 觀點；Classifier／Taxonomy 是索引支援，不是第三層。使用者研究問題產生 owner／Lens 範圍的 L2，整合催化、反證、條件與缺口，不只查核新聞日期。意圖與已取代設計見 [RESEARCH_LAYERS](RESEARCH_LAYERS.md)；目前只是第一條垂直流程，完整長期目標尚未全部驗收。
- **成本與資料**：顯示預算／來源勾選／開頁不等於重新推論；分組方法共用資料身分及已完成成果。先救援相容資料，不預設清庫。快取、快照及 merge 邊界分別查 [CALCULATION_METHODS](CALCULATION_METHODS.md)、[DATA_MERGE](DATA_MERGE.md)。
- **目前有效測試範圍**：使用者後續指定 GOOGL 最近一個月；本次實際凍結為 UTC 2026-10-07→2026-11-07，gpt-6.1-sol/high。早先七股年度 heartbeat 已暫停，不復活它或其他取消工作。未來若新開「最近一月」工作，先確認當時日期及授權；不能把既有工作偷偷延長。正式驗收不新增付費模型探測。
- **Git 與部署分開**：實際專案 `/home/a0665x/Desktop/AI_AGX_WS/StockNexus-Wiki`，branch llm_wiki（環境 GraphNews 已過時）。本輪從乾淨 `e325392` 開始；部署證據與測試見上方及 TESTING。下一 session 仍須重查 Git／工作樹／執行服務，不能把歷史交付當即時狀態。
- **最後進度觀察，非即時狀態**：08:25 UTC，原 GOOGL 工作 v441／done71 接續；沒有證明整月或所有分類完成。資料預檢保留原成果，未清庫。來源取得完整度、Wiki coverage、分類完成度與觀點正確性分開判斷。
- **最近驗收證據**：正式 15 項 UI 流程、5 次主入口回饋 133–1044ms；隔離 News 33、native 23、Wiki 48、研究／工作區／Chat 及 22 Node suites。完整命令、失敗原因及限制查 [TESTING](TESTING.md)「跨步驟互動驗收」。2 秒是可見回饋，不是模型完成期限或永久 SLA；本次文件整理沒有重跑這些行為測試。
- **下一步**：有新任務時先對照相關契約與當前程式；要追蹤 GOOGL 則查現有 jobs／coverage／receipts／log 與持久重試紀錄，不另建重複工作。價格特徵／敘事基線、複雜語意 Lens、多 owner 與真實模型品質尚有限制，詳見 RESEARCH_LAYERS。不要為補齊長期願景而擴大當前授權。
- **延續維護**：新明確修正合併到領域契約與 [偏好紀錄](ai-dev-experience-preferences.md)，標明取代關係；最新交接更新本節，詳細證據進 TESTING／CHANGELOG。skill 只提供讀寫方法，並不自帶聊天記憶。

## 歷史觀察（保留追溯，不代表目前工作狀態）

2026-11-07 完整交互驗收：實際操作跨 News／Timeline／Wiki／L2／設定／Chat，修正 L2 主畫面缺少載入／空／失敗重試提示、晚回覆搶回 L1、快照無回饋／重複點擊／舊回應覆蓋，以及背景 News 重繪改掉 Wiki 設定標籤。程式 `8480627`／`609f404`／`ca7c47a` 已推送 llm_wiki，最後補丁 08:24 UTC 安全部署 healthy、實際資產一致。正式 15 項流程 PASS、入口 133–1044ms，包含新導覽清除失效 spinner；隔離 News 33、native controls 23、Wiki 48、L2／工作區／Chat 與 22 Node suites PASS。完整 BDD、初始測試失敗原因、執行命令與限制見 [TESTING](TESTING.md)。資料無遷移或刪除；GOOGL 原月工作 v441／done71 接續，不代表整月完成。

2026-11-07 按鈕回饋：Wiki／L2 非同步操作加即時 busy、防連點與失敗復原；停止成功拒絕舊 poll，導航保持可用。程式 `066d10b` 已推送 llm_wiki 並於 08:03 UTC 安全部署，正式資產一致、容器 healthy。真實正式頁面三輪 22 次回饋 84–1314ms；Wiki 隔離 48 checks、L2 流程與 22 Node suites 通過。2 秒指可見回饋，不是模型完成時間；寫入按鈕在隔離資料驗證。實作 `dist/wiki-view.js`／`research-view.js`，重跑 `tests/browser_wiki_live_feedback.py --url <服務網址>`，完整證據及測試 driver 修正見 [TESTING](TESTING.md)。原 GOOGL 月工作 v433／done43 持續 running，設定與成果保留；整月仍未完成，沒有新付費測試工作。

2026-11-07 分類一致性：選單、柱狀圖與群列表共用模型分類群索引，原財務影響只留詳細屬性。新增噪聲／查核更正詞彙與相容舊 assignment 的增量升級；尚未分類明示，不以舊分類猜補。實作／升級見 RESEARCH_LAYERS，測試及部署見 TESTING。程式 `0b5915c` 已部署並推送；七個有效 Wiki 的兩術語已增量加入，重跑 unchanged，舊 assignment 保留。GOOGL 原月工作仍在原設定下推進至 v425／done 21，不代表整月完成。

2026-11-07 GOOGL 正式月驗收發現舊 context revision 導致 CAS 衝突，及失敗／停用旗標分次提交導致重啟誤續跑。已保留 421 個原版本並取消誤建工作；修正當前 context 篩選、原子終止與拒絕用量紀錄。修正後正式續跑已發布至 v422、月覆蓋 921/2760；其餘仍在背景整理。驗證以 TESTING 最新記錄為準，首批成功不是整月完成。

2026-11-07 最新資料前置：GOOGL 正式庫唯讀預檢通過（13943 article revisions、421 versions、2164 nodes、1373 edges），保留歷史、不清空。維護測試改為 UTC 2026-10-07→2026-11-07，2760 篇中 921 可重用、1839 待整理，694 舊觀點群可補分類。已修正補分類未遵守日期的問題；來源與實際部署／執行證據見 WIKI_RUNTIME／TESTING。預檢是結構與引用核對，不等於事實審查。

2026-11-07 最新修正：Wiki 狀態 GET 重跑初始化造成 SQLite 寫鎖／503，已改為已初始化 schema 純讀；coverage 有界快取、輪詢單飛、重進重用圖。整理入口合併為單一開始／繼續，明確點擊才 plan/jobs，含缺漏分類。首次錯誤重試、保存篩選同步圖形均有瀏覽器回歸。來源：`news_atlas/wiki/store.py`、`compiler.py`、`dist/wiki-view.js`；測試與部署以 [TESTING](TESTING.md) 本次紀錄為準。無資料刪除或破壞性 migration。 已部署 8765 且原 TSM 佇列接續；程式修正 commit `1457de8` 已推送 llm_wiki，實際延遲與保留設定核對見 TESTING。

2026-11-07 本輪：依使用者十項畫面回饋，整合共用 L1/L2 圖譜與 Chat、模型分類與舊群補足、唯讀分類定位、進度區尺寸保存、L1 忙碌守門。原始碼與邊界見 [RESEARCH_LAYERS](RESEARCH_LAYERS.md)，測試／部署證據見 [TESTING](TESTING.md)。既有資料保留；新 L1 prompt 為 wiki-extract-v8。

# 目前功能與實作邊界

查核日期：2026-11-07；以目前本地工作區原始碼為準。部署驗收記在 [TESTING](TESTING.md)，不以本頁推斷遠端分支或任意正在執行的服務已同步。

## 雙層研究與合併資料的實作摘要

- 主契約：[RESEARCH_LAYERS.md](RESEARCH_LAYERS.md)，完整使用者架構來源位於 `L2_Archirecture/`。已接到既有 SQLite／單模型槽／API／Wiki，沒有另建 mock 平台。舊 L1 保留，新 L1 加入條件與修訂原因；分組方式共用同一資料庫。
- 新入口：Wiki → 我的研究 · L2。分類／全文 → 固定 snapshot → L2 → live/pinned → 增量刷新與來源圖。分類、模型推論、價格及事後 outcome 分開；新 inference 另做一次有界語意審核。
- merge_data 修正匯入 captured_at 前視污染，增加引用 span/hash 與版本檢查；未知未來 schema 不得被開庫降級。來源／目標備份與衝突保存沿用。
- 初版曾驗證 279 Python tests、Node chat suites、隔離 Chrome 研究與 live CLI merge；這是歷史結果，後續各輪範圍以 [TESTING](TESTING.md) 為準。正式資料不作額外付費模型測試。
- 舊七股 heartbeat 已暫停；當時背景 AMD 的觀察已被後續 GOOGL 月驗收範圍取代。不要依歷史段落恢復取消／額度失敗工作；以本頁有效交接及即時 jobs 為準。
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
- 無關群不造線；未成熟行情不補值。舊四種財務影響／證據狀態只留詳細屬性；分類選單與圖表已改用 Classifier，不構成校準過的可信度排序。
- 情境快照、無前視研究預測、事件階段樣本及完整回測屬 [研究設計](TEMPORAL_WIKI.md)，不是現有可交易系統。
- 合併為逐庫原子、非跨庫全域交易；衝突另存，尚無 GUI 衝突解決器。新增來源資料不會擅自取代使用者正在看的 News 圖或觸發模型。
- 正式驗收使用現有資料且攔截模型呼叫／測試偏好寫入；隔離測試不能證明所有硬體 GPU 或所有上游授權均正常。

## 維護入口

開始修改先讀 [協作偏好](ai-dev-experience-preferences.md)，再讀任務規格與 [互動事故經驗](references/lesson-20261106-interaction-and-delivery.md)。所有公式、範圍與完成條件從 [CALCULATION_METHODS](CALCULATION_METHODS.md) 查找；不要從截圖推測運算定義。

### 2026-11-10 L2 論證閱讀更新（尚待部署）

已在前端加入 saved support/counter 分支（青綠菱形／橙色方塊）、精確 L1 引用聚焦、節點類型／分類色標與雙語提示。無引用分支不建立；純投影不改保存資料、不呼叫模型。細節見 RESEARCH_LAYERS，11 項新瀏覽器檢查通過；既有工作不為此次 UI 更新中斷。

同輪 48 項版面／手勢與完整研究 HTTP／Chrome 回歸通過，更新映像已建置；正式服務仍未重啟，不能把原始碼完成當作已部署。

### 2026-11-10 後續閱讀與 Chat 整合（已部署）

固定文字圖例已改為當前可見 mesh 的立體縮圖；英文分類及 L2 入口、新 URL 語系已修正。Chat 安全 Markdown 表格完成，新增唯讀 read_research MCP，從 DB API 讀取完整 L2/L1 引用及近期／快照時間水位。BDD、既有 Chat／研究回歸及一次真實模型隔離抽查完成；細節與限制見 [CHAT_RESEARCH_BDD](CHAT_RESEARCH_BDD.md)。在確認正式模型槽閒置後，已用標準啟動器更新 frontend 容器及 host bridge。健康、HTTP 資產雜湊、正式頁面英文分類／L2 入口及立體圖例 PASS；DB／設定保留，未啟動新的整理工作。此交接取代上方歷史待部署狀態。

### 2026-11-10 L2 側欄語系補強（已部署）

完整展開側欄、保存歷史、忙碌 tooltip、排隊／執行秒數、中斷／重連／恢復的介面訊息改由 L2 自有語系流程呈現；原始研究問題與來源內容保留語言。載入狀態使用獨立狀態值。`browser_research_locale.py` 10 項檢查及 `browser_wiki_reading.py`、`browser_research.py` 通過；前者包含修正前確實失敗的忙碌案例，未呼叫模型。模型槽閒置後發布，HTTP 資產雜湊與本地一致，正式 Chrome 英文左欄無殘留中文介面與 JS 錯誤；正式服務未人工建立忙碌工作，該狀態以隔離測試驗證。

### 2026-11-11 研究問題目錄（已部署）

L2 左側新增多面向篩選與問題搜尋，納入已完成未另保存的結果，已保存版本歷史不重複列卡。圖上方、節點提示明示研究問題。面向依問題文字規則產生，舊資料只讀補足、不重跑模型；目前沒有手動改面向或多問題同圖，細節見 RESEARCH_LAYERS。24 項研究測試、語系／篩選測試、真實 HTTP/Chrome 研究流程與論證圖回歸通過。模型槽閒置時發布，正式頁面已讀取既有 GOOGL 結果並驗證目錄→圖中問題一致、中英往返無 JS 錯誤；測試阻擋 workspace/API 寫入，未變更使用者偏好或建立研究。Live 與 pinned 同一結果仍是兩張不同保存模式的卡片，面向數量以卡片計。
