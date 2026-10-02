# Design proposal, not completed architecture

## Authority and boundary
The source requirements permit CLI or hosted web, and plain Python or a framework. They require a 200-episode arc, sequential 400-700-word episodes with hooks, lasting human feedback, restart recovery, traceable bounded operation, and eventually 15 real episodes with two observed interventions. This scaffold is not those deliverables. Private source documents and hiring materials stay outside this repository.

No architectural disagreement with the source was found. Two unresolved differences matter: the document's shorter deadline versus the email window, and promised credits versus the web option's own-key wording. Neither is silently resolved here. The example premise is not assumed to be an assigned premise. Coding-assistant permission is unverified.

## Explain it without agents
A plan says what should happen. An accepted episode says what did happen. A draft says neither until a person accepts it. The system's job is to bring relevant accepted evidence to each writing step, keep human decisions, and pause rather than invent a way around uncertainty.

```text
premise -> proposed plan -> HUMAN approval -> bounded writing context
                                                  |
                                                  v
                    explicit new attempt <--- rejected draft
                                                  ^
                                                  |
                          draft -> HUMAN review --+
                                     |
                            accept final edited text
                                     |
                       one SQLite transaction:
              accepted text + memory source + event + next episode
                                     |
                              exit / reopen / read
```

## Framework discussion
| Choice | Benefit | Work/risk we still own |
| --- | --- | --- |
| Plain Python + SQLite | Few concepts, inspectable transitions and transactions; no separate database server[1] | Review gates, call reservations, invalidation and context policy must be implemented explicitly |
| LangGraph + durable persistence | Explicit graph orchestration, checkpoints and human interrupts; useful as branching grows[2][3] | Still needs a canonical domain ledger, stable thread IDs, durable checkpointer, idempotent operations and checkpoint/domain reconciliation |

Recommendation: plain Python for this bounded learning milestone. This is not a permanent framework decision. If later using LangGraph, keep generation separate from the review-interrupt node. Resuming an interrupt restarts its node; persist and identify results before any repeatable side effect.[2] Checkpoints are workflow state, not authority for story facts.

## Smallest data model
Now, one story per database:
- Story: premise, next eligible episode, history revision, durable fake-call policy.
- Plan: proposal ID, approval state, JSON intentions. Fake beats cover numbers 1-200 but are deliberately placeholders, not a credible narrative arc.
- Episode revision: ID, episode number, pending/accepted/rejected, proposed prose, accepted prose, parent history revision. Each retry gets a new ID.
- Review event: decision, target revision, note and timestamp. Unique acceptance target.
- Memory source: accepted episode revision and final text. This is a provenance seam, not a semantic fact extractor.
- Call record: operation ID, stage, episode, status, integer reserved/spent micro-USD, latency, provider label and creation time. Fake calls report no provider token usage.

Proposed next: scoped Direction records, structured Memory records (characters, knowledge, relationships, facts, events, threads), and Summary records with source-revision dependencies. Add only when the corresponding service and regression tests exist.

## Review state machine
Plan: PROPOSED -> APPROVED. No drafting without an approved plan.
Episode: PENDING -> ACCEPTED or REJECTED. Acceptance optionally supplies final edited prose. Rejection retains the draft for inspection, writes no canon and leaves the same episode eligible. Drafting again is explicit. Repeated acceptance of the same final text returns the same receipt. A different repeated acceptance is refused; historical editing needs a different operation.

Approval updates text, memory source, review event and cursor together. New process startup reads pending reviews rather than regenerating them. A reserved/uncertain call stops another attempt, rather than assuming no charge or silently repeating a potentially completed operation.

## Recommended memory and context policy
Durable disk storage is larger than each model context:
1. Compact approved global arc and current/nearby beats, as intentions.
2. Essential canon: identity, living/dead status, relationships, time and character knowledge, sourced only to accepted revisions.
3. Relevant open threads, especially due or overdue payoffs; retain dormant ones on disk.
4. Accepted episode/arc summaries with dependency provenance.
5. One or two recent accepted episodes when space allows.
6. Human directions with effective episode, scope and status, reconciled into future beats.

Retrieve by stable entity/thread IDs and episode windows first, not a vector service by default. Keep a manifest of included and omitted IDs. Essential material must fit; otherwise stop for explicit compaction. Provider-specific token counting comes later, before paid calls.

Implemented context is much smaller: premise, current fake beat and at most the last two accepted texts, bounded by a character count with omitted IDs recorded. It is NOT the episode-150 memory solution. The future layered policy above is the recommendation, not a completed feature.

## Feedback examples
- Accept episode 3: its final prose becomes evidence, next eligible episode becomes 4, and one acceptance receipt is saved.
- Reject episode 3: the rejected prose stays inspectable; canon and the cursor stay unchanged.
- Edit the final episode 3 prose to keep a character alive: the stored memory source and subsequent recent-text context use your edit, not the model's death scene. This alone does not reconcile the whole future plan.
- Direction 'keep the character alive': future design stores a scoped direction, proposes affected future-beat changes for review, and includes it in writing context. It must not retroactively invent survival in accepted history. Directions are not implemented in this milestone.

## What fails first near episode 150
Missing old facts and open threads outside the recent window; summary/extraction drift; characters knowing facts too early; repetition of forgotten beats; and retrieval selection under a strict context cap. Sending all prior episodes worsens spending/context growth, not authority. Fix with source-linked canon and thread ledgers, layered summaries, explicit retrieval manifests, evidence-based checks and late-stage fixtures. A critic or schema-valid JSON cannot guarantee truth. Fifteen real episodes cannot establish quality across 200.

## Episode-40 edits
Recommended first repair policy: preserve old revisions, accept revised episode 40 in a new history, invalidate 41 onward and their dependent memory/summaries, rebuild the valid prefix through 40, set next eligible to 41, and request approval before regeneration. Flag directions anchored to invalidated events. Even episode 40's own derived memory must be replaced. This over-invalidates safely. Dependency-aware selective repair is an optional later design, not promised now. This scaffold refuses changes to already accepted text instead of pretending to repair history.

## Spending and traceability
Now: zero-cost fake provider, no credentials read, no SDK/network adapter. Persist call counts, reservations, outcomes and wall-clock stage latency. A per-episode call limit covers every attempt that reaches the provider. Plan calls are accounted separately under episode zero. An integer reservation/settlement interface is exercised with artificial accounting units in tests only. Policies survive restart; unresolved reservations are not free.
Later: obtain provider/model/access/budget approval; persist conservative cost reservations before calls; disable unbounded SDK retries; bound tokens, requests, timeouts and revision attempts across writer/checker/memory stages. Retain uncertain charges until reconciled. Capture actual provider usage and dated pricing. Forecast 200-episode cost/time from observed complete-episode usage plus stated repair allowance, with separate human waiting time. No invented real price now.

## Test plan
This milestone: full fake cycle; approval gate; edited acceptance; rejection; repeated approval; atomic rollback; accepted-only bounded context; persistent call exhaustion and uncertainty; CLI happy/error paths; actual fresh-process pending-review and accepted-text reads. Synthetic fixture prose tests plumbing, not story quality.
Next phase: directions and beat changes; malformed/refused/truncated real outputs; historical invalidation; episode-150 retrieval fixture; token-aware budgets; two real intervention evidence chains; exit after 12 and continue to 15. Eventual episodes must be real 400-700-word outputs, not these fixtures.

## Discussion decisions
1. CLI-first now, or prioritize a later web review surface?
2. Continue with plain Python, or choose LangGraph deliberately as a learning investment?
3. Historical edits: refuse them initially, conservatively invalidate all descendants, or invest in dependency-aware repair?

## Primary technical references checked
Python sqlite3 documentation; LangGraph interrupts and persistence documentation. Reviewed on 2026-10-01. No provider selection or pricing research is inferred from them.

## Sources

[1] https://docs.python.org/3/library/sqlite3.html — Python sqlite3 documentation
[2] https://docs.langchain.com/oss/python/langgraph/interrupts — LangGraph interrupts
[3] https://docs.langchain.com/oss/python/langgraph/persistence — LangGraph persistence
