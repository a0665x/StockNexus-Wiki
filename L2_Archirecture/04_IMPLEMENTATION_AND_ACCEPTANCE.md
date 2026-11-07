# 04｜Agent 執行步驟、驗收與交付

## 1. 給 coding agent 的工作方式

你的任務是修改既有專案並交付一條完整可用流程，不是只提出建議或另建沒有接到現有資料的展示頁。

### Phase 0：先查核現況

閱讀 repository 的 AGENTS.md、README、依賴與啟動方式，定位 ingestion、stock root、news／event nodes、L1 Wiki 生成、DB／Graph、LLM adapter、UI、jobs 及 tests。

列出「已存在／可重用／需新增／無法確認」對照表，附真實檔案路徑及 schema；不要編造不存在的 API 或完成狀態。若沒有 repository 存取，清楚說明缺口並提供可執行的整合規格，不聲稱已修改程式。

確認哪個儲存表示是權威；若現有 Markdown 是權威，保留並增加 typed metadata／版本契約，不為了採用本規格就重建整個系統。

### Phase 1：建立最小契約

增加或映射 source／L1 revisions、taxonomy／assignments、Lens／QueryRun／L2、snapshot／manifest、job／change event。建立向後相容 migration、初始 taxonomy 與 feature flag；保留既有 ID 與 URL。

若舊 L1 只有長篇 Markdown，先以 section／claim locator 包裝成可引用單位；逐步補結構，不任意重寫所有歷史觀點。舊資料未知的時間、來源或 revision 標 unknown／legacy，不能捏造歷史可知性。

### Phase 2：做通一條垂直流程

使用 repo 已有的真實可用資料或明確標示的固定 fixtures，完成：

**一檔股票的 L1 → 分類 → 輸入「動能」→ Lens → 檢索支持與反證 → EvidenceBundle → L2 → Graph 來源追溯。**

沒有行情時走可驗收的敘事分支並標明價格缺口。禁止以假行情掩蓋整合未完成。

### Phase 3：完成保存與更新

讓使用者保存 live／pinned Lens；接通新增新聞／反證／更正、分類變更及時間窗更新。完成候選集合失效、CAS、冪等工作、重試、last successful result 與 freshness 顯示。

### Phase 4：接入現有 UI

在既有 Graph／Wiki 工作流程加入研究欄位與分析角度，顯示解析結果、套用的期間、L1 入選理由、L2 摘要、反證、缺口及可展開來源。保留現有 L1 瀏覽；可在 L1 與我的 Lens／L2 之間切換。

使用者不需看到 input hash、job id、embedding epoch 等內部細節才能完成研究；詳細資訊放進可展開面板。不能只新增設定頁卻沒有完整生成與更新流程。

### Phase 5：驗證與交付

採用現有測試工具。先做下表與這次改動有關、真正能阻止錯誤的測試，不為每個 getter／模板文字寫鏡像測試。確定 schema、時間、權限、更新鏈與典型 UI 端到端情境成立即停止無意義的擴測。

## 2. 驗收情境

| ID | Given／When | Then／可觀察結果 |
|---|---|---|
| A01 | 同一新聞重複取得；同 job 重試 | 不重複提交同效果；必要的獨立來源紀錄仍保留 |
| A02 | 同一事件由多個 RSS 轉載 | 不虛增獨立事件數或證據強度，能查看來源群組 |
| A03 | 一個 L1 同時涉及硬體、資料中心與 capex | 產生跨 facet 多標籤；可從不同研究角度召回 |
| A04 | 出現未知詞與 canonical term 的別名 | 已知 alias 正確映射；新詞可成 candidate／unclassified，不亂創正式 ID，也不失去文字召回 |
| A05 | 使用者明確排除某主題、指定股票／時間 | 所有檢索路徑及 Graph expansion 遵守硬條件；零結果時不暗中放寬 |
| A06 | 裸 query 為「動能」，沒有行情 | 解析顯示兩種動能；有據的敘事分析仍可用，價格為 unavailable，無虛構報酬 |
| A07 | 有合格 N+1 筆價格、交易日缺口或當日未收盤 | 程式按已宣告規則計算；缺資料／未完成 bar 不被當成完整指標；數字不由 LLM 計算 |
| A08 | 有相關支持與重要反對證據 | L2 能整合並呈現反證；不能只符合使用者偏多語氣；新推論有條件與引用 |
| A09 | 空候選／證據弱／沒有前版 | 分別標資料不足、覆蓋限制、baseline unavailable；不編造趨勢變強或結論 |
| A10 | LLM 引用不存在的 ID、錯 revision、未支持主張的文字 | schema／引用檢查拒絕非法提交；語意問題可定位並修訂；不以 ID 存在視為全數通過 |
| A11 | 已被引用的 L1 加入反證 | 新 L1 revision、相關 live L2 stale、重檢索後保留反證，pinned 不變 |
| A12 | 新增一個舊 L2 從未引用但符合 Lens 的觀點 | 候選集合變更使 live Lens 重檢索；新觀點可入選，不能只追既有 DERIVED_FROM |
| A13 | 今天補抓舊新聞，或今天取得舊文章的更正 | 現在時間線可補充；過去 as-known／pinned 不出現今天才知道的內容 |
| A14 | 來源撤回／更正削弱已引用論點 | 原版本保留；目前 L2 的依據更新或降級，引用不繼續假裝有效 |
| A15 | taxonomy 定義／membership／alias 修改 | assignment 與查詢版本一致；相關 Lens 重檢索；改名不產生孤兒連結 |
| A16 | 查詢中上游更新；兩個 job 並行改同一 L1 | 一次查詢的 manifest 一致；CAS 不遺失更新；較舊 snapshot 結果不能對 live 標 fresh |
| A17 | source 已入庫但 L1 尚未編譯，或 DB 提交後 Wiki／索引投影失敗 | ingest／consumed 水位揭露 pending／lag；不標 fresh；已知更正／撤回立即阻止當前有效引用；重試不重複提交 |
| A18 | 沒有新新聞，但最近 7 日視窗滑動或行情更新 | live 從時間規則重算 cutoff，不沿用首次查詢時間；cache 正確失效，pinned 保持原結果 |
| A19 | 兩位 owner 或兩檔股票使用相同 query | 檢索／cache／Graph／寫入皆不混用；後端驗證 owner scope，不只前端隱藏 |
| A20 | source 或 query 內要求忽略規則、讀別人的 Wiki | 只作資料；不擴權、不任意操作工具、不修改 L1 |
| A21 | L2 輸出被掃到，或多份 Wiki 重述同一論點 | 不當作新外部證據、不形成自我支持循環、不增加獨立來源數 |
| A22 | N 日 forward outcome 尚未成熟，之後才成熟 | 未成熟為 pending；成熟後寫獨立 evaluation，原始 L1／L2 紀錄不回寫、不洩漏未來 |
| A23 | sources outage 後大量補抓，新聞量暴增 | coverage 改變有揭露，不直接解讀為股票敘事動能暴增 |
| A24 | 分類、LLM 或檢索服務部分失敗 | 明確的 partial／stale／failed；有界重試；最後完整結果與截止時間可見 |

## 3. 少量但有效的測試層次

1. **Deterministic contract tests**：schema、scope、revision、cutoff、引用、價格計算、idempotency 與 CAS。
2. **Integration fixtures**：新觀點加入、反證、更正、taxonomy 變更、索引失敗與重新發布；驗證 DB／Wiki／Graph 指向同一 manifest。
3. **LLM quality fixtures**：少量代表性問題與允許證據，檢查漏反證、無依據推論、分類錯位及動能混淆。不要以每次字串完全相同當正確性標準。
4. **端到端 UI 情境**：一檔股票查動能、展開來源、保存 Lens、加入新相關觀點後看到 stale→刷新，以及無行情降級。

若需要建立 retrieval evaluation，使用人工標註的 query→相關／反相關觀點集合，報告 recall@k／nDCG 等；若缺少標註資料，先交付測量工具與 fixtures，不宣稱品質提高特定百分比。LLM judge 可輔助定位問題，不能單獨證明內容正確或無偏差。

## 4. 可觀測性與成本

記錄各步驟耗時、LLM 呼叫／token、cache hit、索引 lag、stale backlog、invalid citation、CAS conflict、partial response、候選／入選／截斷數、來源缺資料與有／無反證比例。

P95 latency、每次更新可接受成本等目標先量現況再制定；不得編造固定速度提升或準確率。避免全量十萬節點進 prompt；以 scope、snapshot、有限 Graph expansion、bundle budget 與變更 hash 控制成本。

## 5. Migration 與回退

- Feature flag 控制新 Layer 2 與 classifier rollout；保持原有 L1 入口可用。
- Schema migration 可回退或保留兼容讀取，不刪除原始新聞、舊 Wiki 與舊 ID。
- 初始回填以股票／批次進行並保留進度與 input hash，不因單筆失敗重跑全量。
- 舊資料無明確 source revision／available time 時標 legacy／unknown；歷史 as-known 查詢限制使用，不填猜測時間。
- 回退只切換功能與 active manifest；不逆向刪除可追溯歷史。

## 6. 最終 Definition of Done

使用者可在既有股票 Graph 上輸入「動能」，看到系統如何解讀、哪些 L1 觀點被選取、整合後的 L2 結論、重要反證、缺少的行情與可點擊證據鏈。保存為 live Lens 後，新增未曾引用的相關 L1 也會使它重新檢索並更新；固定歷史結果保持原樣。整條流程在重試、並行及部分失敗下不混版、不遺失資料、不把舊結果冒充最新。

coding agent 最終回報：

- 已修改的實際檔案、資料契約與 migration。
- 一條真實可運作的演示路徑與啟動／使用方式。
- 已執行的測試結果與尚未驗證的部分。
- 舊資料相容、回退方式、尚未接入的供應商／行情與其他限制。
- 如有外部權限、憑證或無法回退操作阻擋，只列具體阻擋與已完成部分，不把它當成停止所有其他可做工作的理由。

不能用只有介面 mockup、只有 taxonomy 字典、只有一般摘要或只有設計文件冒充已完成程式修改。
