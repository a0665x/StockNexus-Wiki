# Read API contract and scenario details

GET `/api/context/{resource}`. All resources are cache-only; `network_requests=0`, `model_calls=0` (catalog reports only network count). Use the exact stock from catalog. Requests require an allowed same-origin host (configured with `NEWS_ATLAS_WIKI_ORIGINS`); cross-site browser requests are rejected. No bearer credential is needed at the trusted local origin. This is a single-owner trusted-network application, not a multi-tenant gateway.

| Resource | Parameters | Response |
| --- | --- | --- |
| catalog | none | `instruments`: exact instrument, stored article count, wiki availability |
| news | instrument, days=7, end=now, query, limit=20, offset=0 | `items`, total, next_offset; title/source summary, URLs and source attribution |
| related | news parameters plus required id | Same page plus relation_evidence per article; shared symbols/entities/topics. This is candidate retrieval, not saved graph edges or semantic similarity. |
| prices | instrument, days, end | cached adjusted daily `bars`, observed `change_percent`, actual_start/end, fetched_at per bar; unavailable if absent |
| l1 | instrument, days, end, query=overview | EvidenceBundle: lens, manifest, opinions with exact claim/revision IDs and evidence, typed relations, assignments, gaps. Bounded to 20 initial opinions plus counterevidence (maximum 24, also byte bound); manifest reports truncation. No pagination here. |
| l2 | instrument, days, end, query, limit, offset | Saved run catalog; dates filter **run creation**, query matches research question |
| l2 | instrument, id | Exact saved result and bundle; fixed snapshot, days/end are not filters on that saved result (`window_applied=false`) |

`days` is 1–3660 calendar days, `limit` 1–100, `offset` 0–100000. `end` must be an ISO timestamp with timezone, exclusive and not future. News filters publication timestamps; it is current cached content, not an as-known historical archive. L1 uses the existing as-known snapshot retrieval. Its manifest includes current processing watermarks; do not describe these as historical coverage. Separate requests are separate SQLite snapshots; pin exact returned IDs for reproducible citations. Future completions can change subsequent reads.

Prices select full date buckets before end's UTC date, use the latest available cached vintage, and report actual first/last sessions. Formula: `(last_close / first_close - 1) * 100`; split adjusted, excludes dividends. This is not mean forward return, forecast, historical-as-known pricing, or institutional flows. No holdings, fund flows or order-book data is exposed. Sparse bars do not imply full window coverage. Missing inputs remain unavailable.

## Other existing APIs

- `POST /api/cache/graph`: cached news by query/source membership; can compute rules-based graph edges. Supply the full SearchRequest from deployed OpenAPI, `defer_relations:true` for news-only. This older path can initialize a stock store; use context/news for strict read-only lookup.
- `POST /api/graph/build`, `/api/graph/filter`, `/api/graph/explore`: operate on caller-provided articles/graph. Build obeys relation settings; explore traverses roots. Do not confuse these with DB lookup. See deployed schemas for exact payloads.
- `GET /api/wiki/node?instrument=...&id=...`, `/article`, `/graph`, `/markdown`: exact Wiki nodes, source revisions, graph versions and Markdown.
- `GET /api/wiki/research/runs|run|lenses|taxonomy|job`: existing research views. Use instrument and id where required. Some older reads observe source freshness; the context family is strictly read-only.
- `POST /api/prices/lens`: explicit Massive acquisition of adjusted daily prices, using ticker and articles[{id,published_at}]. This can perform network requests and write price cache. Its `observations` use a different forward-return definition; do not use them as the observed window change.
- `POST /api/search/result`: explicit news acquisition; inspect partial and provider errors. Not a read-only fallback.
- `POST /api/wiki/plan` then `/jobs`: explicitly authorized L1 work. Reuse existing DB via news_db:true; read Wiki specs before starting.
- `POST /api/wiki/research/query`, `/save`, `/refresh`: explicit L2 generation and saved-Lens maintenance. They can consume model tokens; query/refresh may be blocked while L1 owns the model slot. Reading existing context remains available.

## Example: why NVDA fell

1. catalog → verify NASDAQ:NVDA.
2. prices?instrument=NASDAQ%3ANVDA&days=7&end=<UTC cutoff> → check whether prices actually fell and report actual sessions.
3. news with same window → headline/summary timeline; page through relevant reports.
4. related with chosen article ID → other reports, retaining their source dates.
5. l1 with query=overview or a specific catalyst → exact shared claims, support/counterevidence, pending/truncation.
6. l2 list (a broader creation window may be necessary) → selected id → compare saved assumptions and evidence cutoff with current reports.
7. Distinguish observed facts, reported explanations and your conditional synthesis. If prices are unavailable, say the decline has not been verified from this server rather than inventing its size.

Status codes: 400 invalid/ambiguous parameters; 403 access configuration; 404 unknown stock/resource/article; 503 DB unavailable. Retry a read after a transient 503; never switch into model generation as a retry strategy.
