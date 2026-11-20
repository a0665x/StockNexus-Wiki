# NVDA annual research — November 20, 2026

The user authorized a full local service restart, annual NVDA data acquisition, L1 processing with 6.2 Sol, and two L2 studies. This run does not resume other stocks or erase existing results. Git remains `llm_wiki` at `228f6a7`, with the document-import follow-up and onboarding documentation uncommitted. No push was made.

## Latest transition: user-selected three workers

This section supersedes the original single-worker L1 status below. The user chose three `gpt-6.1-sol` workers for L1; `gpt-6.2-sol` high remains the L2 model. The original job was cancelled at v184 after saving `wiki-before-workers.sqlite3` and `workflow-before-workers.json` in the private run directory. `transition-stop.json` records the explicit stop. Published revisions and frozen annual inputs were preserved.

The controller was resumed once (process metadata is in `process.json`), with first-part parent job `36b0116765f94ae9b066dda22a0efec0`, base v184, 1,424 reused revisions and 7,576 pending revisions. Read-only API failures now receive at most three attempts; mutation requests are never automatically replayed. Production SQLite and the real Tailscale UI confirmed three simultaneous lanes assigned to distinct trees, all with saved segments, and committed versions through **188**. UI snapshot: 23/1,170 completed trees, 1,424/9,000 article coverage; partial segments publish before final tree evidence credit. These are observations, not completion claims.

A progress-query 503 was traced to an unindexed sort of 28.7 MB of job payloads spilling into the container's 32 MB temporary filesystem. The additive timestamp index was applied online without restarting or replaying model work. The source constructor includes the same migration for subsequent builds. Check live status before any recovery; never start a second controller from historical IDs. The remaining annual partition and both L2 studies are still pending.

## Original runtime and acquired evidence

Rebuilt using `./run.sh up --non-interactive` and restarted the host Chat bridge after confirming no active model work. The container is healthy; `/documents` and `/api/capabilities` return 200. Served document HTML matches the checkout. Chat and Wiki report ready; the live model catalog includes `gpt-6.2-sol`. The previous image is tagged `news-atlas:before-documents-20261120`. Existing data and Tailscale routes were preserved.

The fixed source publication window is **2025-11-20 through 2026-11-19 UTC**, inclusive. The source database now contains **10,755 provider article records** in that window: Google 1,379, Massive 6,260, Yahoo 3,116. These are provider records, not a count of unique stories across publishers.

Massive has stored `complete` coverage for 365 days. Google has 355 stored snapshot days (November 10–19 remain unmarked); Yahoo has 347 (November 2–19 remain unmarked). All missing days received a bounded acquisition attempt; returned records were retained without inventing coverage. RSS snapshots never establish exhaustive historical coverage, and old stored coverage is not a claim of current cache freshness.

The standard NVDA price cache contains **250 split-adjusted OHLC sessions**, November 20, 2025 through November 18, 2026. The requested November 19 endpoint returned no session for that date. Volume, flow and volatility data were not acquired. Do not infer panic from price decline alone.

## Workflow and recovery

Private operational files are under `data/private/nvda-research-20261120/` (ignored by Git):

- `acquisition.json`: attempts, coverage, provider counts and price acquisition result. Acquisition completed; the final summary serialization was repaired without repeating successful downloads.
- `workflow.json`: authoritative controller status, exact model, scope, partition plans/job IDs and L2 run/lens IDs when produced.
- `input-0.json`, `input-1.json`: frozen provider references and evidence revision IDs, 9,000 and 1,755 records respectively. The split respects the current 10,000-record API bound. Hashes are in the ledger.
- `process.json`, `workflow.log`, `process.py`: detached controller process and diagnostics. A host/service restart does not guarantee this controller resumes.

The first L1 job, `6553f8039b9a43ce85da718c1b657558`, is running from base version 130. Its plan selected 9,000 records, reused 1,066 and has 7,934 pending. Initial graph planning took several minutes and a separate read-only progress request timed out; no duplicate model work was submitted. The remaining 1,755-record partition and both L2 studies are still pending. At 2026-11-20 00:23 UTC, SQLite confirmed a new committed version **131** (previously 130) while the job remained running. Job `done` was still zero because tree-level evidence credit follows completion of all segments; a published segment is not whole-year completion. Read the live ledger for newer progress.

New L1 calls use `gpt-6.2-sol`, medium reasoning, Graph root incremental update, bilingual output and existing graph settings. Completed evidence is reused across models; existing 6.1-derived knowledge is not recomputed. The second partition follows the first, and classification must be idle before L2 starts. Final annual extraction coverage is checked against every frozen revision rather than trusting the last partition's UI denominator.

Two L2 questions are queued: **panic selling** (support, counterevidence, alternative explanations and recovery conditions) and **future drawdown magnitude/duration** (conditional short/medium-term scenarios and invalidation conditions). New L2 calls use `gpt-6.2-sol` high and are saved as pinned lenses, without recurring refresh. They are not yet saved results at this handoff.

The controller stops on failed/cancelled/uncertain mutations and does not automatically replay model work. On recovery, read the ledger and live jobs first. An uncertain submission may already have produced a job; inspect its ID and published results before any explicit resumption. Do not start a duplicate controller. The run has a 14-day controller deadline; expiry records a block and requires inspecting any app job still active.

## Research limits and verification

Current L2 retrieval selects a bounded subset of L1 opinions using classification/full-text relevance and connected counterevidence. It does not consume the raw OHLC cache as a historical forecasting series; its existing contract explicitly marks market/baseline evidence unavailable. Numeric drawdown estimates must therefore be supported by eligible L1 citations, or reported as unsupported. A downloaded price series alone does not remove this limitation. News evidence is title/summary material, not fetched full articles.

Six isolated controller tests passed with mocked API responses: uncertain L1/L2 submissions are not replayed, running L1 prevents L2, user cancellation does not cancel replacement work, pending annual revisions block L2, and the exact completed L2 run is saved as pinned. Command: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s data/private/nvda-research-20261120 -p test_process.py -q`. This verifies sequencing, not real model quality or eventual completion. Operational completion must be confirmed from the live ledger and saved API results.
