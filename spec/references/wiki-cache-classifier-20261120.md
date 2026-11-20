# News-to-Wiki switching and L1 classification recovery

## User journeys

A researcher working in News can open the matching saved stock Wiki, inspect the last available graph immediately after a successful prefetch and keep reading while newer publications arrive. Classification backfill should preserve completed opinions when one part of a run times out. November 20, 2026, Asia/Taipei. The implementation is on `llm_wiki_unslop`.

| Given | When | Expected and verified behavior | Evidence |
| --- | --- | --- | --- |
| News accepts TSLA evidence and the unsubmitted ticker field says AAPL | The user stays on News | One read-only TSLA graph fetch warms the tab. No Wiki job is submitted. | [Browser with real SQLite and HTTP](../../tests/browser_wiki_cache.py) |
| TSLA v1 is warm and v2 has been published | A foreground status response is deliberately held open | v1 and both of its nodes are visible with the request still blocked. Releasing it applies two new nodes and shows v2. | [Navigation BDD](../../tests/browser_wiki_cache.py) |
| A different stock's first graph read is still in flight | A publication lands before the user enters Wiki | Foreground and background share the first full read. A token-based follow-up retrieves the newer publication. | [Concurrent navigation BDD](../../tests/browser_wiki_cache.py) |
| A graph is current | The user returns, changes stock, then returns to a pinned version | The unchanged acknowledgement has no graph body. The pinned version and type filter return on the correct stock. An old response cannot replace the selected stock. A stock without a Wiki stays empty. | [Navigation and absence BDD](../../tests/browser_wiki_cache.py) |
| A client holds a prior graph | A taxonomy changes at the same L1 version, a row is inserted, updated, reordered or removed, or the client changes its date or version filter | The reconstructed graph follows the server projection and its ordering. An unknown, expired, evicted or wrong-scope token gets a full snapshot. A wrong-stock reply cannot enter the cache. | [HTTP sync tests](../../tests/test_wiki_view_sync.py) and [client patch tests](../../tests/wiki-cache.test.mjs) |
| A running tree worker has a frozen root | The UI polls progress | Compact status returns the displayed workers' frozen trees, totals and usage. The next matching read can omit configuration. Navigation opens the exact saved members. | [HTTP state tests](../../tests/test_wiki_view_sync.py) and [worker UI](../../tests/browser_wiki_workers.py) |
| Two L1 opinions share a premise and exact quoted evidence | The classifier prepares the request | A shared node and citation have one stored body per packet. Each target retains its own dependency list. Differing translated text, term rules, IDs, quote spans and independent hashes survive compaction. | [Classification BDD](../../tests/test_wiki_classification_batches.py) |
| One of six test opinions causes a persistent deadline failure | A four-opinion batch times out | The original four split into two pairs once. The unaffected pair and the last two opinions publish. Four of six are saved. Explicit continuation processes exactly the two outstanding opinions to completion. | [Persisted queue BDD](../../tests/test_wiki_classification_batches.py) |
| A response is incomplete, a target exceeds the UTF-8 budget, credentials/quota fail, or a cancellation races a late timeout | The scheduler advances | An incomplete parent publishes zero partial labels. Its two child batches survive a scheduler restart. An oversized target is recorded without a call. Global errors stop the job. A late result cannot restart a cancelled one. | [Classifier tests](../../tests/test_wiki_classification_batches.py) and [bridge tests](../../tests/chat-wiki.test.mjs) |

## Runtime behavior

News schedules a best-effort GET after accepting stock identity. It coalesces nearby updates with an 80 ms timer and suppresses repeat prefetch for the same stock for five seconds. The first visit can still wait for storage if the prefetch has not completed. The tab retains up to four graph query scopes, four instrument status records and four sets of view controls. Cached bodies stay in memory for the life of the tab. The existing workspace persistence still saves the last view's controls. Reopening a saved L2 layer reads its saved research when available. A changed News selection is sampled again on entry for subsequent Wiki maintenance.

The graph cache key includes instrument, version or as-of, and UTC bounds. The two views remain independent publications. News changes affect its selections and future maintenance. The Wiki shows newly published evidence and classifications when they become available. Reading a graph or its progress consumes no inference calls.

- `GET /api/wiki/graph?instrument=…&sync=1` returns a full graph, an opaque token and a publication/classification epoch. Supply `since` for the same scope. The response kind is `unchanged`, `delta` or `full`.
- Deltas identify their base token. Ordered row collections support upserts and an optional final ordering that excludes deleted IDs. Keyed histories and memberships carry replacements and deletions. Changed aggregate sections, including taxonomy or perspectives, travel whole. The application accepts only the expected stock and query and retries a mismatched patch base once with a full request.
- The server keeps up to 12 hash manifests. An unchanged SQLite/WAL signature takes the fast path. A changed signature can require rebuilding and hashing the projection on a consistent read transaction, even when the resulting token agrees. A server restart or eviction can require a new full fetch.
- `GET /api/wiki/jobs?instrument=…&view=compact` returns progress, coverage, epoch and a configuration token. Resend `config_token` to suppress identical settings. The active worker supplies the frozen tree for its link. The full graph and jobs GETs remain available to existing consumers.
- Standalone `classify_l1` backfill admits up to **four opinions and 48 KiB of compact UTF-8 evidence JSON**, including the frozen taxonomy. Instructions, SDK framing and the response schema add further input. Mandatory target evidence stays intact. Optional dependency omission is marked explicitly. The host validates responses against the original full taxonomy and exact revision IDs.
- Identical translations use their canonical fields, matching term defaults are encoded once in the prompt, and a citation's redundant hash can be recovered from its article revision ID. Compilation batch IDs remain in the stored L1 source. Differing values and source quotes remain available. The model receives the full substantive text of every admitted target.
- A confirmed 600-second deadline or batch-specific invalid response permits one split per original batch. Each half can run once. An unsuccessful half remains pending for explicit continuation after the other batches finish. Both the maintenance button and the older resume endpoint pass their selected news interval into backfill. A quota, authentication, unexpected tool-use or service error ends the job. Returned model usage is recorded even if validation rejects the reply. An unfinished call at service restart retains the existing interruption policy. Tree worker settings, L1 extraction checkpoints and L2 semantic review keep their existing behavior.

## NVDA measurements

A read-only projection used the **147 original target IDs and frozen taxonomy** of the historical timeout job, with the saved v231 corpus. The comparison rebuilt payloads offline. Both encodings used canonical compact UTF-8 JSON. The byte counts represent application evidence and exclude prompts, output schemas, retries and model output.

| Packing policy for all 147 targets | Calls if every batch succeeds | Total evidence bytes | Largest packet |
| --- | ---: | ---: | ---: |
| Previous production batching and nested context | 13 | 649,101 | 56,946 |
| Nested context with the new, identical four-opinion groups | 37 | 758,181 | — |
| Shared evidence with the new limits | 37 | 610,279 | 20,150 |

All 37 equal-membership packets shrank. Across the old and new batching policies total evidence fell 6.0% and the largest packet fell 64.6%. The new policy would require more successful calls on this particular workload. Per-call overhead, provider caching, label quality, billed tokens, failure rates and elapsed inference time require observations from actual subsequent work.

## Verification and follow-up

The initial fixtures exposed a single timeout terminating the original job with independent work left, repeated evidence bodies, and the absence of conditional HTTP reads. The new tests use temporary databases and a controlled model. The browser scenarios consume the application's actual HTML, JavaScript and SQLite HTTP responses. Delayed promises establish first-paint and race ordering independently of hardware speed.

The November 20 verification table, production wire measurements and older feature coverage are in [the test ledger](../TESTING.md). Read [the deployment handoff](../CURRENT_STATE.md) before resuming work on NVDA.

On the next authorized classification run, compare `classification_batch` evidence bytes and counts, split/quarantine frequency, completed opinions, returned tokens and wall-clock duration per completed opinion. The [trace guide](../WIKI_OBSERVABILITY.md) covers SDK wait and its measurement limits. On navigation, measure first visible graph separately from background refresh. Profile server-side projection and status decoding on busy stocks before changing the four-opinion limit or cache sizes.
