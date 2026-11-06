# 第一階段驗證紀錄

日期：2026-11-04。範圍：設計契約與本機診斷，不是compiler／研究引擎驗收。

- `python3 scripts/wiki_readiness.py --sample-size 30`：已以唯讀 transaction 檢查本機既有DB；90篇欄位抽樣與價格筆數見 [readiness.json](readiness.json)。無provider／LLM請求。
- `python3 scripts/verify_wiki_design.py`：15項離線設計fixture檢查通過，涵蓋strict Relation schema、synthetic引文hash、禁止CAUSES／缺版本引用／混合confidence／無時區、依賴方向、模型自行verify、回放時間與報酬算式。沒有查真實引用端點或執行LLM語意評估。
- 本機開發檢查使用jsonschema 4.26.0；未新增Docker runtime套件。
- `python3 spec/scripts/verify_docs.py`：26份spec Markdown的本地連結與必要入口通過；`git diff --check`通過；兩個新Python腳本AST語法檢查通過。
- 目錄已由 `GraphNews` 改為 `StockNexus-Wiki`；分支 `llm_wiki`，origin為 `https://github.com/a0665x/StockNexus-Wiki.git`。原有未提交修改保留，未自動commit／push。
- 從新路徑執行 `./run.sh up --non-interactive --tailscale off`：Docker重新build成功、container healthy、首頁HTTP 200、Chat running且程序路徑為新目錄。Compose working_dir與data bind mount均確認使用新目錄；既有Tailscale routes保留。
- 更名後再次唯讀檢查：Google 7,205／Massive 9,325／Yahoo 16,487，日線3,048筆，與搬移前一致。首次沙箱讀取因新路徑SQLite WAL權限失敗，取得新目錄存取權限後檢查成功；不是資料遺失。
- startup執行了既有DNS／HTTPS reachability checks，未執行新聞下載、行情補抓或LLM編譯。
- 附件20項runtime驗收均待後續階段；算式fixture通過不等於production labeler已驗證。無真實策略收益、校準品質或因果效果結論。

## 2026-11-05 runtime 後續交付

此頁上方保留第一階段設計檢查紀錄。後續已加入獨立 DB、增量 compiler、背景查詢追蹤、Wiki UI 與 REST；實際範圍及測試見 [WIKI_RUNTIME](../../WIKI_RUNTIME.md) 及 [CHANGELOG](../../CHANGELOG.md)。完整研究矩陣中的依賴重評、預測／Outcome／回測仍未完成，不把本次 runtime 測試替代該驗收。
