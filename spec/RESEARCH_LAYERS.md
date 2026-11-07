# 雙層研究 Wiki 契約與 BDD 邊界

狀態：第一版垂直流程已接入；驗證與限制見本文末段。

## 已確認產品意圖與取代關係（2026-11-07）

以下是使用者明確要求的設計方向，不代表所有目標已實作；實際能力、BDD 與限制分別在下列章節。L1 的目的不是只判斷新聞時間或真假，而是累積同股票內可引用、可修訂、帶適用條件與反證的通用觀點。L2 才依研究問題選擇角度、整合跨觀點催化與風險；查核、更正與噪聲是其中一類資訊，不應取代全部觀點。

| 已確認方向 | 取代／禁止誤解 | 驗證入口 |
| --- | --- | --- |
| 共用 L1 的 opinion／claim／evidence 身分，逐版累積 | 切 root／詞彙／時間／融合分組不建立互不相容資料，也不全量重抽歷史 | 本文分組／並行 BDD；WIKI_RUNTIME |
| Classifier exact revision 多標籤供選單、群、顏色、圖表及 L2 檢索共用 | 舊直接／間接財務影響不是另一套分類；未分類不等於噪聲或假消息 | 本文分類／共用工作區；TESTING 分類一致性 |
| 一個研究問題入口與共用 L1／L2／兩層圖、來源鏈、Chat 情境 | 不另開孤立 L2 畫布，不要求一般使用者撰寫 taxonomy 定義或技術 include/exclude 欄位 | `tests/browser_research.py`；本文操作習慣 BDD |
| 閱讀、導航與會花模型成本的動作分開 | L1 忙碌只守門新 L2／更新，已有 L2 可讀；不把整個入口永久鎖死 | 本文忙碌守門；TESTING 正式互動紀錄 |
| 顯示範圍、完整圖、工作範圍與保存結果分開 | 800／2400 是 GPU 預算，不是 L1 全局資料上限；開頁、篩選不得暗中重啟模型 | [計算契約](CALCULATION_METHODS.md)；[快取與來源](SOURCES_AND_CACHE.md) |
| 自然語言保留明確硬條件，缺證據就顯示缺口 | 簡化 UI 不等於放寬條件；分類／檢索分數不等於事實可信度或上漲機率 | 本文篩選／無行情／引用 BDD |

完整目標還包括原子 claims、不可變 revision、來源／事實／推論區分、歷史可見性、live/pinned、水位與未成熟 Outcome 隔離；以 `L2_Archirecture/` 為需求來源，對照本文「已知限制」逐項落地。不能把欄位存在或 fixture 通過當作市場判斷品質已驗證。增量更新先重檢索，包括之前未引用的新觀點，再依有效輸入是否變更決定推論；使用者不接受每次介面小改就消耗 token 重做。

延續此方向時，先讀 [目前交接](CURRENT_STATE.md) 與 [協作偏好](ai-dev-experience-preferences.md)，核對現有實作再改。新的觀點設計修正更新本節及相關 BDD，舊決策註明被何項要求取代，不堆成互相矛盾的待辦。

## README 三層視覺模型（2026-11-07 使用者確認）

使用者確認白底、柔和配色、圓角框、AI 插畫、節點簇與清晰箭頭的構圖符合產品概念。三層金字塔是 **News／Evidence → 共享通用 L1 → 客製 L2**；不改程式的兩個觀點層命名，Classifier／Taxonomy 仍是支援元件。圖上 Root Trees 是新聞分組示意，不能把 News 規則邊當成已驗證的支持／因果關係。

[README](../README.md) 提供 [中文圖](../docs/media/stocknexus-architecture-zh-TW.png)／[英文圖](../docs/media/stocknexus-architecture-en.png)。技術文件保留第一版限制（介紹圖不放限制旁註）：確定性 Lens、分類＋文字檢索、候選詞受控審核、價格／敘事基線缺口；持續累積不等於保證正確。維護回路是新增證據、檢查反證、修訂受影響觀點與刷新研究，不許把 L2 推論當 L1 外部證據。這次只更新介紹與圖，不宣稱新增 runtime 能力。

## 現況與整合

- 新聞：`news_atlas/storage.py`、`graph_storage.py`，provider/id 去重、每股票 SQLite；上游新聞覆寫需由 Wiki capture 保留不可變內容版本。
- L1：`news_atlas/wiki/store.py` 的 articles/nodes/edges/versions/extractions 是權威；Markdown、圖是投影。Claim/Event/Thesis 可相容包裝；UPDATES 連結保持 logical opinion 身分。
- 工作：`compiler.py` 與 `chat/wiki.mjs` 已有單槽、模型目錄、取消、引用驗證。研究工作沿用同槽，不另外並行付費。
- 新增：`research.py` 的 taxonomy、assignment、Lens、QueryRun、snapshot、L2。分類是索引，並非第三觀點層。L2 不進 articles/nodes/extractions。
- UI：既有 `dist/wiki-view.js` 保留 L1；研究入口與結果在相同 Wiki 中，來源逐步展開。
- 未確認：外部全文、歷史合格行情 revision、向量索引；不假裝具備。第一版價格 unavailable，分類＋全文檢索。

## 行為驗收（Given / When / Then）

| 邊界 | Given / When | Then |
|---|---|---|
| 匯入 | 舊版本或新電腦匯入，同一包重試 | 真正開啟 DB、Graph、來源引用可讀；重複匯入不重複觀點，未知新 schema 拒絕且不部分污染 |
| 歷史 | 今天匯入或補抓舊新聞 | 首次可見是今天；過去 snapshot 不出現它 |
| 分組 | root/詞彙/時間/融合切換 | 同一 SQLite、相同 opinion 身分、已完成 evidence 不重抽 |
| 分類 | 同一 claim 包含 topic 與 driver，未知詞 | 多標籤 exact revision；未知保留文字召回，不創 canonical ID |
| 篩選 | include/exclude AND/OR 與零結果 | 單一 Boolean AST，所有檢索路徑同條件；不放寬 |
| 時間 | future cutoff、未知日期、窗邊界、回填 | as-known 可見性與半開窗口；未知明列；不能倒填可知時間 |
| 無行情 | 查「動能」 | 敘事/價格分欄，價格 unavailable 無數字；無基線不說轉強 |
| 引用 | 假 ID/錯 revision/未支持數值/注入文字 | 拒絕提交，保留上次完整結果；來源僅作資料 |
| 更新 | 新增未曾引用的觀點、alias、反證 | live stale，重檢索完整候選；有效輸入未變不再呼叫模型 |
| 並行 | 查詢中 L1 改變或兩個更新同 Lens | 快照不混版、CAS 防遺失；舊 snapshot 不標 fresh |
| 隔離 | owner/股票相同文字 | 服務端固定 local owner（單人部署），拒絕客戶 owner 欄位；結果不跨 scope |
| 循環 | L2 保存/刷新 | 不增加 L1 evidence/extractions；未成熟 outcome 不進 prompt |
| 失敗 | 模型、分類或投影失敗 | 最後完整結果可讀；明示 failed/partial，無自動付費重試迴圈 |
| 時窗 | 沒新新聞但日期移動 | live 重解析 cutoff；pinned 原 snapshot 不變 |
| 水位 | 新來源未編譯或更正 | 不標 fresh，已知更正提示待重評；不以 max 完成 job 跳過缺口 |
| 操作習慣 | 已選股票、Enter 提問、切換頁籤 | 沿用 root 與模型，單一研究動作；無二次確認，切換不觸發模型 |
| 操作邊界 | 空問題/雙擊/切股票時回應到達/刷新失敗 | 防重工作、錯誤可恢復、舊回應不污染新選擇、保留成功內容 |

完整產品目標與來源圖見 `L2_Archirecture/`。歷史無可證明的 metadata 標 legacy，不補造。遷移採新增表，可用 NEWS_ATLAS_RESEARCH=0 停用研究 API 與背景工作（UI 入口仍顯示停用錯誤），保留原 L1。任何回退不刪資料。

## 第一版實際範圍與 API

SQLite 新增 `research_objects`（不可變 taxonomy/classification/source_status/snapshot/run/lens_revision/candidate_term）、`research_lenses`（CAS current pointer）、`research_jobs`。不刪既有表與 ID。分類和新資料已在同股票 DB 累積，分組只影響 L1 evidence batching。開啟 DB 拒絕未知較新 user_version，不能偷偷降級。

`/api/wiki/research/` GET：`taxonomy`、`lenses`、`job?id=`、`run?id=`。POST：`query`（query/instrument/model/reasoning_effort/lookback_days/filter_ast/as_of）、`save`（run_id/mode）、`refresh`（lens_id/expected_revision）、`taxonomy`（expected_revision/terms）、`candidate`（text/facet）、`source-status`（revision_id/status/reason）。所有讀寫必須是允許的本機來源；server 固定 local owner，拒絕客戶 owner 欄位。這不是多租戶登入系統。

Live 保存代表後續增量維護：工作槽輪到該股票時檢查 candidates/taxonomy/source status/UTC 日期變動；重檢索後有效輸入相同不呼叫模型。第一次模型失敗／重啟中斷便停止自動付費重試，保留上一份 run，等使用者按更新。未完成 L1 水位會讓 live 保持 stale。Pinned 保留完整 snapshot，讀取另外附 current_epochs，內容不回寫。一次工作 snapshot 所有表讀取使用同一 SQLite transaction。沒有外部索引發布，因此無 DB/索引雙寫混版。

UI：Wiki 右上「研究問題 · L2」，沿用股票與模型。Enter 建立研究；來源可展開，研究圖以 DERIVED_FROM/SUPPORTED_BY 呈現。保存 live／pinned、刷新、歷史版本與前版 claim 差異；分類清單唯讀，可定位到共用圖的 L1 群；不要求使用者編寫分類定義。所有來源 tooltip 先轉義。

## 遷移、合併與回退

新增表透過 WikiStore 初始化。保留 legacy L1，不全量重寫；模型分類按 exact opinion/taxonomy revision 增量建立，歷史 cutoff 不能使用今天才分類的 assignment。新模型提案另存 claim_type/conditions/horizon/change_reason；UPDATES 沿用 logical lineage，已被修訂的 base 拒絕並行覆寫。

merge_data.sh 同時檢查 L1/research 活動工作，驗證版本外鍵、引用 field/start/end/quote/content_hash、node ID，所有 DB 預檢後才提交。新匯入來源 captured_at 與撤回 known_at 以本機匯入時間記錄；原 source snapshot 備份保存。目標 taxonomy 不覆蓋；完整定義與別名相同時，匯入模型分類以可追溯映射重用，available_at 為本機匯入時間；不相容定義的原分類封存，等明確補足。私人研究成果保存為 imported owner 封存，不自動冒充本機 local owner 或啟動背景模型；目前需重新建立本機 Lens。這是明確的跨 owner 邊界，不是匯入資料丟失。

關閉新功能：`NEWS_ATLAS_RESEARCH=0`（Compose 環境轉交）後重啟；L1 保持可用。資料回退使用 merge report 中 before 備份，停服務後 SQLite backup 還原，不能只覆蓋有 WAL 的主檔。原 Wiki 未刪除。

## 已知限制（不可當成完整長期架構驗收）

- Lens 是確定性解析＋顯式 Boolean AST；未知的自然語言硬條件拒絕並提示。尚未接 LLM 複雜查詢解析、跨語種語意檢索、任意自然語言時間政策。
- Classifier 已接 L1 模型輸出與舊群分類工作；schema／版本／術語白名單由程式驗證，語意仍需抽查。candidate 不自動升級。無模型分類的舊節點標 pending，仍有文字與 alias 檢索降級；不能把文字命中當作模型分類。
- 價格動能與敘事量化基線不可用；不計算假數字。現有事後行情檢視保留，尚無新的 MarketFeature／Outcome 版本儲存與成熟排程。
- 模型敘事 inference 有引用白名單、數值、條件、反證與基線規則，新 inference 額外做一次有界語意支持檢查，失敗不自動重試；原文 excerpt 不加付費審核。模型通過仍不是證明。`semantic_validation` 明示是否 model_checked_not_proven；引用存在不代表支持關係為真。真實模型輸出品質尚未在此輪付費驗收。
- 自動更新時窗粒度為 UTC 日；尚無完整市場交易日曆／盤中滾動排程。Saved Lens 修改規則目前以建立新研究保存，歷史不覆寫。
- SourceStatusEvent 支援本機受控 API；供應商自動撤回 feed 尚未接入。新聞目前是 title/summary，來源歷史取得缺口不等於 Wiki 編譯缺口。
- L2 Graph 第一版為結論→L1→原文來源；沒有新增獨立 Evidence DB，引用 span 是 evidence identity。

這些缺口是後續驗收項，不以 mock 或 schema 通過宣稱全部 A01–A24 已滿足。

## 2026-11-07 共用觀點工作區

使用者回饋取代獨立 L2 3D 畫布與手填 taxonomy 編輯器：一個 `wikiCanvas`、相同攝影機／選取／側欄 Chat，提供 L1／L2／L1+L2。研究輸入位於左欄，已驗證的完整結果提交後逐點顯示 L2；推論中只有真實 queued/running 狀態，不預先顯示未驗證結論。L2 IDs 由 run+claim 組成，DERIVED_FROM 連到精確 L1，來源及時間仍屬固定 snapshot。

原「直接／間接／低關聯／不足」是財務影響與證據屬性，保留在詳情；頂部分類篩選、色彩圖例、L1 群與 L2 檢索都使用同一 taxonomy assignment。`classifier.py` 沿 DEPENDS_ON 與反向 SUPPORTS/CONTRADICTS 取有界依賴群，不沿 RELATED_TO 把共享新聞擴成無限群。分類有多標籤；主色按穩定 term ID，hover 顯示所有分類。信心不是市場機率。

新 L1 同次模型呼叫回傳分類，與觀點一併驗證／原子提交。按「補足到今天」另外為尚無當前 taxonomy 模型分類的獨立群排程，最多每批 12 群／65000 字元上下文，不重抽既有新聞。過時修訂跳過，失敗保留成果，需明確重試。方法切換不刪分類。已有 L1 分組工作不會因單純部署自動新增分類補足工作。

L1 與分類工作共用模型槽；全局仍有 queued/running 時，研究頁可讀，但新 L2／更新 API 與按鈕拒絕，停留 550ms 顯示原因。停止 L1 不刪已完成資料。持續追蹤研究在 L1 空閒後才檢查更新。進度區新增可拖拉／鍵盤調整邊界，尺寸與既有工作區一起保存；不修改圖資料、鏡頭或模型設定。

BDD 增補：分類補足重入不重複付費；未知 term 不部分發布；同定義資料合併不丟模型分類；分類不跨 RELATED_TO 擴散；忙碌拒絕新 L2 但舊圖可讀；真實指標拖拉不重建圖；停留提示時限；L1/L2 切換共用相同 3D 實例；Chat 工具依選取回傳 L2、L1 與精確來源。GET research 新增 `availability`、`runs`，仍遵守原本機來源／owner 邊界。

交叉審查補充邊界：純 L1 只讀目前所選 L1 版本，切換歷史版本會退出研究疊圖；L2 引用背景明示固定研究快照，bundle 保留原節點 kind。隱藏的選取會同步從 Chat 清除，無選取時只以畫面可見節點為預設範圍。返回設定／切換股票再回來會接續原研究 job，availability 可找回該股票活動工作；不因重新開頁重送模型。分類工作可用同一停止按鈕取消，取消後的模型例外不能把 cancelled 改成 failed，已提交標籤保留。


## 2026-11-07：分類圖表與漸進詞彙升級

Wiki 選單、日期柱狀圖與群列表共用 `classifier.enrich()` 的 `opinion_index`，每個 L1 群以根觀點計一次，引用多日取所選區間內最新日期；多標籤各計一次，所以分類合計可超過獨立群數。顏色與分類 ID 同 taxonomy；原 assessment 財務影響保留於詳細屬性，不再作另一套圖表分類。`__pending`／`__unclassified` 只是 UI 缺資料狀態，不是模型分類。選單採原生 select，不再在 focus 時疊加第二個分類清單，輪詢亦不替換正在操作的選項。

新增 `analysis.noise`（低相關／噪聲）與 `analysis.fact_check`（查核／更正）。後者包含反覆驗證、澄清及更正，不代表新聞已證實錯誤；不得從舊 assessment 或關鍵字猜貼標。無相應 assignment 時數量為零。

詞彙純新增時，僅在舊 vocabulary 全部定義／別名／狀態等欄位完整保持不變的條件下重用原 assignment；保留確切舊 taxonomy revision，以 `unassessed_term_ids` 記錄未評估新詞。新 revision 的 assignment 優先於較晚到達的相容舊工作。定義修改失效、歷史 cutoff 不借用未來 taxonomy／assignment。L2 bundle 使用相同 lookup，保留原引用版本與缺口。讀取／升級不啟動模型；既有凍結工作不換詞彙，下次新 L1 呼叫使用新定義。

無 SQLite schema migration、無刪除資料。部署新版後可先預覽，再顯式執行：

```bash
python3 scripts/wiki_taxonomy_upgrade.py --instrument NASDAQ:GOOGL
python3 scripts/wiki_taxonomy_upgrade.py --instrument NASDAQ:GOOGL --apply
```

腳本經公開 taxonomy API 以 expected_revision CAS 附加缺少的兩個詞；可多次傳 `--instrument`，重跑為 unchanged，不覆蓋同 ID 自訂詞彙。舊庫須執行此步，新庫 seed 已包含。回退程式優先保留現有 DB；新增 taxonomy revision 不刪舊版，但回退到只接受完全相同 taxonomy revision 的程式會將舊分類視為待補，應保留此相容 lookup 或暫停補分類，避免重算。

## 2026-11-07：研究層的等待與切換

由工具列切 L2 時，讀取／空結果／錯誤重試必須在主畫面可見，不依賴研究側欄是否開啟。無 L2 引導到「研究問題 · L2」，不要求重新整理 L1。讀取回覆同時核對股票、頁面 generation、層選擇與 run 請求序號；切回 L1／切歷史／換股票後的舊回應不能搶回畫面；開啟研究表單時清除已被新導覽取代的圖層 loading。來源和模型資料不因 UI 狀態改寫。實際操作與回歸見 TESTING。

## 2026-11-07：跨股票模型槽的可見性

研究可用性使用全局 L1／分類工作狀態；主畫面進度僅屬目前股票，不能推斷其他股票也閒置。當 TSM 閒置但 GOOGL 整理中，建立研究旁直接顯示 GOOGL 與共用模型忙碌原因，並可前往該股票；不靠停留 tooltip 才發現。前往後不自動停止工作，返回原股票保留研究草稿與觀察期間。忙碌解除由輪詢恢復按鈕，不建立額外模型工作。

BDD：本股閒置／別股 busy → 顯示 ticker 與可操作導覽；別股 completed → 不重新開頁即解除；availability 503 → 明示無法確認及重試，不假稱 L1 忙碌；恢復 200 → 清除錯誤；晚回覆不覆蓋新股票／較新檢查。正式狀態查詢與隔離瀏覽器驗證分開記於 TESTING。


## 2026-11-08 L2 執行與結果交接

- 排隊、分析、結果載入在側欄與中央圖譜同步呈現；中央使用 L2 標示及實際工作建立時間計算的等待秒數，不能沿用「尚未建立」空狀態。L1 覆蓋進度仍獨立保存。
- 結果必須通過既有提交驗證才加入圖；等待期間不生成假節點、不以時間猜完成百分比。
- 讀取失敗保留 job ID，45 秒讀取逾時後可恢復，持續輪詢既有 job/run；結果成功掛載才清除 pending。離開研究側欄仍追蹤；切股票使舊回應失效。
- 後端完成而前端結果未載入是不同狀態；不得藉新建模型工作修復 GET 失敗。

BDD 邊界（`tests/browser_research.py`）：

1. Given 已提交研究且尚在佇列，When 側欄開啟或關閉，Then 中央顯示 L2 工作進度，不能邀請重複建立研究。
2. Given 後端已完成但結果 GET 回 503，When 使用者已返回 L1 設定，Then 中央顯示重新連線；恢復後載入既有 L2，研究 job 數不變。
3. Given 切股票或切回 L1，When 舊讀取晚到，Then 不覆蓋新選取；同股票原工作可接續讀取。
4. Given 已完成正式研究，When 用原生下拉選股票並切 L2，Then 圖中 L2 節點數等於該 run claims 數；唯讀驗收禁止建立模型工作。


讀取成本邊界：job、runs、taxonomy GET 只讀已提交 Wiki，不再 observe／ingest 整份新聞；run 與 lenses 仍檢查來源以計算新鮮度，query／refresh 的來源觀察與背景增量維護保持。`test_polling_and_catalog_reads_do_not_reingest_news` 以來源掃描會失敗的情境驗證輕量讀取，並確認 run 仍執行觀察。
