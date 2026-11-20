<p align="right"><strong>English</strong> · <a href="README.zh-TW.md" lang="zh-Hant">繁體中文</a></p>

# StockNexus Wiki

StockNexus Wiki connects stock news to the claims people make about a company. Explore related stories, see which sources support or challenge a viewpoint, and follow a research conclusion back to the articles it cites. You can also build a separate graph from your own documents.

[![Stock news feeds a shared L1 Wiki. A research question selects L1 evidence for L2. Personal documents follow a separate JSONL import path.](docs/media/stocknexus-architecture-en.png)](docs/media/stocknexus-architecture-en.png)

## Quick start

From the repository root, run the launcher with Python 3.10+, Docker Engine and Docker Compose with `up --wait` support.

```bash
./run.sh
```

Choose a data directory and connection mode, then open the [local workbench](http://127.0.0.1:8765/). Google News RSS and regional Yahoo coverage via Google RSS are available immediately. For Massive, enter an API key in the source settings.

For AI-assisted Wiki and Chat, install Node.js 20+ and use your local Codex account. Skip the login command if you are already signed in.

```bash
./run.sh chat setup
npx --no-install codex login
./run.sh up
```

## Research a stock

1. **Explore the news.** Choose a stock and date range. Open a story in the 3D graph or timeline to inspect the rule behind a connection and read the original source.
2. **Build shared viewpoints (L1).** Open **LLM Wiki** for that stock and select **Start processing**. Each viewpoint keeps its citations and revision history. In graph mode, 1, 3, 5 or 10 workers can take different news trees. Expand progress to see which tree each worker is processing.
3. **Ask a research question (L2).** Open **Research question · L2** and ask, for example, “Which reports support or challenge the claim that data-center demand is improving margins?” L2 retrieves relevant L1 viewpoints and evidence for the selected period. Save a **Pinned snapshot** or choose **Track updates** to follow changing evidence.

The **Chat Agent** in News and Wiki can discuss the current selection. Reopen a saved conversation to continue, or export the Wiki as Markdown to share your findings.

## Import your own documents

Give your agent the [import skill folder](skills/stocknexus-document-import/) and your articles, then ask it to prepare the import.

```text
Read stocknexus-document-import/SKILL.md and process <path to an article or folder>.
```

The agent returns a validated `records.jsonl` with article sections and links grounded in the text. Missing titles fall back to the filename stem. Unknown dates can be omitted.

Open **Import research documents** on the homepage. Choose **只預覽** to preview, then **匯入並開啟圖譜** to import and open the graph. Articles in the same collection share a graph with their sections and citations. The collection is stored separately from the stock Wiki. [Try a sample JSONL](skills/stocknexus-document-import/examples/manual.jsonl) · [Import guide](spec/DOCUMENT_IMPORT.md)

## Reference

[Startup and service commands](spec/RUNTIME.md) · [Data migration and backups](spec/DATA_MERGE.md) · [Wiki and research layers](spec/RESEARCH_LAYERS.md) · [API](docs/API.md) · [Project map](spec/PROJECT_MAP.md)
