# Contextual Chat and UI tools

Entry: [PROJECT_MAP](PROJECT_MAP.md). Implemented 2026-11-03.

## Runtime architecture

The right details panel switches between news and Chat Agent. News DOM and graph
state remain mounted while chatting. Chat uses the host's existing Codex file-backed
login through the TypeScript SDK, not a browser API key. The original supplied
`codex-local-chat` example is retained locally; production code is in `chat/`.

Browser → same-origin `/api/chat/*` → Python Unix-socket proxy → host Node service
→ SDK thread → stdio MCP server → per-session browser command queue → existing UI
handlers → acknowledgement with updated state. The host socket is
`data/private/chat.sock` (0600); the container receives no host login mount.

`chat/service.mjs` owns bounded browser sessions, a thread per conversation, actual
SDK events, cancellation, disconnect handling and a 10-minute turn timeout.
`chat/mcp.mjs` exposes get_state, read_news, read_edges, read_wiki and act. These are real MCP
tools, not OpenAPI annotations. The browser proxy does not expose the tool route.

## Start and stop

Install Node.js 20+ and run `npm ci`. Authenticate with the host Codex account first.
`./run.sh chat start|stop|status` controls the bridge; `./run.sh up` starts it when
installed and `down` stops it. Without dependencies, news still works and the
launcher reports the missing chat prerequisite. `data/private/chat.log` contains
service diagnostics. Chat is currently for `http://127.0.0.1:8765` or localhost;
LAN/Tailscale chat needs an explicit authentication design before being enabled.

The bridge has an isolated configuration/work directory under
`~/.local/state/stocknexus-wiki/chat`. Its auth.json links to the existing host
login. It does not inherit the user's other MCP servers. Only these four allowlisted MCP tools have explicit approval in this integration.
Shell tools and web search
are disabled; the SDK runs read-only with no interactive approvals. Prompts and
news sent to the signed-in model are not local inference. SDK conversation records
may persist in that isolated home; New chat starts a fresh thread, not deletion of
old stored records. Browser chat messages are in memory and reset on refresh.

## UI contract

`AtlasRuntime.state()` exposes selected article, confirmed roots, category,
visible and scope IDs, view mode, search metadata, source/edge/time/glow controls,
render budget, work status and recent deliberate control actions. Passwords,
credentials, localStorage contents and Three.js objects are excluded.
`data()` returns sanitized full loaded article/edge evidence separately; tools
paginate results instead of putting the full graph into every prompt. It does not
read the entire database or fetch article full text. Displayed and loaded counts
are distinct. Hover is not confirmed selection. News snippets are untrusted data.

Chat preserves confirmed root focus while open or replying. New requests use the
current selection; get_state obtains a fresh browser acknowledgement during a turn.
The assistant can therefore follow explicit mid-turn selection changes. Responses
identify source URLs and must not treat rule scores as probabilities or causality.

`act` requires the current monotonically increasing state revision. A stale action
fails before changing anything. Buttons use click(); slider/text controls dispatch
input/change through existing handlers; article selection clicks its real news-list
button. Controls briefly highlight. This is semantic UI automation, not physical
OS mouse input or isTrusted events. No arbitrary JavaScript/SQL/credential control
is exposed. Supported controls are returned by state; unsupported actions fail.
New controls must be explicitly added and validated. Async relation/root work is
checked before acknowledgement, and longer work is reported as pending, not success.

Two random capabilities separate browser access from the model's tools. Every
queue command is associated with its owning session and a distinct command ID.
Closing/stopping a turn cancels pending commands; a missing browser times out.
Responses from another session cannot acknowledge commands. UI changes already
applied before Stop remain applied. New chat resets the thread and its tool token.

## Verification and boundaries

`npm run test:chat`: ownership, thread continuity/reset, cancellation, selection
pagination and UI acknowledgement. `tests/test_chat_proxy.py`: origin/route checks.
Existing Python and CJS regressions still apply. A real signed-in integration test
must additionally exercise MCP discovery, a cited answer, actual view/slider changes,
continuation and cancellation; mocked SDK tests cannot establish login availability.

This adds interactive discussion and UI controls only. Background LLM Wiki analysis,
article correction, persistent knowledge versions and automatic DB maintenance are
not implemented by this change. Existing snapshots, DB and graph evidence remain
under their original contracts.

Integration verified on 2026-11-03 with an isolated Chrome profile against saved
news: actual SDK/MCP cited answer, timeline mode and zoom 2 acknowledged by the
browser, root preserved, follow-up context, live cancellation and new conversation.
Run `python3 tests/browser_chat.py` for UI-only checks; `--live` also uses account
usage. Tests do not overwrite news or snapshots.

SDK references: [TypeScript SDK](https://learn.chatgpt.com/docs/codex-sdk),
[MCP configuration](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).
The standalone example's read-only/never policy alone is not sufficient for tool
execution; this integration explicitly approves only its four bounded MCP tools.

## 安裝與啟動

在儲存庫根目錄（本機 `/home/nvidia/Desktop/AI_WS/stocknexus-wiki`）執行 `./run.sh chat setup`，檢查 Node.js 20+ 並用 `npm ci` 安裝 lockfile 固定版本，包含 Codex SDK、CLI 及 MCP SDK。已登入時沿用登入；否則執行 `npx --no-install codex login`。`./run.sh up` 啟動 8765 網頁和整合橋接；亦可 `./run.sh chat start|stop|status` 管理。私有記錄在 `data/private/chat.log`，不可提交。

使用者提供的根目錄 `server.mjs`、`codex-chat.html` 是獨立 3210 範例，`node server.mjs --open` 啟動，Ctrl+C 停止；它不連到新聞 runtime 或 MCP 操作。後續維護應集中在 `chat/` 的整合服務。單獨複製範例才使用 `npm install @openai/codex-sdk @openai/codex`；本專案使用 `npm ci` 避免漏裝 MCP 或改動版本。重複匯入的 `codex-local-chat/` 留在本地且忽略。

## Separate Wiki compiler (2026-11-05)

The same private host process now also serves a tool-free structured-output Wiki compiler. Its `/wiki/*` socket routes are not exposed through `/api/chat/*`; the separate Python Wiki API controls plans, jobs, citations and per-instrument persistence. Chat keeps its existing localhost-only boundary. See [WIKI_RUNTIME](WIKI_RUNTIME.md) for the opt-in continuous compiler and explicit trusted-origin setting.

## 2026-11-06 聊天訊息操作

整合頁的 assistant 訊息不附逐則複製按鈕；文字仍可選取，原始來源連結仍可開啟。模型的中間說明與最終回答均沿用真實事件，MCP 決策／操作／回報流程不受影響。獨立 3210 範例不屬於本次 UI 修改。

Wiki Chat uses a separately mounted widget, session and runtime. `read_wiki` is paginated (maximum 20 nodes) and returns interpretations, citations and histories for the current stock/version/date scope. It rejects a News surface. Wiki actions expose only visible type/relation/category/version controls and node selection; version changes await the actual load before acknowledging. News `AtlasRuntime` stays mounted and unchanged. The compiler and chat discussion remain separate model workflows.

News 與 Wiki 共用的聊天輸入採文字框內右下角紙飛機 submit 圖示，保留中英文 aria-label／title 與鍵盤送出。空白及回覆中停用；移除原本獨立的全寬送出列。訊息與模型工具流程不變。

## UI language ownership and lifecycle

`AtlasI18n` owns the UI language. Both News and Wiki runtime contexts include
`language`; sessions, selections and datasets remain separate. `chat-panel.js`
owns all of its UI labels and keeps canonical status plus parameters, rendering
with the current language on every async update and `atlas-language` event.
Context cards use exact templates, then insert data. The global DOM translator
skips these owned regions and raw messages. User input, model replies and citation
labels remain original; only generated source-link labels and known UI/error
messages are translated. Unknown diagnostic details stay verbatim.

Same-origin tabs in the same browser profile receive localStorage changes through
the same update path as the language picker. Different origins/profiles do not
share this preference; host workspace recovery is a separate mechanism. A late
connect, sync or stream callback must not restore an old locale. Cancellation
acknowledgement must not overwrite a completed/stopped stream status.

Regression: [browser_chat_language.py](../tests/browser_chat_language.py);
causes and test boundaries: [language runtime incident](references/lesson-20261106-language-runtime.md).
