# Debate Arena 實作計畫與第一版操作規格

**目標**　讓正反兩組代理人對同一個研究命題交換論證，讓多位評審檢閱每條主張的原始引文。使用者可以重看某次辯論當時有哪些材料、哪些席位發言失敗、哪一段推論仍有爭議。新聞圖譜、L1、L2 和庭次各自保有來源與版本。

## 1. 從 Paperclip 借用什麼

本次核對 Paperclip 提交 `635ed5a36480dc1886e6d18ee7eeb96f7486a81b`。下表把上游實作位置與本案採用方式對在一起。

| 上游元件 | 程式裡的行為 | StockNexus 的對應決策 |
| --- | --- | --- |
| Agent 資料與 adapter registry | Agent 存有 `adapterType`、`adapterConfig`。Server registry 依 type 選到對應的執行模組，模組可提供環境測試及執行能力。 | 使用者把角色放到席位後指定 runtime、模型、自訂角色指示。角色外觀、席位職責、模型各自獨立。[Agent schema](https://github.com/paperclipai/paperclip/blob/635ed5a36480dc1886e6d18ee7eeb96f7486a81b/packages/db/src/schema/agents.ts) · [Registry](https://github.com/paperclipai/paperclip/blob/635ed5a36480dc1886e6d18ee7eeb96f7486a81b/server/src/adapters/registry.ts) |
| 任務分派與 heartbeat | Issue 指派到 agent 後，assignment wakeup 服務排入喚醒，heartbeat 管理獨立執行、狀態和輸出。同一個模型可受不同 agent 使用。 | 庭次分派給座位。例：`con-challenger → Iris → claude / sonnet`。主持流程將題目、角色、前一輪發言與證據包交給該 adapter。後續用 turn ID 接入排程與恢復。[Issue routes](https://github.com/paperclipai/paperclip/blob/635ed5a36480dc1886e6d18ee7eeb96f7486a81b/server/src/routes/issues.ts) · [Assignment wakeup](https://github.com/paperclipai/paperclip/blob/635ed5a36480dc1886e6d18ee7eeb96f7486a81b/server/src/services/issue-assignment-wakeup.ts) · [Heartbeat](https://github.com/paperclipai/paperclip/blob/635ed5a36480dc1886e6d18ee7eeb96f7486a81b/server/src/services/heartbeat.ts) |
| Runtime 與認證 | Codex、Claude Code、Gemini 各自有接合程式，入口、配置、登入錯誤與 session 語意由該 adapter 處理。Registry 也有 HTTP、process 類型。 | 先提供四個具名 runtime。席位表單只處理配置，服務主機管理憑證。自訂 HTTP agent 在後續階段加入來源與權限清單。[Adapters](https://github.com/paperclipai/paperclip/tree/635ed5a36480dc1886e6d18ee7eeb96f7486a81b/packages/adapters) |
| 預算保留、結算 | 建立執行與實際用量入帳是不同事件。 | 第一版限制發言次數並保存可取得的 token。下一階段才用價格表、預留與結算建立金額硬上限。[Budget reservations](https://github.com/paperclipai/paperclip/blob/635ed5a36480dc1886e6d18ee7eeb96f7486a81b/server/src/services/budget-reservations.ts) |
| 半透明立體角色 | UI 讀取角色外觀；avatar worker 可由 ClipLab 的姿勢與色盤渲染靜態頭像。 | 五個角色使用相同上游造型系統離線繪製成透明 PNG，隨專案附 MIT 聲明。法庭拖曳使用靜態圖，一頁有十一席也無須為每席建立 WebGL 場景。[AgentAvatar](https://github.com/paperclipai/paperclip/blob/635ed5a36480dc1886e6d18ee7eeb96f7486a81b/ui/src/components/AgentAvatar.tsx) · [Avatar worker](https://github.com/paperclipai/paperclip/blob/635ed5a36480dc1886e6d18ee7eeb96f7486a81b/server/src/services/agent-avatar-worker.ts) · [ClipLab provenance](https://github.com/paperclipai/paperclip/blob/635ed5a36480dc1886e6d18ee7eeb96f7486a81b/packages/shared/src/cliplab/PROVENANCE.md) |

## 2. 第一版如何開庭

1. 從新聞工作台的 LLM Wiki 右側點 **Debate Arena**，或從 Wiki 工具列進入。首次開啟為空庭。選定研究標的，在中央黑板填寫可受證據檢驗的命題，例如「NVDA 本季資料中心收入成長主要由出貨量增加帶動」。
2. 將左側角色拖到空席，或先點角色再點席位。雙方各有立論員、駁論員、推論規劃員、總答辯員。上方一至三個評審席可各選不同環境、模型及權重。角色可以跨色、跨職務入席，以席位所示職責為準。
3. 在配置視窗填入代理人名稱、runtime、模型及額外角色指示。確認後，代理人會進入此瀏覽器可重用的席庫。點已入席角色可編輯；拖回席庫或按「移出席位」即可離席。設定另一個席位時按關閉可放棄該次變更。
4. 雙方各四席及至少一位評審配置完成，且主機可偵測所選環境與模型後，點 **敲槌開庭**。黑板下列出本庭的發言呼叫上限。每個已選服務都會收到本庭封存材料，可能包括綁定到該股票的研究文件原文。
5. 從「庭次紀錄」檢視來源、每席回應、回合失敗、引用、判決與個別票。重大爭點可留下未決結果。既有庭次保留當時的席位配置，後續改動瀏覽器的草稿不會改寫已開庭紀錄。

| Runtime | 模型與認證方式 | 可用性判讀 |
| --- | --- | --- |
| Codex | 使用專案現有 Codex SDK 與主機登入。從橋接目錄選模型。 | 可讀到模型目錄。實際登入狀態及模型配額仍以模型回應為準。 |
| Claude Code | 主機 `claude auth login` 或主機 API 憑證，透過 `claude auth status` 查核。席位填寫該帳號可用的模型或別名。 | 讀取 CLI 的登入狀態，只將可用與否傳回瀏覽器。個別模型權限在呼叫時確認。 |
| Ollama | 在橋接主機啟動 Ollama、下載模型，清單讀自本機 `127.0.0.1:11434/api/tags`。 | 必須能讀到已安裝模型，推論走 `/api/chat`。 |
| Gemini CLI | 主機安裝支援 `--admin-policy` 的 CLI，橋接程序環境須有 `GEMINI_API_KEY`，席位填模型 ID。 | 檢查 CLI 與主機金鑰是否存在。每回合使用暫存環境、停用 hooks、MCP、extensions，套用拒絕工具的 admin policy。瀏覽器 OAuth 是後續項目。[Gemini policy engine](https://geminicli.com/docs/reference/policy-engine/) |

首次安裝沿用專案的 `./run.sh chat setup`。既有 Docker 安裝在方便中斷作業時執行 `./run.sh up` 載入更新；該流程也會依模組版本更新主機橋接。入口為 `/arena`。草稿可在橋接離線時編輯。不同席位選相同 runtime 時共用該主機已授權的帳號，角色指示與每次呼叫的上下文獨立。目前支援單一受信任工作台；多人部署的帳號與庭次隔離列在階段 3。

## 3. 辯論、證據與裁決

| 階段 | 誰參與、看得到什麼 | 留下的紀錄 |
| --- | --- | --- |
| 資料準備 | 兩隊平行。立論員先看封存來源目錄，自選 E 原文與 K 背景節點。規劃員讀同隊簡報與選取的材料，預判反方假設。 | 實際讀取的索引、交給隊友的簡報與攻防路線。 |
| 立論、駁論 | 每庭隨機決定先手，雙方輪流說話。只要已有對方發言，每一席必須回應最近的對方 Claim。 | 命題 ID、回應哪一條、論據與逐字引用。 |
| 隊內重整 | 任一方在前兩輪發言請求重整，駁論結束後由該隊總答辯員檢視新材料與對手攻防。雙方都有需要時平行執行。 | 各隊更新策略的簡報，在下一輪送交隊友。 |
| 深化、總答辯 | 兩方繼續交替發言。規劃員檢驗替代解釋，總答辯員說明哪些推論仍然站得住腳。每次公開發言最多主動補查一次封存索引。 | 新命題、回應鏈、補查對象及實際通過比對的引文。 |
| 獨立評審 | 評審平行查看完整發言及相同封存材料，逐條核對原文、評分與說明。 | 個別判斷、加權裁決、優勝方或平手／未決。 |

準備四席、公開交替八席、評審一至三席。加上至多兩席隊內重整與八次補查後的追加呼叫，每庭上限為 23–25 次席位模型呼叫。每席 180 秒期限涵蓋該席補查。逾時或失敗會記錄於該席，下一席可接續已成功的論點。觀察員只在使用者提問時另行呼叫，並行讀取當時的庭次快照。

**法庭工作台**　保留原頁首、圖譜模式按鈕和已載入的背景工作區。左欄排席，中欄觀看法庭，右欄在「索引來源」和「Chat Agent」之間切換。角色以帽子、煙斗、書、領帶、評審假髮區分。實際的調閱、引文核對與簡報交接事件會驅動席位與書堆動作；偏好減少動畫時保留文字與高亮。點書堆顯示本庭封存的新聞快照邊、Wiki 節點／關係與引用。點某一條歷史調閱事件可看到當時的高亮。沒有節點或快照邊時如實顯示。

**上層 Chat Agent**　使用該庭支持方總答辯席的 runtime 和模型，另開唯讀詢問。可讀取雙方簡報、命題、正在執行的席位、查證紀錄及裁決。回答依送出問題時的紀錄，無法更動發言、排程與票數。

**什麼算證據**　新聞如果只說「公司提高資本支出」，原句可以支持「公司公告提高資本支出」。若辯手進一步主張「因此次季每股盈餘會上升」，評審須檢查支出如何影響盈餘、時點及替代解釋。兩方都缺少這些材料時，兩方都可以得到「目前材料不足」。研究材料的覆蓋、引文存在與命題成立是三件可以分開檢驗的事。

**第一版證據包**　由 Web 服務端在開庭時唯讀擷取，前端提交的來源包會被服務端重建。最新 30 日新聞最多 8 篇；最新已儲存新聞圖譜快照最多 3 條邊與端點文章；最多 4 段當時可用、經股票綁定的文件；已發布 L1 最多 6 個節點，每節點最多 2 條核過位置的封存引文；近 30 日內最新一份既存 L2 取最多 3 條命題，各自從該 L2 的原始快照解析最多 6 個被引用的 L1 節點，保留較早觀點的連結。每個可引用原文片段最多 1,600 字元。L2 推論及圖譜關聯以背景資料提供，正式判決須回到新聞或文件。初版取樣依時間與固定上限，擴大到封存範圍外的題目搜尋、跨標的及選擇特定歷史版本留到階段 2。

**票怎麼算**　每位評審對每條 Claim 給出支持、反證、材料不足或棄權，記錄理由與可信度、邏輯、反駁、完整性四項 0–4 分。支持與反證至少須附一段可在封存材料逐字找到的引文。評分讓研究者理解分歧；裁決採評審預設權重 1、可調 1–5 的絕對過半。分母包含所有配置的評審；格式錯誤或失敗的整張評審票視為棄權。以權重 2、1、1 為例，兩票權重合計 2 仍是未決，合計 3 才通過。相同 runtime 與模型的評審在紀錄裡有共同偏誤提示。精確引文檢查只證明文字出現在該版本；引文與結論的關聯留給獨立評審及人類查閱。

**如何選出優勝方**　每位評審對每一方的命題取平均論證分。支持得 1 分再加四項品質總分除以 16，有反證扣 1 分，其他項目計 0 分。兩方均有受評命題且至少有一項獲支持時，較高平均分的一方得到該評審的票，分數相同投平手，其他情形棄權。總票數依配置權重計算，支持、反對或平手需取得全體權重過半，否則未決。可展開紀錄查看每位評審的雙方平均分與投向。

## 4. 工程分期與驗收門檻

| 階段 | 實作範圍 | 可接受的完成結果 |
| --- | --- | --- |
| 1 · 已實作，待實機帶帳號驗收 | 空庭、角色與拖放、每席模型設定、唯讀證據快照、固定回合、逐項評審、庭次保存與回放。採用專案既有 Python API + Node bridge。 | 使用者能從空席開庭。固定測試可重現雙方均不足、失敗席位與棄權、不實引文及重啟中斷。上線時另以有權限的帳號執行一次短庭。 |
| 2 · 擴充證據與交互詰問 | 擴充 Knowledge Gateway 提供限定範圍的 REST/MCP 工具，依黑板題目檢索、去除同源轉載，回傳真實 DB 邊、原文範圍、available_at。支援 NVDA + VIX、研究者勾選來源與結束日期。允許評審要求補證、辯方答覆一次。 | 固定案例含晚到文件、重複轉載、L2 推論及矛盾報導。鎖定時間後可重播，清楚顯示缺哪一類材料、補查了哪些來源。 |
| 3 · 多帳號與可靠排程 | Registry 持久 ID 與版本，認證引用存在主機 credential store。增加 provider 登入狀態及連線測試、自訂 HTTP adapter 白名單、每個角色的工具權限。排程加 turn ID、租約、心跳、發言輸出事件、對單席重試、金額預留及用量結算。 | 不同帳號與庭次資料隔離；同一發言重送不重複立項。可分別診斷等待席位、認證、限流、模型生成與解析失敗。超出預留金額會在下一次派送前停止。 |
| 4 · 評審校準與反偏誤 | 盲化發言人與正反順序，明示同一模型家族、同源新聞及共享假設；聚合同家族票重。建立有人類標註的支持、反證、未決與兩方均不足校準集。 | 對調左右席位、複製相同模型評審，記錄逐條判決的變動率。按標註報告引文不相干率、未決率、評審分歧及權重敏感度，校準結果隨版本保存。 |
| 5 · 研究回寫與演化 | Debate Memory 增加已證實、待追蹤、反駁與延伸關係。把候選 Claim 與既有 Wiki 觀點比對，產生預覽差異，由研究者審核，核准後單向寫入帶來源的 Wiki 新版本。 | 新聞原文可追至版本及片段，庭次可追至評審與模型。拒絕候選不改 Wiki，同一決議再次送審不重複建點。下一庭可同時看到舊裁決與新反例，且能區分研究產物與原始資料。 |

## 5. 儲存與介面契約

- `dist/arena.html`、`arena.js`、`arena.css` 管理席庫、U 形法庭、草稿與逐項裁決顯示。首次入席時把角色指示、runtime 與 model 存入本機席庫，可重用至其他標的。股票的題目與席位分開保存。
- `news_atlas/arena.py` 是知識與來源邊界。沿用同源檢查及唯讀 SQLite 連線，經私有 Unix socket 派給 `chat/service.mjs`。所選股票是資料邊界。未指定股票時庭次使用空證據包。
- `chat/arena-adapters.mjs` 對外提供 `catalog()` 與 `turn(profile, prompt, signal)`。後者回傳文字及實際可取得的用量。新 runtime 的測試須涵蓋可用性、失敗、取消及結果擷取。
- `chat/arena.mjs` 按席位建構上下文、分派回合、驗證 Schema、比對引文及彙總權重。逐庭檔案存於橋接資料目錄的 `private/arena/<uuid>.json`，以暫存檔原子更名保存。第一版一次接一庭，所有已授權使用此本機工作台的人共用庭次歷史。
- `GET /api/arena/catalog` 讀執行環境；`GET /api/arena/runs` 列出庭次；`GET /api/arena/run?id=<uuid>` 讀含配置、證據包、回合與票的完整紀錄；`POST /api/arena/start` 接受 `id, instrument, topic, seats`；`POST /api/arena/cancel` 接受庭次 ID。`POST /api/arena/observe` 接受庭次 ID、問題與近期對話，回傳答案及快照時間。同一 ID 與同一配置可安全重送。變更同一 ID 的配置回應 409。
- 自動驗證分為證據閘道、辯論與投票、adapter 契約、介面操作四組。Python 執行 `python -m unittest discover -s tests -p test_arena.py`；Node 執行 `node --test tests/arena.test.mjs`；介面測試使用 jsdom，在 Debian 安裝 node-jsdom 的環境執行 `NODE_PATH=/usr/share/nodejs node --test tests/arena_ui.cjs`。測試資料與正式資料隔離。
