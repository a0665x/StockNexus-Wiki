# L1／L2 Chat 證據整合與 BDD

2026-11-10：原始碼、隔離驗證與正式服務更新完成。部署前確認所有 L1／L2 模型槽閒置；保留 DB／設定，透過標準啟動器更新容器及 host Chat bridge。入口：[專案地圖](PROJECT_MAP.md)、[Chat](CHAT_AGENT.md)、[研究](RESEARCH_LAYERS.md)。

## 修正的邊界

- 一般 `read_wiki`／`read_edges` 仍讀取瀏覽器已載入資料，不代表全部 DB。新 `read_research` 經瀏覽器唯讀 action → `/api/wiki/research/run?id=…&instrument=…`，取得 DB 已保存的完整研究快照、L2 結果、精確 L1 premises、引用與 current epochs。GPU 節點預算、L2-only 不裁切此回應；研究本身的檢索上限仍以 manifest.truncated 明示。
- MCP 工具在 active Chat turn、獨立 tool token 下使用。只讀目前選取的 run／股票；讀取途中切股票／run，結果拒絕。沒有 L2 就明示沒有選取，不暗中建立或更新研究。所有資料保持 untrusted evidence。
- 支持／反對是研究問題下的模型論證分組。引用、分類與線索數不能當作機率、因果或證明。共用新聞 revision 去重，不把 L1＋L2 重複引用算成兩筆獨立消息。

## 日期與預測契約

`read_research({lookback_days:7})` 的近期範圍以 bridge UTC 現在回推，1–3660 日，預設七日。傳回 `temporal.start/end`、`snapshot_window`、`view_date_range`，三者不混用。每則引用保留 published_at／available_at／URL／claim_ids，標記 recent、older_context、future_or_not_yet_known 或 unknown_time。時間未知或未到可知時間不能列作近期證據。

`current_epochs` 與快照 epochs 不同時 `snapshot_stale=true`；`pending_l1`、candidate/selected count、truncated 一併提供。這不表示工具已把新的 L1 自動融合進舊 L2。缺資料／舊快照必須揭露，使用者未要求時不發付費更新。

三個**未來交易日**的目標不同於歷史新聞後三日平均報酬，也不等於三個日曆日。此研究 snapshot 沒有經驗證的現價 revision、交易日曆與預測模型，`forecast.status=unavailable`。Chat 可依可追溯證據描述條件式多空情境與失效條件，不提供杜撰目標價／機率。

## Given / When / Then

| Given | When | Then／證據 |
|---|---|---|
| SQLite 有昨日需求、前日成本、90 日前背景、明日新聞 | 建立 120 日研究 fixture | DB 快照含三筆 L1，未來發布項目排除 |
| L2 畫面不渲染 L1 | Chat 透過真實 MCP stdio 呼叫 read_research | HTTP 讀回全部快照 L1、L2 正反分組、精確引用；不依 GPU 切片 |
| 快照保存後又新增未整理新聞 | 讀取原 run | snapshot_stale=true、pending_l1=1；原結果保留，編譯呼叫數不增加 |
| 新舊／未知／未來可知時間及共享來源 | 七日 evidence metadata | 近期去重、舊聞標背景、未知／未來不冒充近期；無近期時 recent_count=0 |
| 工具讀取尚未回來 | 切另一股票／run | 409 拒絕晚回應，不混資料；瀏覽器 token 不能直接呼叫 tool route |
| 模型回答 Markdown 表格與惡意 HTML／程式碼 | Chat 收到 message | 語意 table/th/td、可點來源、欄內捲動；HTML 不執行，fence 保持 code |
| 英文偏好＋新 URL 視窗 | 初始化／另一視窗切語言 | 研究入口與分類一致；原始新聞與引述保留原文 |
| 目前可見節點集合改變 | 分層／篩選更新 | 圖例由可見實體 mesh 產生 WebGL PNG 縮圖，只顯示當前綁定，不顯示固定色彩操作長句 |

## 可重跑的驗證

- `python tests/browser_research_chat_bdd.py`：臨時 SQLite＋真實 HTTP＋瀏覽器同步／ack＋MCP SDK stdio＋Chat DOM。預設 deterministic agent，只驗證資料及互動契約，**不**宣稱驗證模型理解。
- `node --test tests/chat-research.test.mjs tests/chat-service.test.mjs`：時間、去重、缺口、隔離、晚回應；含既有工作階段行為。
- `python tests/browser_wiki_reading.py`：英文分類與 L2 入口重現（修正前 FAIL）、新 URL／跨視窗語言切換。
- `python tests/browser_wiki_arguments.py`：既有論證分支＋真實 mesh 縮圖與可見範圍綁定。
- `python tests/browser_chat_language.py`、`python tests/browser_research.py`：重連、串流、切股票、兩視窗、研究讀取與保存回歸。

只有明確要花用量驗證時才設 `ATLAS_BDD_LIVE=1`：同一隔離案例呼叫一次 gpt-6.1-sol low，上限 150 秒，唯讀 MCP、無 shell/web。不應列入預設 CI 或失敗自動重跑。

本輪真實回答已人工核對：工具 trace 包含 get_state/read_research/read_wiki/read_edges；回答引用 11/09 與 11/08 兩則近期消息，8/12 僅作背景，11/11 未來消息明示排除，辨認為測試資料，不杜撰目標價。測試初版誤取第一則進度文字；修正為最後一則 assistant message，以 `ATLAS_BDD_REPLAY=/tmp/research-chat-live-audit.jsonl` 重播原回答，表格及來源日期驗證通過，沒有第二次付費推論。這是一次 fixture 語意抽查，不能保證所有問題、真實行情或預測正確性。原始輸出留在 `/tmp/research-chat-live-answer.md`，不是正式資料。

## 正式服務核對

8765 健康、Chat ready/wiki_ready，wiki-view/research-view/chat-panel/i18n 四個實際 HTTP 資產 SHA-256 與原始碼一致。隔離 Chrome 阻擋 workspace／Wiki 寫入後檢查正式 UI，英文分類／L2 入口與可見 L1 立體圖例 PASS、無 runtime errors。使用者保存的 L2 圖層當時沒有節點，空圖例是正確行為；驗證切到已有 L1，沒有改動正式偏好，也未啟動模型。此前待部署記錄已由本節取代。
