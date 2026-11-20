# 年度新聞、L1 與市場研究交接（2026-11-14）

本頁是一次明確授權批次的續作入口，不是恢復舊七股 heartbeat 的指令。先讀當下 private ledger、jobs 與 Git，再執行任何動作；本頁的進度是歷史觀察。

## 使用者確認的範圍

- 同步 `llm_wiki`，更新已保存有效股票及指定研究標的一年新聞，沿用既有 L1 並增量整理。
- 指定研究：NVDA、AMD、AAPL、TSLA、SpaceX、META、VIX、QQQ、ASML、AMZN、RDW、SNDK；既存有效股票另含 GOOGL、TSM。GOOGLE 是既存查詢別名，不另外建一個股票。空的錯字／片段分庫不當成股票。
- 「SPCX」已由使用者澄清為 SpaceX；「patents」為類似事件 patterns；資金分析是市場輪動及大型機構持股／資金行為，不是使用者個人資產配置。
- 新聞日期固定 UTC 2025-11-14 至 2026-11-13（含）；行情截至開始分析時最後完整美國交易日 2026-11-12。這是新的明確年度資料工作，取代本次任務沿用舊 GOOGL 月驗收限制的假設，但不復活舊取消工作。
- L1 使用 gpt-6.1-sol / high、Graph root、update；保留已有 revisions，沒有全量 review、沒有清庫。報告另以正式公告與真實日線分析，不宣稱它是所有年度 L1 完成後的產物。

## 執行入口與權威資料

- 正式專案仍是 `StockNexus-Wiki`；舊環境 GraphNews 路徑不存在。新聞權威資料為 `data/graph/<ticker>/news-atlas.sqlite3`，L1 為 `data/llm_wiki/<ticker>/wiki.sqlite3`。
- 本批操作紀錄：`data/private/annual-research-20261114/manifest.json`、`*-acquisition.json`、`l1-batch.json`、`*-universe-*.json`。私有檔不提交 Git；不記錄金鑰。
- `l1-batch.json` 的股票／partitions/job_id 是續作依據。API 送出前保存 submitting；若回覆不明，查 jobs 與 payload 後處理，不能重送猜測。停止或失敗不自動付費重試；權限／額度問題停止此批模型提交。
- 使用既有 `GraphRepository`、`search_source`、來源快取與公開 Wiki plan/jobs API。沒有新增產品 migration 或改資料庫 schema。
- 先讀 canonical query memberships；不把 raw 股票 DB 裡無關搜尋（例如早期 power／tpu）全部當成該股研究範圍。凍結圖譜 universe 保存 SHA-256；超過 9,000 個引用分批，每批圖關聯範圍有限，但共享 L1 成果可重用。
- 若來源補抓晚於已啟動模型，不改動該工作凍結輸入；完成後再對新增引用做增量補充。沒有新增引用時不建立補充工作。
- 完成需有非空範圍、pending=0，並等待既有分類／整理工作結束。第一版新發布、queued 輪替與下載完成都不等於整批完成。

## 來源與研究邊界

- Massive 請求共用 pacing，不能在不同股票上並行用同一 key 猛打。限流／權限錯誤保留缺口，不更換身分繞過。
- 單次取得的 request/time budget `limit` 不等於 provider 權限失敗；按回應的明確 missing_ranges 分成 RSS 單日、Massive 小區間，各補一次。單日仍達來源筆數上限時保留缺口，不遞迴無限重試。父請求的歷史錯誤與補抓後結果分開保存。
- RSS 是當下索引快照；完整掃描日期也不能稱為世界上所有新聞。保存標題、來源摘要、連結，不宣稱已取得付費全文。L1 的覆蓋率只對已取得且凍結的文章計算。
- SpaceX 上市前同一 SPCX 代號曾屬不同基金；依 Nasdaq 的證券身分公告，SpaceX 日線與 Massive 新聞從 2026-06-12 起，上巿前公司新聞用 SpaceX 名稱檢索。不得把前身基金日線拼接成 SpaceX 一年價格。
- Massive 的 VIX 指數權限不足，改用 Cboe 官方日線。VIX 是預期波動指數，沒有可當成股票的成交量或公司獲利。
- 價格相對強弱、ETF 淨發行及 13F 季末股數是三種不同證據。成交量不是機構淨買入；13F 的市值增加不是買進金額。比較同 CUSIP 股數、拆股及申報日期，不能把缺少申報當作清倉。
- 歷史相似檢索使用 canonical 範圍、公司名稱約束、去同標題、排除報價頁／模板標題、新舊相隔至少 45 天。文字分數僅是找證據的線索；同一合作的後續報導不計為第二個獨立催化。
- 使用真實價格特徵做 Ridge / 21 交易日診斷，訓練標籤成熟後才劃分樣本外。精確線性 SHAP 滿足加總一致；本次模型 MAE 13.05 個百分點，劣於零報酬基準 11.03，故不採用模型作股價預測。只有 3 個測試日期，不能聲稱完成一年期預測校準。

## 本輪實際驗證

Git 從乾淨 `8285c09` fast-forward 到 `f63e896`。執行 `./run.sh chat start`、`./run.sh up --non-interactive`；正式容器健康，HTTP research-view.js 與 checkout SHA 相符。沒有為了報告改動產品程式；本地報告／批次工具另保存。

| 行為邊界 | 實際檢查與結果 |
| --- | --- |
| 上游研究與 Chat 契約 | `python3 -m unittest discover -s tests -p 'test_research.py' -q`：24 通過；`node --test tests/chat-research.test.mjs tests/chat-wiki.test.mjs`：12 通過。Node 在允許 loopback 的環境重跑，隔離環境 socket 失敗不是功能缺陷。 |
| 真實付費路徑與保存 | 新 AMD job 首次觀察由 v27 到 v28，證明已發布成果；不代表年度完成。當次先重用 769 篇，其餘增量。後續狀態查 private ledger／API，不以此數字做即時判斷。 |
| 不拼接不同證券／不使用未完成交易日 | 報告測試拒絕 SpaceX 2026-06-12 前日線、重複日期與 11/12 後 bars，檢查 OHLC 合法。 |
| 報酬定義與未成熟 outcome | 21 期報酬用第 22 根與最後收盤計算；測試標籤晚於訓練截止且不超過行情截止。累積報酬不冒充平均日報酬。 |
| SHAP 不冒充預測能力 | 測試 baseline + contributions = prediction，劣於基準時 use_for_investment_forecasts=false。 |
| 歷史候選／完成度／缺量 | 測試候選非同篇且相隔 ≥45 日；L1 completed 必須非空且 pending=0；VIX 無成交量比；HTML 無未填 placeholders、所有圖檔／下載檔存在。報告 10 項測試通過。 |
| 真實瀏覽器閱讀 | 隔離 Chrome 開啟本地報告：圖片皆載入、8 章節、導覽可跳轉、1440px 桌面及 390px 手機無頁面橫向溢出，PDF 匯出成功。最初手機 innerWidth 被寬表格撐大，修正為內部捲動後用指定 viewport 寬度再驗證。 |

補充驗證：私有批次控制器 5 項隔離測試通過（既有分類工作阻擋新提交、凍結 SHA 不符不呼叫 API、未知提交結果保留 submitting、來源權限拒絕跨重啟保留、明確缺口只補一次）；不使用真實模型或 provider。正式觀察確認 14 股都有新年度 job，AMD 已達 v31；大圖冷快取期間部分 GET jobs 超過 60 秒，後續 AMD API 約 4 秒返回，SQLite 與服務健康核對無需重啟模型。這不是兩秒 UI 完整性能驗收，該負載下的狀態查詢延遲仍需獨立改善。

## 未完成與續作

本輪 14 股來源取得及有界補抓已完成一輪，canonical provider/id 引用合計 50,954 筆（跨股／來源可重複），仍有 RSS 來源上限缺口；L1 是長時間背景工作。交付圖文報告不會自動讓它們完成。先讀 ledger 中每個股票的來源缺口、活動 job、版本、coverage、錯誤。不要改用 resume 延長凍結截止日，不要重算已完成 revisions，不要為了讓狀態轉綠清庫或改低模型。

本批有限控制腳本保存於 private 批次目錄的 `scripts/stocknexus_annual_update.py` 與 `scripts/stocknexus_annual_l1.py`；有 file lock 與持久進度，不能再建立第二套批次。重啟前先看正在執行的程序與 ledger。

本輪未完成全市場 13F 彙總、帶身分的即時大戶交易、付費新聞全文、全年事件回測或可校準長期股價模型。這些與來源取得及 L1 pending 分開說明。報告保存在使用者 Documents/Codex 的 `StockNexus-Research-2026-11-14` 資料夾，不上傳私人新聞／模型成果到 GitHub。


## 2026-11-14 05:20 UTC：使用者指定 medium 與股票身分 UI

- 應用程式 04f79b8 已部署／推送，靜態 JS hash 相符；正式 Chromium 驗證既有 SNDK 唯讀股票與新建 14 個非空 DB 選項。
- 87 Wiki Python、9 Graph storage、9 專項 Chromium 檢查通過；40 spec 文件檢查通過。舊 browser_wiki.py 自動預覽假設失效，不列為本次全套通過。
- 上輪 2026-11-13T17:20Z 因 quota 停止，並非資料庫未建立。此輪 14 股 configure 已保存 gpt-6.1-sol/medium；固定日期／凍結引用與已發布 revisions 保留。閒置更換模型走 configure，避免 apply 重建全年度圖譜。
- 使用者新的「開始 medium」要求在原 quota 訊息重試時間之後；一次接續記錄保存在 private ledger 的 resumptions，舊失敗和工作 ID 留於 attempt_history。先 NVDA 驗證真實發布，再放行其餘；若供應商再次拒絕則 controller 停止，不自行循環重試。
- NVDA extraction 7c3831fe40c049ce942c86711e50d95f、classification 078ad271fab44daa946252db2aa85ef5 已確認 payload 為 medium，初始 API 顯示 queued；8,472 篇範圍／8,138 待補，並非完成。controller PID 與 hash 見 private/controller-process.json；後續以即時 API／ledger 為準。
