# 01｜產品概念與邊界

版本：1.0 · 2026-11-07 · 對象：維護既有專案的 AI coding agent

本文是建議的新產品規格，不是對現有程式碼已具備功能的宣稱。現有資訊來自使用者描述與手繪圖；實作前必須查核 repository。範例名稱、門檻、API 形狀均須依既有技術棧映射。

## 1. 產品目標

在既有「單一股票 root → 新聞 Graph → LLM 維護的通用觀點 Wiki」之上，增加可程式化的分類與查詢機制，讓使用者輸入研究問題後，得到有依據、可追溯、可持續更新的第二層客製觀點 Wiki。

核心公式：

**Layer 2 觀點 = 使用者的研究角度 × 截止時間內可用的 Layer 1 觀點及原始證據 × 必要且可用的行情特徵。**

「×」代表選取、比較、整合與條件化推論，不是文字串接或固定數學運算。

## 2. 現況、假設與未確認項目

| 類別 | 內容 |
|---|---|
| 使用者已描述 | 已蒐集 Google／Yahoo Finance RSS 與 Massive API 新聞；已有 Graph 與 Layer 1 LLM Wiki |
| 既有設計脈絡 | 每檔股票一個 root，新聞之間有 node／edge；希望持續增量更新 |
| 本次新需求 | 分類與分類 Wiki、自然語言 query、Layer 2 fusion 與客製 Wiki |
| 本規格採用的假設 | 同一股票的 Layer 1 可在有權限的 workspace 內共用；Layer 2 依 owner／Lens 隔離 |
| 必須檢查 repo | DB／Graph schema、Wiki 目錄、LLM adapter、排程、行情資料、權限、測試、UI 與 API |
| 不得推定 | 已有價格／成交量、完整歷史新聞、資料供應商所有權限、已完成的回測績效 |

新聞覆蓋範圍只能宣稱為「目前已接入且成功取得的來源與時間範圍」，不能寫成已讀取市場所有新聞。

## 3. 概念與責任

| 元件 | 負責什麼 | 不能替代什麼 |
|---|---|---|
| Raw source／News revision | 保存來源、可取得的內容、時間、版本與來源定位 | 原始事實不因模型偏好而被改寫 |
| Event／Evidence／Claim | 把新聞中的事件與可引用主張整理成可追蹤單位 | 報導中的主張不自動等於已證實事實 |
| Layer 1 General Opinion | 對同一股票形成可重用、原子化、帶證據與反證的通用分析 | 不為某位使用者的偏好改寫共用結論 |
| Classifier | 對 L1 觀點做多軸、多標籤分類，記錄分類依據 | 不預測報酬、不把 relevance 當漲跌機率 |
| Taxonomy Wiki | 解釋每個分類的定義、別名、邊界、關聯及相關 L1 觀點 | 不形成第三層投資觀點；不只是一個自由散文目錄 |
| Query／Lens | 將問題轉為股票、範圍、時間、分析角度、偏好與約束 | 使用者輸入不是股票事實或證據 |
| Retrieval | 在授權範圍及同一 snapshot 內找相關觀點、反例及來源 | 不能只找支持使用者原有立場的內容 |
| Layer 2 Customer Opinion | 依 Lens 整合 L1，分析一致性、衝突、時間變化與缺口 | 不只重述某篇 L1、不反寫 L1、不自動下單 |
| Outcome evaluation | 觀察之後 N 個交易日的實際結果，供獨立評估 | 未來結果不得流入當時的 L1／L2 推論 |

General 指「不依客戶客製」，不是「跨所有股票混在一起」。股票範圍以穩定 instrument ID 與市場識別為準，ticker 只是顯示與查詢入口。

## 4. Layer 1 必須是觀點集合

保留原有總覽頁，但底層應能定位到個別觀點，而不是只存一篇無法切分的長篇總結。每個 L1 觀點至少有：

- 穩定 `opinion_id`、不可變的 `revision_id`、股票／workspace 範圍。
- 一個清楚的分析命題、時間範圍、適用條件與狀態。
- 支持證據、反對證據、未解問題；每一主張可連到來源位置。
- `facts`、`reported_claims`、`inferences` 的區分。
- 多標籤分類、來源覆蓋與資料缺口。
- 這次修訂改了什麼、為何修改、依賴哪些上游 revision。

同一事件可以有不同且並存的觀點，例如「需求支撐營收」與「投資支出壓縮短期現金流」。不能因兩者情緒不同就互相覆蓋。

## 5. Classifier：固定維度＋穩定 ID＋受控擴充

採多軸多標籤，而非互斥的單一分類。第一版建議三個核心 facet：

| Facet | 回答的問題 | 初始 term ID 範例 |
|---|---|---|
| `topic` 主題 | 在談哪個領域？ | `topic.data_center`、`topic.ai_hardware`、`topic.cloud`、`topic.energy` |
| `driver` 驅動因素 | 哪種變化可能影響股票？ | `driver.demand`、`driver.capex`、`driver.earnings`、`driver.supply`、`driver.regulation`、`driver.valuation` |
| `analysis_dimension` 分析角度 | 可以用什麼角度研究？ | `analysis.narrative_momentum`、`analysis.price_momentum`、`analysis.fundamentals`、`analysis.risk` |

`stance`、`time_horizon`、`evidence_quality`、`lifecycle_state` 是觀點的結構化屬性，不與主題混成一張扁平字典。`price_momentum` 被貼標只表示該觀點涉及價格動能，不代表已計算、確認或預測價格上漲。

同一觀點可以是：資料中心＋硬體＋資本支出＋敘事動能＋基本面。同一分類也可以對應多個 L1 觀點；兩邊均為多對多。

### 5.1 詞彙治理

- `term_id` 永久穩定；中英文 label 可以改，alias 可新增，但不得靠改 ID 破壞歷史連結。
- 每個 term 有 definition、include／exclude rules、正反例、父子／相關詞、版本與狀態。
- LLM 只能產生分類或詞彙修訂提案；程式驗證 term、facet、引用與 revision 後才提交。
- 新詞先進 `candidate_terms`。先檢查既有 term／alias／語意近似，再決定映射、維持候選或合併。
- 首版由維護者明確 promote 新 canonical term；未來可加入有版本的自動審核規則。日常新聞分類與更新不必等待人工逐筆確認。
- 候選詞不阻止 lexical／semantic retrieval，不必先成為正式分類才能被查到。
- 允許 `unclassified` 或空分類，不強迫低依據貼標。
- 分類信心僅表示模型對該分類的判斷，不是統計校準的機率；第一版可用 high／medium／low 加理由。

### 5.2 Taxonomy Wiki 的內容

每個分類頁包含定義、別名、適用／排除邊界、相關分類、代表性 L1 觀點及版本化變更摘要。反向 membership 清單由權威資料依 scope 與 snapshot 計算，不能由 LLM 自行隨手列一份而無法對帳。分類頁可以跨股票共用詞義；觀點清單則必須受股票及權限篩選。

## 6. Layer 2 的產品行為

輸入「股票動能」時，系統應顯示其解讀，預設涵蓋敘事動能，並在行情可用時附上價格動能；兩者分開呈現。若使用者明確只要其中一種，就遵守該範圍。只有未能確定股票等必要條件時才要求補充。

一份 L2 至少回答：

1. 這次研究的股票、截止時間、觀察範圍及問題是什麼？
2. 哪些 L1 觀點相關，為什麼相關？
3. 哪些驅動因素互相支持，哪些有衝突？
4. 與前一次可比 snapshot 相比，新增、轉強、轉弱或失效的是什麼？
5. 有哪些反例、資料缺口、假設及可使結論失效的條件？
6. 每個實質主張來自哪些 L1 revision、來源證據或行情 feature？

沒有足夠證據時，回答「資料不足」或「僅能回答部分問題」，不能把空結果寫成中立、看空或沒有風險。

### 6.1 一次性查詢與持續 Wiki

- `QueryRun`：一次查詢與其 snapshot、結果、檢索 manifest。可快取，但不自動變成永久追蹤任務。
- `SavedLens`：使用者儲存的研究角度，有 owner、scope、排程／更新策略。
- `CustomerWiki`：SavedLens 對應的一組版本化 L2 頁面、index 與變更 log。
- `live` Lens：隨新資料、時間窗與設定更新；每次結果仍為不可變版本。
- `pinned` Lens／結果：固定 snapshot，不因之後新聞自動改寫。若要以後見資料重新研究，另建明確標示的重建結果。

兩個不同使用者都查「股票動能」，可以共用授權範圍內的 L1，但不共用私人 Lens、持倉偏好、查詢紀錄或 L2 頁面。

## 7. 本次範圍與非目標

### 必須完成的第一版

- 原有 L1 的相容讀取、原子觀點／引用／revision 契約。
- 多標籤 classifier、初始 taxonomy、taxonomy Wiki 與索引。
- Query→Lens→受限檢索→EvidenceBundle→L2 fusion 的完整鏈路。
- 可追溯的 L2 頁面、一次性查詢與 SavedLens 的區別。
- 新聞／觀點／分類更新後的失效、重檢索、增量重建。
- UI 可看解讀、證據、反證、版本、新鮮度及資料不足原因。
- 關鍵 schema、引用、權限、時間與增量情境的驗證。

### 有資料才啟用

價格／成交量特徵、敘事計數時間序列、前一個可比 snapshot、事後 N 日結果。缺資料時降級並列出需求，不製造樣本或接入成本未授權的供應商。

### 本次不擴張

不重建整個爬蟲平台、不強制換 DB／Graph／LLM、不訓練分類模型、不建交易執行器、不保證報酬、不做跨股票投組最佳化。跨股票共用 taxonomy 可以保留，但一次 Lens 的股票範圍必須明確。不要為這一功能先引入微服務、訊息叢集或新的大型框架。

## 8. 技術與來源的界線

本設計借用 LLM Wiki 的持續編譯概念，再加上股票系統需要的分類、時間版本、證據與更新契約；不是 Karpathy 原文的逐字規格，也不要求採用特定 GraphRAG 套件。

- [Karpathy：LLM Wiki 原始概念](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)：來源、持續維護的 Wiki、schema，以及 ingest／query／lint。
- [Microsoft GraphRAG：Local Search](https://microsoft.github.io/graphrag/query/local_search/)：在查詢時結合 Graph 結構與原始文件內容。
- [Elastic：Reciprocal Rank Fusion](https://www.elastic.co/docs/reference/elasticsearch/rest-apis/reciprocal-rank-fusion)：合併不同檢索結果的名次；本規格僅借用演算法概念，不要求 Elasticsearch。

以上為概念依據；下列流程、資料模型、初始參數與驗收條件是本專案的設計建議。
