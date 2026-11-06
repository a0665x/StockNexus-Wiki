# Temporal Wiki v0.1 資料與研究契約（待實作）

入口：[設計](../../TEMPORAL_WIKI.md)。這份契約及 JSON schema 是第一階段交付，不代表資料表、compiler 或研究引擎已存在。

## 1. 儲存與不可變版本

`<data>/research/<instrument_key>/` 下分開保存 `wiki.sqlite3`、`blobs/sha256/`、`index/`、`cache/`、`renders/<graph_version>/`、`exports/`。instrument_key 來自經驗證的交易所＋代碼＋證券種類，不直接把輸入拼成路徑。ticker 更名用有生效期間的 alias，不更換穩定 instrument_id。不同股票禁止共用索引、抽取快取、模型統計或工作 checkpoint；同一文章提及多股時，各股自行記錄引用與解讀。

SQLite 是結構化事實來源，Markdown 與 Graph JSON 是同版本投影。所有 domain rows 有 instrument_id、ticker、stable_id、revision_id、schema_version、run_id、mode、produced_at、provenance。表的複合外鍵包含 instrument_id，開啟 foreign_keys；每次檔案／DB／索引操作亦核對所屬 instrument manifest，防止路徑混用。

| 紀錄／擬議表 | 必要資料與不可變規則 |
| --- | --- |
| `instruments`, `runs`, `schema_migrations` | 交易所、時區、幣別、識別；模式、模型完整名稱／版本、prompt/schema/config hash、知識截止限制、資料 cut、migration checksum |
| `article_revisions`, `source_observations` | 原 `(provider, article_id)`／URL 對照、publisher、精確保存的 title/summary/body、content_hash、原始 payload hash、完整度 `title_only/summary/full_text`、每次觀測；舊 payload 不改寫 |
| `claims`, `claim_versions`, `evidence_spans` | 原子命題、subject/predicate/object、說話者、assertion_kind（reported_statement/verified_fact/hypothesis）、scope/period/units、unknown；逐項指向原文版本與片段，不因新聞刊登就視為已證實 |
| `events`, `event_versions`, `event_aliases` | 系統指派穩定 ID；事件類型、主體、發生時間／區間、階段與關聯 Claims。名稱或 root 改變不換 ID；合併／拆分留 alias 與歷史決議，不刪舊版本 |
| `theses`, `thesis_versions` | 可檢驗命題、支持／反證、適用時間／條件、失效條件、狀態 supported/weakened/unresolved/invalidated；不能靠股票漲跌證明真假 |
| `relation_versions` | 下節 strict schema；同一 logical relation 穩定 ID，每版保存精確 endpoint revision；反向依賴索引供 dirty propagation |
| `patches`, `jobs`, `change_log`, `checkpoints` | patch 前後版本/hash、操作、模型 provenance、token／費用、驗證／審閱狀態；durable cursor、idempotency key、重試／DLQ、lease／owner |
| `graph_versions`, `render_manifests` | DB commit 版本、受影響 node IDs、Markdown／JSON hash、渲染狀態；只發佈整份完整 manifest |
| `scenario_snapshots`, `snapshot_members` | 決策時點、精確 node/edge revisions、feature vector＋missing mask、feature schema/hash、episode membership 版本、資料／索引 cut；封存後不可重寫 |
| `price_observations`, `calendar_versions`, `corporate_actions` | provider、session、OHLCV、幣別、adjustment policy、抓取／可用時間、修訂；現有 daily_prices 與 sidecar 匯入時保留來源及缺口，不相互無聲覆蓋 |
| `outcomes`, `forecasts`, `analog_sets`, `research_runs`, `positions` | 標籤定義與價格版本、成熟時間；預測輸入 hash／所選樣本／統計版本；成本、試驗登記、成交／持倉流水。更正 Outcome 新增 revision；Forecast 永不以結果覆寫 |

完整原文不一定可得：不自動繞過付費牆或把摘要補寫為全文。引用索引採所保存 UTF-8 解碼文字的 **Unicode code-point offset** `[start,end)`；跨 Python／JS 使用相同定義，驗證 substring 等於 quote。原始 bytes、decode policy、正規化版本各留 hash。重複文章群是有時間版本的來源相依紀錄，不能把今天的分群結果套回昨天。

## 2. 結構化 Edge

正式範本：[schema](../../../schema/temporal-wiki.relation.schema.json)、[synthetic example](../../../schema/examples/temporal-wiki.relation.synthetic.json)。這是 wire contract；JSON Schema 只能檢查結構，以下語意與時間限制必須由程式查 DB 驗證。

| relation_type | 方向／適用對象 | 語意限制 |
| --- | --- | --- |
| SUPPORTS | ArticleRevision/Claim/Event → Claim/Event/Thesis | 同命題範圍的支持，不能推出預測勝率 |
| CONTRADICTS | Claim/Event → Claim/Event/Thesis | 指定衝突的 scope／period／units；不同期間不自動矛盾 |
| UPDATES | 新 Claim/Event/Thesis → 舊版／既有 Claim/Event/Thesis | 補充或改變，不自動作廢原說法 |
| SUPERSEDES | 新 revision → 同類舊 revision | 明示替代、記錄原因；不刪除歷史，不允許替代環 |
| DEPENDS_ON | Thesis → Claim/Event/Thesis | **依賴者指向被依賴者**；更新沿反向索引傳播 |
| TEMPORALLY_PRECEDES | Event → Event | 只聲稱順序，時間不明／區間重疊不能標 verified |
| RELATED_TO | Claim/Event/Thesis → Claim/Event/Thesis | 關係描述；機制推測標 hypothesis，不由共同 ticker 推導真因果 |
| HAS_OBSERVED_OUTCOME | Snapshot/Forecast → Outcome | 成熟且已 available 的結果，由 deterministic labeler 產生，不允許 LLM 寫數字 |

共同欄位：ID／revision／時間、endpoint types/versions、scope、relation_type、status、rationale、evidence_refs、provenance；`semantic_similarity`、`evidence_quality`、`predictive_association` 各自物件與 method/version，缺少可驗證結果填 null，沒有總合 confidence。

`evidence_quality.score` 是經規則／評估定義的來源品質描述，非客觀真實機率；`semantic_similarity` 只是檢索分數；`predictive_association` 必須指向獨立 research_run、樣本量、horizon、effect 與 units，不給 LLM 任填權限。`status=verified` 表示此關係完成所定引用／語意查核，不能暗示新聞因果已成立。模型只能提 proposed/hypothesis；程式或人工決議才可提升狀態。

`CAUSES` 不在 enum。若未來加入因果研究，另設 `causal_assessments` 記錄 estimand、識別假設、對照、混雜、placebo、敏感度與審閱狀態；不能把 RELATED_TO 自動改為因果邊。

## 3. 時間不變量與 as_of

全部保存帶時區的 UTC timestamp；exchange timezone 只作交易時段換算。未知時間為 null 加 reason，不補午夜偽裝精確。

- `event_time`：現實事件發生時間，可為區間／估計。
- `published_at`：來源宣稱的公開時間，可能更正；不是系統取得時間。
- `first_seen_at`：系統第一次實際看見該文章；`revision_first_seen_at` 是這個內容版本首次觀測。
- `ingested_at`：這個不可變版本提交進庫的真實時間。
- `available_at`：live 資料最早可供系統使用的時間，不早於版本觀測及提交；缺 publication 不可向前猜。
- `produced_at`：衍生物實際生成時間，永遠不改成回放日期。
- `decision_as_of`：資訊集截止；`decision_ready_at` 加上編譯／訊號運算時間；最早可進場時間嚴格晚於 ready＋execution_delay。
- `label_available_at`：最後必需的價格／公司行動資料已取得且 label 計算完成的時間，不是只填第 N 日收盤鐘點。

每筆版本兼有事件有效時間（valid time）與系統紀錄時間（recorded time）。查詢 `as_of(T,mode,run_id)` 先篩可見的來源／節點／邊，再做索引、摘要、分群及特徵計算；不是用 latest 摘要算完再加日期篩選。Forecast 保存的 snapshot hash 是最終權威，不能用最新圖重建取代。文字修辭變更與語意變更 hash 分開；不能由 LLM 任意決定兩命題等同。

**live_recorded**：只用實際 T 前已 available／produced 的資料。今天從 legacy DB bootstrap 的版本用今天作研究庫 ingested/available；原 fetched_at 另存為未經版本 ledger 證實的 observation，不倒填系統首次歷史可用時間。三個月前新聞今天補抓會進 latest，但不進三個月前 live 快照。

**historical_replay**：獨立 run、索引與輸出目錄；保存 actual produced_at 及 simulated_effective_at。明示假設 publication＋來源延遲可用、模擬 compiler 延遲及無法驗證的修訂史；過濾發生在任何模型上下文建立之前。禁止與 live 統計混合。模型預訓練可能知道未來，時間 prompt 不能消除，報告需保留污染限制。

日後補資料、事件合併、更正價格、模型升版不改舊 Forecast。可建立 correction/new_run，UI 並排原預測、原結果版本與更正版本。

## 4. 增量、交易與投影

先建立每股 ArticleRevision＋change_log 的 durable capture，再讓 legacy payload 被覆寫。若 legacy 取得與研究庫分屬兩個 SQLite，使用 legacy 同一 transaction 的 outbox（階段二獨立 migration），consumer 以 source change sequence 去重複製至授權股票庫；先 commit 證據＋jobs，再 ack outbox。外部程序繞過 outbox 的寫入只能定期 hash reconciliation 發現，無法找回期間被覆寫內容，標明觀測缺口。

Job key = instrument/run/task＋input revision IDs/hash＋model revision＋prompt/schema/config hashes。抽取快取按文章內容版本重用；事件候選檢索與 patch key 還包含 graph base version／候選版本，換 root 可重用抽取但不能略過新關係判斷。模型升版以顯式 reprocess run 執行，不無聲使全部快取失效。

每股單一寫入者 lease，SQLite `BEGIN IMMEDIATE`＋base_version CAS。LLM 在 transaction 外呼叫，提交時驗證 endpoints／引用／時間／權限與 CAS；失敗重新檢索或排隊，不能用過期 patch 覆蓋新版本。成功 transaction 同時寫 versions、edges、patch、dirty jobs、checkpoint；重跑依 idempotency 不重建資料。

初始建議限額：每批20文章、每篇有明示截斷及原位置映射、最多12候選頁、輸入上限16000 tokens、輸出4000、每次運行100000 total tokens。這是資源預設，不是模型能力或費用承諾；估價需實際模型計費設定。每日費用未設定時不啟用自動雲端排程。

暫時性錯誤最多3次帶 jitter/backoff；格式錯誤最多1次受限修復，無效引用不自動合理化；超限進 DLQ。排程有租約逾時及 checkpoint；取消不刪已提交版本。波及頁面僅由實質變更的反向 DEPENDS_ON 找到，每輪 visited(node,revision,input_hash)，深度上限3；循環不收斂或預算耗盡留 dirty/pending，**不能把半完成圖標為 consistent**。

DB commit 後 renderer 寫 `renders/<version>.tmp/`，驗證 links/hash 後 atomic rename，再更新 published manifest。Graph/Markdown API 只讀 manifest 指向同一版本；失敗沿用上一版並顯示落後狀態。原 Markdown/log 只增版本，人工筆記另存，不讓 renderer 覆蓋。

reconciliation 每次有來源／節點上限，檢查 orphan、壞引用、重複候選及 dirty，不做全庫 prompt。無內容變動且無重評工作時 LLM calls=0；價格成熟 worker 獨立運行。覆蓋率分 submitted/extracted/pending/failed/missing_text/pending_merge，重複群不算獨立來源數。

## 5. 行情與研究數學

預設待驗證配置：exchange `XNYS` 或 `XNAS` 由 instrument 指定、America/New_York、每交易日17:00 cutoff、horizons `[1,3,5,10,20]`。交易日由有版本的交易所 session calendar 決定，含假日／提早收市／DST；停牌另需狀態證據。calendar 來源與正式 runtime 相依在階段三鎖版本；現在未安裝不宣稱可用。

entry 是嚴格晚於所有輸入／編譯／訊號 ready＋delay 的下一個正常可交易開盤。開盤缺價／停牌時預設 `not_executable`，不隨意跳到後來有價的日期製造交易。entry session 算 k=1，exit 是第 N 個日曆交易 session 的收盤；缺資料為 missing，未到期為 pending，已知停牌不能假裝按官方無成交價成交。

- `terminal_return R_N = C_N / P_entry - 1`
- `mean_path_return A_N = (1/N) * sum(C_k / P_entry - 1)`，不是每日報酬平均或可實現持有收益。
- `analog_mean_terminal_return mu_hat_N = sum(w_i * R_i,N) / sum(w_i)`，不是觀測到的未來。

所有數字用 decimal return，0.05=5%。synthetic `entry=100, closes=[102,98,105]`：R1=A1=0.02，R3=0.05，A3=1/60。加權 R=[.05,-.01], w=[2,1] 時 mu=.03。

價格 baseline 選 split-adjusted price，cash dividends 獨立入持倉帳本，不與 total-return adjusted close 混用。保存價格與復權 factor vintage，後續拆股不得改當時的價格特徵。OHLCV、基準指數、公司行動缺任一所需欄位顯示不支持的研究輸出；成交量不從新聞推算。

Outcome 分 horizon、status、value|null、label_available_at、price_version_refs、calendar_version、label_definition_version；修正以新版本。maturity worker 只寫 Outcome，不能更新 Forecast 本文/hash。基準 excess return 是關聯控制，不是反事實因果量。MFE／MAE 的價格頻率、計算窗口與缺值同樣明示。

## 6. 類比、校準、策略與因果

樣本是單股每日決策快照；同日十篇新聞只形成一個決策。候選要求 snapshot<T，使用候選自己的歷史版本，該 horizon label_available_at<=T。先以 X 檢索並凍結 eligible sample IDs，才 join 已成熟 Y。X 不讀 forward returns、後來驗真假、後來 edges、全期間 P95 或正規化。missing mask 保留未知；訓練／檢索 normalization、權重、episode 分群只用 cutoff 前資料。

排除當前 episode，對重疊窗口限額；提供 raw sample_count、episode_count、weight n_eff=(sum w)^2/sum(w^2)，不能說 n_eff 就是獨立事件數。先以規則／FTS候選＋可解釋特徵距離，不要求向量庫。預設不足20個 episode 或 n_eff<10只顯示描述性資料、預測 null、INSUFFICIENT_EVIDENCE；這些是事先配置的最低門檻，不代表20樣本足以證明有效。報酬 quantile interval 與平均估計 confidence interval 分開；不確定性使用登記的時間block／episode bootstrap，無法合理估計時 null。

每個 N 事先固定正值 u_N/d_N；up為R>=u、down為R<=-d、neutral其餘。歷史比例欄名 empirical_frequency，LLM extraction confidence 與 calibrated_probability 各自獨立。校準器只用時間外 validation，缺類別、樣本、合適類比或漂移時 null；回報可靠度曲線、Brier/log-loss等，不能單憑一分數宣布校準成功。

Forecast 固定 contract：instrument/run/mode/snapshot/hash/decision_as_of/produced_at、horizon/label version、eligible analog IDs/versions、distribution/uncertainty/calibration、main_changes/support/counterevidence/limitations、signal.action、cost_config、invalidation_conditions。action限 LONG_CANDIDATE/SHORT_CANDIDATE/NO_TRADE/INSUFFICIENT_EVIDENCE；`execution_enabled=false`。synthetic 無樣本範本另附，不能匯入正式 DB。

研究以 chronological train/validation/test walk-forward；按實際 label intervals purge 跨邊界樣本，embargo 用 sessions／時間而非不規則新聞列數。最後測試段封存，所有 horizons、閾值、特徵、模型與試驗數留紀錄。相同 cutoff/交易成本/持倉約束比較 price-only、raw-news+price、Wiki+price，加 cash／buy-and-hold基準；分開預測品質及策略淨績效，long／short、實錄／回放亦分開。預訓練污染仍需揭露。

第一版帳本每股最多一個方向／部位、每日最多一個決策、不加碼疊加；持有N日預先設定，同日反向信號記錄但持有期內不反轉，結束後下個可執行日才考慮新訊號。N不是同時開五份持倉；不同N屬不同預登記 research run。每次下單名義曝險固定為可用資金配置上限，費用、spread、slippage從現金帳扣除。short另外借券費、股息負債、借券availability、recall與margin；缺資料標 hypothetical，不能只把long績效反號。不得直接把相關新聞的R_N全部相加當收益。

因果問題另設事件研究 protocol：明定 event-time uncertainty、估計窗口、benchmark、宏觀與財報同日混雜、預期差／提前反映、反向因果、placebo與前趨勢。單股日線與觀測新聞通常只能支持 association；没有可信對照／自然實驗的識別假設時，UI 保持 hypothesis。不把事後漲跌拿來判定文章品質，保留傳聞與不準確報導的當時狀態。

## 7. LLM 信任邊界與四組提示詞合約

共用 envelope：task/prompt_version/schema_version/instrument_id/run_id/mode/as_of/input_hash/base_graph_version，news/quotes/retrieved 是不可信 data；只允許送入當時可見文字及不可執行的 ID。模型不得 shell/network、讀憑證、改交易／工具權限、直接寫 DB。compiler SDK 與 UI chat 分離；工具 allowlist 為空或只提供有界 read_evidence，絕不繼承 UI act。prompt 不要求或保存內部推理，僅要可查核簡短理由。成本／token 未知保留 unknown。

| 模組（階段二建立獨立版本 prompt＋I/O schema） | 最小輸入 | 受限輸出與驗證 |
| --- | --- | --- |
| extract_claims | 精確ArticleRevision/時間/證券定義，無Y | atomic claims、assertion_kind、event_candidates、evidence spans、unknown；每項命題必有來源，無價格預測欄位 |
| propose_knowledge_patch | 新Claims＋最多12個同股可見候選版本＋base version | add/version/link/supersede/no_change、依賴dirty candidates；無任意SQL或刪歷史操作，合併僅提案；程式決定ID、時間與commit |
| reassess_thesis | 變更事實＋受影響thesis＋當時支持與反證 | maintain/strengthen/weaken/unresolved/invalidate、新命題／依賴／反證refs、簡短理由；不能查未提供歷史 |
| explain_forecast | frozen snapshot＋deterministic statistics＋engine action | 摘要、類比差異、風險與不交易理由；數值以輸入 JSON pointer 引用，渲染器代入，不准模型改數字／action |

Schema 過關只代表格式；還需引用、版本、ticker、方向、時間、revision existence、跨度、權限及金額由程式查核。另用人工標記評估集測事件合併/拆分、引用、矛盾、時間抽取，結果與結構測試分開報告。
