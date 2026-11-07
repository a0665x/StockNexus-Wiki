# 雙層研究 Wiki 契約與 BDD 邊界

狀態：第一版垂直流程已接入；驗證與限制見本文末段。

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
