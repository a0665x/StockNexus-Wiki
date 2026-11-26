# L1 viewpoint lineage

An L1 thesis records an interpretation of the news available for one instrument. A quote can establish that a supplier reported a delay while the revenue effect remains open. The reader displays operating impact and quote support separately. For a conditional thesis the model states its mechanism, conditions and an observable development that could change the interpretation.

## What a new report changes

| Comparison with an existing thesis | Published result |
| --- | --- |
| Same original publication, same URL, date, title and summary, different feed ID | An eligible single-article update links the two sources without a model call. |
| Restatement with no additional observation | The model can finish the batch with no new interpretation. |
| Same proposition with additional supporting evidence | A source-to-opinion `SUPPORTS` edge carries the exact new quote. The original text keeps its original citations. |
| Changed premise or reversed conclusion about the same question | `UPDATES` connects the new revision to its exact predecessor. Both versions can be read. |
| A distinct question follows from an existing thesis that still holds | `EXTENDS` connects child to parent. Both opinions stay available for further development. |
| None of the retrieved theses can be continued | A new thesis records the closest supplied thesis and why its mechanism, scope or conditions differ. A first thesis records what prompted it. |

The compiler checks existing extraction credit and tree checkpoints first. It retrieves a bounded set of current opinions for the same instrument, reserving space for theses. The model compares their propositions with the new batch. Publication checks verbatim quotes, parent type, comparison ID and relation direction. Exact proposition reuse and stale revision-base checks run in the publication transaction. Paraphrase matching depends on candidate retrieval and model judgment.

Open **Wiki → a viewpoint → Viewpoint lineage** to follow exact parent, child and revision links in the selected version, including a neighbor outside the graph rendering budget. Subsequent supporting articles appear below the original citations. Historical views expose edges published by that version. Older records with no recorded decision still expose their saved relations. The selected-interval workload panel explains the pipeline before starting. Once a segment publishes, the activity panel reports its actual comparison and decision counts.

## Evidence scope and compound viewpoints

Graph root coverage uses the frozen News exploration rules. Selected trees cover the eligible target articles in the chosen UTC date interval. Tree members can overlap or supply older context. A target receives coverage once all segments of its tree finish, including a valid batch that yields zero viewpoints. The two workload bars count articles and trees respectively. Date fields and slider handles edit the same interval. While a job runs, its applied scope is frozen.

The News timeline counts all filtered articles. With view-scoped relation calculation the rendering budget also limits which articles enter that calculation. Selecting an older time cell prioritizes that date and nearby articles for the available slots. Lines still require a qualifying cross-cell relation. Members sharing a channel and day can occupy the same cell.

In **Wiki settings**, enable **Compare VIX in L1** for a job that should consider a joint stock/VIX interpretation. The compiler can supply up to two archived VIX reports from that instrument's captured news in the preceding seven days. A joint thesis needs dated quotations for the stock and VIX premises. The stock and VIX observations may come from one report. The optional input supplies published news and does not fetch price series or calculate correlations. Existing extraction credit still applies.

## Acceptance scenarios

Run `tests/run_l1_bdd.sh all` from the checkout or select one group. The tests use temporary databases, a scripted model and local JavaScript fixtures. The range and memory groups require Node.js and the `jsdom` module, installed locally or available from the system Node module path.

| Group | Observable behavior |
| --- | --- |
| `range` | Latest slider/date edit wins over a slow response. The UTC interval and source/tree counts agree with the maintenance plan. |
| `timeline` | Old nearby nodes can re-enter an 800-article relation view. The same channel/day cell has no internal line. |
| `memory` | Reprints, corroboration, revisions, independent branches and new topics yield distinct results. A historical reader sees only the links available then. |
| `compound` | Joint theses require stock and VIX premises. Future, stale and VIX-only material cannot provide the required pair. |

Run `tests/run_l1_bdd.sh documents` for document-only revision, exact quoted spans, deduplication, source binding and frozen parallel inputs.
