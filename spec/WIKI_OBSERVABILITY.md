# Wiki execution traces and performance diagnosis

## Contract

From the November 20 trace deployment onward, all stocks use private structured stage logs for preparation, L1 serial/root-worker calls, classification, L2 synthesis/review, and saved-viewpoint comparisons. This is execution metadata, not a transcript of hidden model reasoning. Historical stage durations cannot be reconstructed from old job timestamps.

- `data/private/wiki-trace/python.jsonl`: application stages, UTC timestamps, monotonic elapsed milliseconds, span/parent span IDs, instrument, job/call IDs, worker/root/segment identity, model/effort, repair flag, input size, output counts and returned token usage.
- `data/private/wiki-trace/bridge.jsonl`: the same job/call correlation across the Unix socket; model catalog check, SDK call, response parsing, completion/failure, and a heartbeat every 15 seconds while a call remains in progress.
- Each file rotates at 8 MiB with five backups (`.1` newest through `.5` oldest). Total budget is approximately 96 MiB across both streams. These logs are bounded, not an indefinite audit archive. Copy rotated files into private archival storage before retention expires if a longer investigation is needed.
- New files use 0600 and the trace directory 0700. Evidence bodies, prompts, responses, credentials and raw exception messages are excluded. Safe errors include category/type and Python source frame locations. Existing rejected-proposal records and model receipts in Wiki SQLite remain the source for exact validation details and usage; the new logs do not replace them.
- Writes are serialized per process/file. Python and Node use different files. Logging failure warns once on stderr and does not change model/publication behavior. Partial or rotated history is explicitly reported as incomplete rather than inferred as success.

## Reading a trace

Run from the repository root:

```sh
python3 scripts/wiki_trace_report.py --instrument NASDAQ:NVDA
python3 scripts/wiki_trace_report.py --job JOB_ID
python3 scripts/wiki_trace_report.py --job JOB_ID --json
```

The report reads current and rotated files, lists stage counts, accumulated/p50/maximum durations, safe errors, latest job states and unfinished spans. Use `--directory PATH` for a privately archived trace folder. Empty logs return zero events, not fabricated timing. Malformed/partial lines are counted.

Start with Python `model_call` versus `publish`, `context`, `prepare_forest` and validation. Join `call_id` to bridge `sdk_run`/`catalog`/`parse_response`. SDK duration includes provider queueing, network, inference and output generation; streamed SDK lifecycle events show when the turn started, when an output item was observed, and whether the SDK reported reconnection. Provider queue time and time to first token are not separately exposed. `input_bytes` is serialized application evidence/context or bridge request bytes, not exact prompt tokens; returned `usage` is authoritative for token counts. Failed calls may have no usage receipt.

Stages are nested and workers overlap: **never add Python + bridge or all stage totals to claim wall-clock job duration**. In traces from before the November 24 isolation change, `context_wait` includes context resolution and coordination; `context_lock_wait` isolates condition-variable wait, while nested `context` measures retrieval. `queued_ms` is elapsed since the job's previous saved timestamp at admission, including claim/setup overhead; it is not model-provider queue time. Requeued work has a separate admission event each scheduler turn. `research_deferred` identifies L2 waiting for queued/running L1 or classification across stocks. A span without a terminal event can be active, interrupted, or missing rotated history; a heartbeat does not prove token progress.

Opening or polling a Wiki does not issue model calls. Preparation and enqueue spans link `plan_id` to the eventual `job_id`; checkpoint reuse, published/rejected batches, job failure/cancellation/completion and startup are distinct events. The trace does not log every polling GET or every SQL statement. No schema, prompt, batch-size, model, reasoning or retry policy was changed for observability.

## Why an L1/L2 result takes time

L1 reads titles/provider summaries (not fetched article full text), plus bounded related original evidence, existing interpretation pages, a taxonomy and detailed generation rules. It extracts Claim/Event/Thesis nodes, exact quotes, scope and provenance, classification, conditions, bilingual text by default, and only supported relations. It can revise an existing proposition, but never has to invent both a supporting and opposing position. Each root can contain multiple capacity-limited sequential segments; nearby roots can share context. Workers may read the same opinion concurrently. Only actual competing revisions are checked at publication.

The host validates exact citations and permitted relation semantics before publishing. A rejected L1 proposal may receive **one** model repair call; it is not an unlimited retry. Standalone classification backfill now sends up to four opinions in 48 KiB of shared evidence. A batch-specific timeout or invalid reply can split once. Traces record packet bytes, targets, distinct nodes/citations, recovery turns and splits. See the [classifier and cache acceptance record](references/wiki-cache-classifier-20261120.md). The scheduler processes L1 work and classification before running L2, so waiting for L2 can be an upstream dependency delay.

L2 selects a frozen L1 evidence bundle and calls `research_fusion` to produce conditional synthesis, supporting/counter evidence and gaps. If it contains new inferences, a second call `research_review` checks semantic support. Exact excerpts alone skip that second call. A failed semantic check preserves previous results and does not automatically retry. These L2 calls have a 600-second deadline and a 640-second Python socket deadline.

## Observed NVDA baseline (read-only, November 20)

For the earlier three-worker parent `36b0116765f94ae9b066dda22a0efec0`, SQLite retains 45 L1 receipts, none marked rejected. Per-call input tokens: median 23,130, range 15,879–26,021; output tokens: median 6,823, range 929–13,553. Batches contained 2–12 article records; this is not a unique article-coverage count. Reported token counts are not word counts or exclusively visible output characters.

Classification job `5c32ba0f96524cbe999188fb67342fb0` saved three successful receipts (maximum input 33,340 tokens, output 2,936) before a later call hit the 600-second timeout; progress was 36/147. This establishes substantial model work and an actual model-call deadline failure. It does not establish a percentage breakdown of old job runtime, provider congestion, or a throughput guarantee. The new trace will supply attribution for future runs; no paid job was replayed to fill missing historical measurements.


## November 24 NVDA worker incident

On November 24, the 10:50–11:03 Taipei job produced eight successful model calls and four 600-second SDK timeouts. Workers 3, 4, 7 and 8 were on their first segment. Their local SDK sessions recorded input setup, then no final message, usage or terminal error. Worker 3 had zero existing context pages. Old bridge heartbeats established only that the bridge process was alive. The underlying provider queue, network and inference durations cannot be recovered from these records. Workers 1 and 6 separately waited about 512 and 601 seconds on the earlier shared-opinion lock. The successful calls published v101 through v108.

The bridge exposes the last SDK lifecycle stage and time since the last event for each active call. A root update can continue past ten minutes if an SDK reasoning or answer event arrives. Ten minutes without model output activity or twenty minutes total ends the call. Bridge heartbeats, turn setup and reconnect notices do not extend it. The Python socket allows 1,240 seconds for a root update. Other operations retain their existing deadlines. Traces correlate transitions, elapsed time and deadline kind; they omit output and reasoning text. The worker panel shows the latest failed tree and segment, pending retry count, and independently active siblings.

The threaded regression holds one turn open while all trees read the same revision, verifies that another lane starts a later tree before release, then checks coverage, explicit resume and a real concurrent UPDATES rejection. Stream fixtures cover silence, progress extensions, provider errors, early termination and the hard ceiling.
