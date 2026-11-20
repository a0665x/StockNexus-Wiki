<p align="right"><a href="README.md" lang="en">English</a> · <strong>繁體中文</strong></p>

# StockNexus Wiki

想知道一個股票觀點是怎麼得出的，可以先看哪些報導在談同一件事，再沿著引用檢查哪些證據支持或反駁這個說法。StockNexus Wiki 會按股票保存新聞與觀點版本，也能讓你用自己的文件建立獨立圖譜。

[![股票新聞形成共享 L1 觀點，研究問題從 L1 選取證據建立 L2。自己的文件則透過 JSONL 匯入獨立知識庫。](docs/media/stocknexus-architecture-zh-TW.png)](docs/media/stocknexus-architecture-zh-TW.png)

## 快速啟動

準備 Python 3.10+、Docker Engine，以及支援 `up --wait` 的 Docker Compose。從專案根目錄啟動工作台。

```bash
./run.sh
```

依提示選擇資料目錄和連線方式，再開啟[本機工作台](http://127.0.0.1:8765/)。Google 新聞 RSS 和透過 Google RSS 取得的 Yahoo 地區新聞可直接搜尋。使用 Massive 時，在來源設定填入 API key。

要用 AI 整理 Wiki 或使用 Chat，請安裝 Node.js 20+ 並使用本機 Codex 帳號。已登入可略過第二行。

```bash
./run.sh chat setup
npx --no-install codex login
./run.sh up
```

## 研究一檔股票

1. **探索新聞。** 選擇股票與日期範圍，在 3D 圖譜或時間軸點開報導，就能查看連線依據與新聞原文。
2. **整理共享觀點（L1）。** 開啟同一檔股票的 **LLM Wiki**，按「開始整理」。每個觀點保留引用及修訂紀錄。圖譜模式可用 1、3、5 或 10 個 worker 分領不同新聞樹，展開進度就能查看各自正在處理哪一棵。
3. **建立專題研究（L2）。** 開啟「研究問題 · L2」，例如問「哪些報導支持或反駁『資料中心需求正在改善利潤率』的說法？」系統會從指定期間的 L1 觀點與證據整理答案。選「固定快照」保留當次結果，或選「持續追蹤」跟進後續證據。

在新聞或 Wiki 頁面都能用 **Chat Agent** 追問目前選取的內容。之後可以重開已儲存的對話，也可以匯出 Wiki Markdown 分享研究結果。

## 匯入自己的文件

把[文件匯入 skill 資料夾](skills/stocknexus-document-import/) 和文章交給 agent，再交代要處理的路徑。

```text
請讀取 stocknexus-document-import/SKILL.md，處理「文章或資料夾路徑」。
```

Agent 會整理章節、依內文建立連線，並產出已驗證的 `records.jsonl`。沒有標題時採用不含副檔名的檔名，未知日期可省略。

在首頁選「匯入研究文件」，選檔後先按「只預覽」，確認後再按「匯入並開啟圖譜」。同一知識庫的文章、章節與引用共用一張圖，和股票 Wiki 分開保存。[試用 JSONL 範例](skills/stocknexus-document-import/examples/manual.jsonl) · [匯入指南](spec/DOCUMENT_IMPORT.md)

## 延伸文件

[啟動與服務指令](spec/RUNTIME.md) · [資料合併與備份](spec/DATA_MERGE.md) · [Wiki 與研究層](spec/RESEARCH_LAYERS.md) · [API](docs/API.md) · [專案地圖](spec/PROJECT_MAP.md)
