# V1 implementation plan and issue disposition

**2026-10-02 · Revision 3 (spec-fix).** Resolves the independent review `REVIEW-FINDINGS.md` (B1–B4, M1–M13, minors, ambiguous clauses) and implements the owner decisions of 2026-10-02 (`OWNER-DECISIONS.md`): one application ledger (B4), the 550/700/900 advisory length band (M10), and story-wide ordinals stamped at acceptance (M6). Traceability: `SPEC-FIX-LOG.md`. The earlier revision, written by the planner, reconciled: frozen revision-1 contracts (manifest `07-08-frozen-inputs`, eight hashes), the early Opus architecture review (`03-architecture-review/REPLY.md`), the parent's proposed disposition (`03-parent-architecture-disposition.md`, not clearance), the Sonnet backend trial receipt, two simulated persona critiques and the integration/test-gap audit. Source inspection only: no tests, application calls, browser runs or code changes were made for this plan.

**Status: backend implementation is on HOLD** until a separate Opus reviewer clears this exact revision of 01–04 and the revised prototype (§12). Nothing here promises runtime spend, prose quality or production readiness.

Companions: [01 workflow, journey J0–J10](01-WORKFLOW-CONTRACTS.md), [02 data and context](02-DATA-INGESTION-CONTEXT.md), [03 diagrams and UX](03-DIAGRAMS-AND-UX.md).

## 1. Cohort and journeys

**Cohort for v1:** one author, one local machine, one story per database, serial fiction written episode by episode, using a loopback browser desk. Three entry patterns share one desk:

| Entry | First session | Reaches the shared journey at |
| --- | --- | --- |
| Planner | Idea → discuss → adopt S1 → arc | J1 |
| Discovery writer | Pasted pages, questions, hand-written paragraph, reverse outline | J0 |
| Returning writer | Accepted E1–E3 with failed memory and a detached late result | J10, then J9 |

The single reference journey is 01 §3 (J0–J10 plus the voice-note side journey). Every test tracer (§10) and browser row (§8) names its J step.

**Author decisions required in J0–J7** (excluding writing, rewriting and chatting): adopt S1, adopt A1, commission once, revalidate E2 and resume after the J4/J5 pause, request one E2 repair, apply that repair candidate and resume after the J6 edit, accept once. The repair is two decisions because a repair is a candidate, never an automatic selection (01 §4 `request_repair`). Selection of each episode is not required in `provisional_chain` mode, and memory and review need no per-job confirmation inside the ceiling. That is the flow improvement over the frozen fixture, which needed one selection per episode plus demo advances. Every remaining decision is a real gate: an author change of basis, a finding, or acceptance.

**Revalidation semantics.** The system cannot judge whether downstream prose still fits a changed upstream episode. `revalidate` is therefore a free author attestation bound to both hashes, refused while a current serious finding binds the pair. A quiet review (review line or `request_job`) can check first; its finding is advisory evidence, and only `resolve_finding` or a prose change clears it.

## 2. Disposition matrix

Every early Opus HOLD finding, the five Sonnet decisions and the persona fixes, with where each is closed and how it is tested. "Spec" means the section that states the rule; "Test" names the RED test in §10.

### Early Opus review

| ID | Finding | Decision | Spec | Owner | Test |
| --- | --- | --- | --- | --- | --- |
| O1 | Two "selected" pointers; batch auto-selection undefined | One `v1_selection` row per episode artifact with `cas`; episode artifacts have no working head; commission slots map position → artifact only. Under `provisional_chain`, a complete result is selected only under the single import rule (02 §3 step 6: running, basis current, target `cas` unchanged). Late, partial, changed-basis or author-preempted results never auto-select. Any selection move of an unaccepted upstream flags downstream whose effective basis (02 §2) is not current. | 01 §2; 02 §2 "Identity and pointers", "Effective basis", §3 step 6 | `repository.py` (pointer), `studio/commission.py` (decision) | T2, T5, T6 |
| O2a | Story lock held through exchange (`authoring.py:193–210`) | Freeze, claim and import are separate short transactions; exchange runs on the runner thread with no SQLite transaction and outside `server.py:327` `write_lock`. | 02 §3 dispatch protocol | `studio/authoring.py`, `studio/runner.py`, `studio/server.py` | T5 |
| O2b | Changed-basis success discarded (`authoring.py:231–232`) | Always store output as revision + `v1_result`; eligibility decided after storage; detached results never trigger successors. | 02 §3 step 6 | `studio/authoring.py` | T5 |
| O2c | Any unresolved call bricks the project; no resolution API | Reserve refuses only on `uncertain` rows. Add `resolve_uncertain` (spent = max(reserved, reported), never lowered) and `release_undispatched` (only `dispatched=0`). | 02 §3 ledger states | `budget.py` | T4 |
| O2d | No batch envelope schema; aggregate versus child holds | `ledger_commission` row is a ceiling; children carry `commission_id`; reserve checks Σ(spent+reserved) for that commission + amount ≤ ceiling and application remaining = cap − Σreserved − Σspent over every project in the one ledger. The ceiling is never subtracted. | 02 §3; §5 ledger DDL | `budget.py` | T4 |
| O2e | `TTL_SECONDS=120` would pause every batch job | TTL applies only to human-confirmed single `request_job` quotes. Commission children are quoted immediately before reservation; a price or bound change from the commission's frozen route pauses with reason `route_changed`. | 01 §2; §4 | `studio/authoring.py` | T5 |
| O3 | Rewrite anchoring unimplementable; no lineage producer | Paragraph blocks; client-sent block IDs on save; hash-unique mapping for ID-less saves; repeated blocks unmapped. Any edit to a target or consumed-context block is overlap. Undo compares stored after-image; preservation guaranteed only for other blocks. | 02 §2 "Block identity producer", "Ranges"; 03 §4 | `studio/rewrite.py`, `repository.py` | T7, T8 |
| O4 | Fallback too broad; leaks later knowledge | Context is clipped at the operation's narrative boundary; later passages only as `protected_outcome`. Fallback applies only to state-asserting recipes. Polish uses local context, discloses no story state and refuses story-change reasons. | 02 §4 recipes | `context.py` | T11, T12 |
| O5a | Promotion/review have no spending authority | Outbox starts `awaiting_authority`; becomes `authorized` by the commission's memory/review line or a single `request_job`. Until then continuation uses exact-text fallback. | 01 §2; 02 §2 outbox | `memory.py`, `studio/commission.py` | T10, T11 |
| O5b | Review tool loop not qualified | v1 review is one call with a server-assembled packet; each included or omitted item logged in `v1_tool_read`. Adaptive tool loop excluded (§11). | 02 §4 review packet | `studio/review.py` | T13 |
| O5c | Late findings lack a version rule | A finding blocks only while its target hash is a current selection or canon; otherwise "about an older version". A late serious finding on accepted text opens impact, pauses continuation, never unaccepts. | 02 §4 | `studio/review.py`, `context.py` | T13 |
| O6 | Canon store undecided; 400–700 hard gate | `v1_canon` sole writer after cutover; legacy reads/exports through adapter; legacy mutation refuses migrated stories; for v1 stories word count is advisory with band 550/700/900 (owner decision, 2026-10-02); the legacy 400–700 refusal at `repository.py:183` is unchanged for unmigrated stories. | 02 §1, §5; §6 | `repository.py`, `migrations.py` | T9, T15 |
| O7 | Claims lack about/stance/exposure | `about_claim_id`, `speaker`, `holder`, `stance`, `exposure`, `narrative_point`, `world_validity`, `reader_reveal_point`. | 02 §2 memory | `memory.py` | T12 |
| O8 | Chat → feedback must be explicit | `mark_feedback` on a message is the only producer; models never extract feedback. | 02 §2 conversation | `studio/store.py` | T3 |
| O9 | Feedback added mid-batch | Commission freezes its feedback set. New feedback is labelled "not used by jobs already sent". `apply=remaining` sets `pause_requested=feedback`, which takes effect at the next checkpoint (02 §3 "Pause requests"); resume freezes later jobs with the feedback within the same ceiling and route, without a new spending decision. | 01 J4; 02 §3; 03 §3 | `studio/commission.py` | T6 |
| O10 | Pasted pages as candidates | Without a target, pages become a `fragment` (exploration). With an episode target they become a revision (`origin=imported`), selected only on explicit `select: true`, acceptable under the same prefix contract; a revision with no job and no parent binds its effective basis at save time. | 01 J0; 02 §2, §4 step 1 | `repository.py` | T9 |
| O11 | Style deferred by review; required by Ayan | Kept in slice in manual form: author-chosen evidence with before/after, propose/edit/adopt/retire/revert, withdrawal flags note `needs_reaffirm`. No automated learning. | 01 side journey; 02 §2 | `studio/store.py` | T14 |

### Sonnet backend trial (five unresolved decisions)

| ID | Decision needed | Closure | Spec | Test |
| --- | --- | --- | --- | --- |
| S1 | Restart classification of in-flight calls | Recovery table keyed by story job state × ledger row, scoped to the runner's own `story_id`; `claiming` or `sent` with `dispatched=1 + no receipt → uncertain`, never resent; `dispatched=0 → release + not_sent`; orphan rows and legacy rows have their own rows. Runs before any dispatch on server start. | 02 §3 recovery table | T5 |
| S2 | Stable ledger identity | One application ledger per user (owner decision B4); `project_id`/`story_id` row columns; cap fixed by CHECK; file created only by `init_ledger` or `migrate --ledger`; `create_project` registers a row; fail closed when missing. | 02 §3 ledger authority | T4 |
| S3 | Separate known, conservative and individually known charges | Ledger snapshot reports `spent_verified`, `spent_conservative`, `reserved`, and per-row `reported_charge`; desk shows them separately. | §4 `ledger_state` DTO | T4 |
| S4 | Batch envelope schema, CAS, atomic child limits | `ledger_commission` with fingerprint; child reservation and ceiling check in one `BEGIN IMMEDIATE`. | §5 | T4 |
| S5 | Deterministic block identity on whole-text save | Client IDs plus hash-unique fallback; ambiguity unmapped. | 02 §2 | T7 |

### Persona critiques (opinions; observed facts separated in 03 §8)

| ID | Opinion | Disposition | Where |
| --- | --- | --- | --- |
| P1 | Authorize provisional progression for the arc | Adopted as `provisional_chain` | 01 §2; 03 §6.1 |
| P2 | Repair scope label contradicted whole-episode candidate | Candidate scope, reason and basis shown together | 03 §6.2 |
| P3 | Acceptance should show prose | Inline prose/diff and changed-since-selected | 03 §6.3 |
| P4 | Duplicate chat/feedback entries; phone composer far away | "Use for next" on a message; fixed phone control | 03 §6.5 |
| P5 | Undo status stale, recovery collapsed | Undo beside edit, "undone" state, sections stay open | 03 §6.4, §6.9 |
| D1 | Readings must name exact words and boundary | Claim span links; planned reveals separated | 03 §6.7; 02 §2 |
| D2 | Reversible editing beside the edit | Same as P5 | 03 §6.4 |
| D3 | Lead with the next decision and its words | One dominant action; compared words first on phone | 03 §6, §6.10 |
| D4 | Style evidence honesty | Evidence types and author choice | 03 §6.8 |
| D5 | Protect unsent composer | Append or replace-with-undo | 03 §6.6 |

### Integration audit proposals, evaluated

| Proposal | Verdict |
| --- | --- |
| `repository.py` + explicit `migrations.py` own revisions, pointers, sole canon writer | Accept |
| `studio/store.py` owns conversation, feedback, direction, style | Accept |
| `service.py` + focused `context.py` own recipes | Accept; `service._operation` stays fixture-only |
| `studio/authoring.py` owns saved jobs, batch checkpoint, pause/resume | **Modify:** `authoring.py` keeps single-job freeze/quote/claim/import; new `studio/commission.py` owns scheduling and pause rules; new `studio/runner.py` owns the thread and recovery. Keeps the scheduler testable without threads. |
| Initially serialize all paid dispatches | **Modify:** chain jobs are sequential by dependency; up to `MAX_IN_FLIGHT = 2` paid calls project-wide so a chat reply or memory update can run while a draft is in flight. Cap safety comes from counting every reservation, not from serialization. |
| Server-assembled review packet; tool loop deferred | Accept |
| Historical staging of at most one episode | **Modify:** one change set may contain several accepted episodes (J10 needs E1+E2); still no suffix removal or branching. |

### Independent review: ambiguous clauses resolved (revision 3)

One reading per clause, stated where the rule lives. The full finding-by-finding log is `SPEC-FIX-LOG.md`.

| Clause | Reading chosen | Why | Stated in |
| --- | --- | --- | --- |
| Overflow threshold, 100% vs 85% | Mandatory items block above **100%** of qualified `max_input_tokens`; 85% caps optional fill only | The bytes + 1,024 estimate already overcounts; 85% for mandatory items ends exact-text fallback early for no safety gain | 02 §4; §7 |
| Memory line lifetime | Valid after drafting completes, for sources accepted from the commission's slots via `accept_prefix`, until ceiling or stop. Change-set tasks wait `awaiting_authority` | J8 needs memory after J7, which follows completion; a change set weeks later is a new author action and must not inherit spend authority | 01 §2 |
| New price, route or ceiling | `resume_commission` carries `accept_quote` (price) or `new_ceiling_micro`; a different route ID needs a new commission | Price and ceiling are spending numbers the author can re-decide in place; the route is the commission's identity | 01 §2; §4 `resume_commission` |
| `adopt` "conflicts with accepted reality" | One deterministic check: an arc revision must keep already-accepted episodes as its first *k* slots (`accepted_conflict`); everything else advisory | Only slot structure is checkable without judging meaning | 01 §4 |
| "Pauses at the next boundary" (J4) | `pause_requested` while a draft is `claiming` or `sent`, effective at the checkpoint after that draft imports; with no draft sent, the pause is immediate and a frozen job becomes `not_sent` | Lets an already-paid draft be selected while never sending a new one | 02 §3 "Pause requests" |
| "Frozen basis equals current pointers" | Every `v1_predecessor` row is current (selection for unaccepted, canon for accepted) plus target `cas`. `canon_seq` is **not** included | Accepting a prefix does not change any revision, so it must not pause a commission; a change set changes canon revisions and does | 02 §3 step 6 |
| `MAX_IN_FLIGHT = 2` counts | All `reserved` rows in the application ledger, dispatched or not | Counting only dispatched rows lets more than two reserve and race to claim; M2 makes undispatched rows short-lived | 02 §3 step 3 |
| Undo of a provisional selection | `revert_event` on the select event restores the before value; a first selection restores `revision_id NULL` | `v1_selection.revision_id` is now nullable with `cas` kept, so "nothing selected" is a real state | 01 §4 "Reversibility"; 02 §2 |
| `v1_artifact.ordinal` vs `v1_canon.episode_ordinal` | Arc-relative and story-wide respectively; the story-wide value of an artifact lives in `v1_story_position`, stamped at acceptance | Owner/parent decision M6; neither load-bearing column is overloaded | 02 §2 "Ordinals" |
| O10 imported pages before any arc (J0) | No target: a `fragment`. Episode target: an episode revision, selected only with explicit `select: true` | Keeps J0 exploratory and keeps every pointer move an author action | 02 §4 step 1 |

## 3. Module ownership and package decision

Keep the existing stack: the Python version pinned in `.python-version` (current code uses `sqlite3.LEGACY_TRANSACTION_CONTROL`, which needs 3.12 or later), stdlib `sqlite3`, `threading`, `hashlib`, `json`, `unicodedata`, `unittest`, and the static browser desk. `pyproject.toml` declares no dependencies and v1 adds none. No framework, ORM, task queue or diff library is needed for block-granular rewrites.

| Module | Owns | Must not |
| --- | --- | --- |
| `serial_story/migrations.py` (new) | Schema version detection, explicit story and ledger migrations, pre-migration copy | Run on open |
| `serial_story/repository.py` | v1 artifacts, revisions, sources, blocks, lineage, selection, effective basis, story positions, canon, acceptance, change sets, events, operation replay, impact rows | Call providers; run DDL when opening a database that contains `v1_meta` (legacy constructors unchanged until cutover) |
| `serial_story/studio/store.py` | Threads, messages, feedback, consumption, skeleton/arc/style revisions and adoption | Write canon |
| `serial_story/context.py` (new) | Recipes, boundary clipping, indexed/exact/blocked decision, budget accounting of items | Reserve money |
| `serial_story/studio/authoring.py` | Single-job freeze, quote, claim, import, eligibility | Hold a story transaction during exchange |
| `serial_story/studio/commission.py` (new) | Commission CAS, next-job choice, pause/resume/stop rules, provisional selection | Network I/O |
| `serial_story/studio/runner.py` (new) | Runner thread, runner lease, recovery on start, exchange call | Accept prose |
| `serial_story/budget.py` | The one application ledger (projects as rows), commission ceiling, resolution, release | Live in a code-tree path; create a ledger file per project; touch another story's rows during recovery |
| `serial_story/studio/rewrite.py` (new) | Range validation, candidates, apply/undo/redo checks | Write canon |
| `serial_story/memory.py` | Outbox leases, claims, snapshots, legacy fact adapter | Write prose |
| `serial_story/studio/review.py` (new) | Packet assembly, read receipts, findings | Any write outside findings/read receipts |
| `serial_story/studio/server.py` | Fixed `/api/v1/*` routes, origin/token guards, short handlers | Wrap exchanges in `write_lock` |
| `serial_story/review/snapshot.py`, exports | Read through canonical adapter | Initialize or mutate |

## 4. Commands, DTOs and events

All mutations: `POST /api/v1/<command>`, body `{operation_id, story_id, expected, payload}`. `operation_id` is 1–80 characters. The server computes a canonical fingerprint (sorted-key JSON SHA-256). Same ID and fingerprint returns the stored receipt with HTTP 200; same ID with another fingerprint returns 409 `operation_reused`. Reads: `GET /api/v1/state`, `/api/v1/artifact/<id>`, `/api/v1/compare/<candidate>`, `/api/v1/ledger`.

**Error codes** (409 for concurrency, 400 for refusals, 503 for gated runtime):

| Code | Meaning |
| --- | --- |
| `stale_pointer` | Expected `cas` differs; body carries current value |
| `operation_reused` | ID belongs to a different request |
| `basis_changed` | Frozen predecessors or direction no longer current |
| `invalid_range` / `ambiguous_block` | Offsets, text mismatch, grapheme boundary, unmapped block |
| `locked_span` | Range or replacement touches a lock |
| `overlap` | Target or consumed-context block changed; body carries before/AI/now |
| `context_overflow` | Mandatory items exceed qualified input bound; lists items |
| `open_conflict` | Serious finding or impact before the boundary |
| `prefix_invalid` | Hole, unselected, stale or missing effective basis (`reason: basis_stale` / `basis_missing`), `origin=fixture`, or open finding in an accept group |
| `accepted_conflict` | Arc adoption would drop or reorder already-accepted episodes (01 §4 `adopt`) |
| `resume_needs_decision` | Resume after `route_changed` or `ceiling_exceeded` without `accept_quote` / `new_ceiling_micro` |
| `ceiling_exceeded`, `cap_exceeded`, `accounting_uncertain`, `too_many_in_flight` | Ledger refusals |
| `route_unqualified` | 503; no qualification supplier or bound mismatch |

**Key DTOs** (abbreviated; every field required unless marked optional):

```json
{"command":"commission_arc","expected":{"skeleton_adoption":"ad-3","arc_adoption":"ad-4","canon_seq":0},
 "payload":{"slots":[1,3],"route_id":"r-1","ceiling_micro":120000,
            "progression":"provisional_chain","include":["memory"],"feedback_ids":["fb-2"]}}
```
Preconditions: adopted S and A equal expected; slots exist in arc and are unaccepted; route qualified; ceiling ≤ application remaining; no `uncertain` row in the application ledger; first job's context not blocked. Writes commission, ledger commission row (ledger txn after story txn; recovery treats a story commission without ledger row as `paused: ledger_missing`), frozen first job with `target_selection_cas`. Replay returns the commission receipt.

```json
{"command":"resume_commission","expected":{"commission_cas":7},
 "payload":{"commission_id":"cm-1","new_ceiling_micro":null,"accept_quote":null}}
```
Preconditions: status `paused`; no open impact or current serious finding before the next slot; for `route_changed`, `accept_quote` equals the current quote of the same route ID; for `ceiling_exceeded`, `new_ceiling_micro` ≥ used and ≤ used + application remaining (it updates the `ledger_commission` row in the ledger txn after the story txn). Writes `status=running`, a new frozen job (new `ledger_operation_id`) for the next slot. `pause_commission` (`expected.commission_cas`) sets `pause_requested=author` when a draft job is `claiming` or `sent`, otherwise `status=paused` at once.

```json
{"command":"save_revision","expected":{"selection_cas":4},
 "payload":{"artifact_id":"ep-1","base_revision_id":"rv-11","blocks":[{"block_id":"b0","text":"…"},{"block_id":null,"text":"…"}]}}
```
Writes revision, source, blocks, lineage; writes the new revision's effective-basis rows (`inherited` from the base revision, or `save_binding` when there is no base, 02 §2); moves selection if base was selected; if the artifact is unaccepted and its selection moved, opens a `v1_impact` (`upstream_selection`) on every later selected episode whose effective basis for this artifact is not the new revision, and pauses any running commission with a frozen or in-flight job whose `v1_predecessor` row for this artifact is no longer current. If the artifact is accepted, the save only moves the working pointer: no impact, no pause (impacts open at `commit_change_set`).

```json
{"command":"apply_candidate","expected":{"selection_cas":5},
 "payload":{"candidate_id":"cd-7"}}
```
Checks: candidate open; current selected revision maps every `v1_affected_block` to an identical hash; no lock intersects; consumed cross-episode context hashes unchanged. Writes revision and event with before/after images. Refusal `overlap` returns three texts; the author may instead save the candidate text manually, which records a human edit with `origin_ref=cd-7` and **inherits** the base revision's effective basis (a manual save never inherits a repair job's basis, because the author did not take the candidate as produced). The applied revision's effective basis is the candidate job's `v1_predecessor` rows for `story_rewrite`/`repair`, and inherited from the base revision for `polish`. A `repair` candidate's affected blocks are every block of its base revision, and its consumed context is every upstream revision it froze.

```json
{"command":"accept_prefix","expected":{"canon_seq":0},
 "payload":{"episodes":[{"artifact_id":"ep-1","revision_id":"rv-15","sha256":"…"},
                        {"artifact_id":"ep-2","revision_id":"rv-18","sha256":"…"}],
            "finding_dispositions":[{"finding_id":"fd-2","resolution_id":"rs-1"}]}}
```
Checks: the listed episodes are, in order, the next unaccepted episodes in story order (02 §2 "Ordinals"), so the *i*-th gets `story_ordinal = canon cursor + i`; each revision is the current selection with that hash and not `origin=fixture`; for every listed episode *D* and every earlier episode *U* (accepted, or listed before *D*), `basis(D, U)` (02 §2 "Effective basis") equals *U*'s canon revision or listed revision, and a missing row refuses with `basis_missing`; no open impact and no open serious finding on any listed hash. Word counts outside the v1 band (floor 550, ceiling 900, target 700) add a `length_warning` per episode to the receipt and never refuse; the payload may carry an optional `length_notes` map `{artifact_id: reason}` that is stored with the acceptance, and the desk always asks for that reason. Writes `v1_story_position`, canon, acceptance and outbox in one transaction; any failure, including the last outbox row, rolls back all.

```json
{"command":"resolve_uncertain","operation_id":"op-41","story_id":"st-1",
 "expected":{"row_status":"uncertain","row_version":3},
 "payload":{"ledger_operation_id":"op-9","reported_charge":null,"reason":"provider receipt unavailable"}}
```
Ledger only, one `BEGIN IMMEDIATE`. Replay by `operation_id` returns the stored resolution; a stale `row_version` or a row no longer `uncertain` refuses with `stale_pointer`. Sets `resolved_conservative`; spent = max(reserved, reported_charge); reserved = 0; writes resolution JSON. Never lowers spent; terminal. v1 has no receipt lookup, so no later receipt arrives. `release_undispatched` uses the same envelope and refuses any row with `dispatched=1`.

**`ledger_state` read DTO:** `cap`, `spent_verified`, `spent_conservative`, `reserved`, `remaining`, `in_flight`, `uncertain_count`, and per commission `ceiling`, `used`.

**Events** (`v1_event.action`): `ingest`, `save`, `select`, `adopt`, `mark_feedback`, `retire_feedback`, `commission_start`, `commission_pause_requested`, `commission_pause`, `commission_resume`, `commission_stop`, `job_frozen`, `result_imported`, `result_detached`, `rewrite_apply`, `revert`, `redo`, `lock`, `unlock`, `keep`, `discard`, `revalidate`, `revalidate_withdraw`, `repair_apply`, `accept`, `change_stage`, `change_commit`, `change_discard`, `interpret`, `finding_open`, `finding_ack`, `finding_resolve`, `style_adopt`, `style_retire`, `style_revert`, `evidence_withdraw`, `impact_open`, `impact_close`. Actor is `author` or `commission:<id>`. `revert_event` accepts the event kinds listed as reversible in 01 §4 "Reversibility" and refuses every other kind.

**Pause rules** are 02 §3 "Gates by job line", "Pause requests" and step 6 "The single import-selection rule"; `commission.py` checks them inside the claim transaction (status and `pause_requested`, currency of every `v1_predecessor` row, `target_selection_cas`, open impact before the slot, open serious finding, context decision, route change) and again at import. Summary: an author or feedback pause is a request that lets an already-sent draft import and be selected, then stops the chain at the checkpoint; every gate pause takes effect at once and detaches the in-flight draft. A claim-time refusal releases the job's undispatched reservation in the same runner step. Stop marks unsent jobs `not_sent`, releases their undispatched reservations, and detaches any in-flight draft with `commission_stopped`; memory and review lines end with it.

## 5. Schema creation order

Story database, one migration step `v1_0001`, inside one transaction: `v1_meta`, `v1_artifact`, `v1_revision`, `v1_source`, `v1_block`, `v1_block_lineage`, `v1_lock`, `v1_selection`, `v1_story_position`, `v1_basis`, `v1_adoption`, `v1_governing`, `v1_thread`, `v1_message`, `v1_feedback`, `v1_context`, `v1_context_item`, `v1_commission`, `v1_slot`, `v1_job`, `v1_predecessor`, `v1_result`, `v1_consumption`, `v1_rewrite`, `v1_rewrite_range`, `v1_affected_block`, `v1_event`, `v1_operation`, `v1_impact`, `v1_canon`, `v1_acceptance`, `v1_change_set`, `v1_outbox`, `v1_snapshot`, `v1_claim`, `v1_claim_status`, `v1_claim_evidence`, `v1_review`, `v1_finding`, `v1_tool_read`, `v1_style_evidence`, `v1_runner_lease`, `v1_legacy_map`. Columns and checks: 02 §2. Indexes: `v1_source(revision_id, sha256)`, `v1_block(source_id, ordinal)`, `v1_selection(revision_id)`, `v1_predecessor(revision_id)` (dependency lookup on save), `v1_basis(upstream_artifact_id, upstream_revision_id)` and `v1_basis(downstream_revision_id)` (flagging and accept checks), `v1_context_item(claim_id)` and `v1_context_item(source_id)` (claim dependencies), `v1_job(commission_id, state)`, `v1_outbox(state, lease_expires)`, `v1_claim(kind, holder, narrative_point)`, `v1_claim(prior_claim_id)`, `v1_claim_status(claim_id, seq)`, `v1_claim_evidence(source_id)`, `v1_event(seq)`, `v1_message(thread_id, seq)`, `v1_impact(state)`.

Triggers enforce what CHECK cannot: revision, claim and basis rows are never updated or deleted (except `v1_basis.withdrawn_by_event`, settable once on `revalidate` rows); `v1_selection.revision_id`, when not NULL, belongs to its artifact; `v1_story_position` rows are never updated or deleted; `v1_canon.episode_ordinal` equals the artifact's `story_ordinal`; `v1_canon` changes only when an `accept` or `change_commit` event with the same operation exists in the transaction (checked by the writer, plus a trigger refusing updates without a matching `acceptance_id`).

Application ledger database (one per user, 02 §3), created by `init_ledger` or `migrate --ledger`, migration `ledger_0001`: `ledger_meta(schema_version, cap INTEGER NOT NULL CHECK (cap = 1000000))` (single row); `ledger_project(project_id PK, created_at)` written by `create_project`; rebuild `merge_calls` with `status IN ('reserved','succeeded','uncertain','resolved_conservative','released')`, `project_id` and `story_id` (NULL only for legacy-imported rows), `commission_id`, `resolution`, `row_version`; `ledger_commission(commission_id PK, ceiling_micro CHECK ≥ 0, fingerprint, status, created_at)`; `merge_preflights` moved here from the `authoring.py:49` property.

## 6. Migration, adapter and cutover

1. `migrate --story <path>` refuses if the story is open by a server lease. It writes `<name>.pre-v1.<sha8>.db` (refuse if present with different content), then runs `v1_0001` and the backfill in one transaction.
2. Backfill: each accepted legacy episode becomes an episode artifact, revision (`origin=imported`, reason `legacy`), source and blocks, canon row and `v1_legacy_map` row. Verify `accepted_text == memory_sources.final_text` byte for byte first; any mismatch aborts with the episode IDs.
3. Pending and rejected legacy rows become unselected revisions; plans become historical arc revisions with no adoption; facts become `legacy_unclassified` claims; receipts and feedback versions are copied with their original IDs mapped. `history_start` is set to the migration time.
4. Ledger: `migrate --ledger --project <project_id>` creates the application ledger if it does not exist, imports `local/merge-project-ledger.db` rows with that `project_id` and `story_id` NULL, records the source SHA-256, leaves the source file untouched and refuses a second import of a different file. In the same transaction it classifies legacy rows once: `reserved, dispatched=1 → uncertain` (liability kept; blocks reservations until resolved), `reserved, dispatched=0 → released` with reason `legacy_unsent`. Runners never touch legacy rows afterwards (02 §3 recovery).
5. Cutover: `SQLiteRepository` and studio routes detect `v1_meta`; legacy `accept`, `save_draft`, `/api/accept`, `/api/draft/edit`, `/api/plan/save`, `/api/memory/fact` and CLI acceptance refuse with "This story uses the new desk." The legacy paid `confirm` refuses for every story after cutover.
6. Canonical adapter: `accepted()`, `read(n)`, studio state and `review/snapshot.py` read `v1_canon` for migrated stories without writing. Export output for a migrated story must be byte-identical to its pre-migration export.
7. Opening never mutates **a database that already contains `v1_meta` (story) or `ledger_meta` (application ledger)**: such a database opens with `PRAGMA query_only` for read paths and runs no DDL. Legacy constructors (`SQLiteRepository.__init__` at `repository.py:70–73`, `StudioStore.__init__` at `studio/store.py:76–87`, `SQLiteBudget.__init__` at `budget.py:50–59`, `ProjectMergeLedger` at `budget.py:146–163`) keep creating and altering legacy schema exactly as today until cutover, because the legacy suite and the legacy CLI create databases by opening them. A legacy database is never upgraded implicitly; v1 schema arrives only through `migrate`, `create_project` (new story database) or `init_ledger`.

## 7. Context budgets, extraction and retrieval

| Recipe | Mandatory budget | Optional fill | Output bound |
| --- | --- | --- | --- |
| `converse` | Target + last 12 selected messages | Governing direction summary | Route qualified |
| `arc_planning` | Skeleton, purpose/end, accepted context to boundary | Feedback, open promises | Route qualified |
| `sequential_draft` | Skeleton, slot intention, accepted context to boundary, selected predecessors untruncated, locks, kept passages | Style notes, feedback, neighbour summaries | Route qualified |
| `polish_rewrite` | Target blocks, ±1 neighbour, locks | Style notes | ≤ 2 × target length |
| `story_rewrite` / `repair` | Full target, change request, prefix context, protected outcomes | Feedback | Route qualified |
| `promotion` | Exact final source, claims to boundary | None | Claim JSON schema |
| `review` | Packet (02 §4) | None | Finding JSON schema |

All mandatory items must fit within 100% of the qualified `max_input_tokens` under the existing UTF-8 bytes + 1,024 strategy; otherwise `context_overflow` before reservation. Optional items fill only up to 85% (02 §4). The current 18,000/48,000-character heuristics are retired as limits for v1 recipes: v1 calls skip the character check in `MergeRuntime.validate` (`merge.py:298`) and apply its token check against the route's qualified `max_input_tokens` instead of the fixed 200,000 (`merge.py:302`). Without this change exact-text fallback would hit the 48,000-character refusal around episodes 10–12. The legacy `confirm` path keeps both checks.

**Extraction recipe (`promotion`, version 1):** input is the exact source with block IDs and the prior claims to its boundary. Output is a JSON list of claims, each citing `block_id`, `start`, `end` and the quoted text. Import rejects any claim whose quote does not equal the cited range, whose `kind` needs a missing `speaker`/`holder`, or whose `narrative_point` is outside the source. Rejected items are recorded, not repaired. A complete import of every canon source through ordinal *k* creates a `complete` snapshot.

**Retrieval** for indexed mode is SQL, not embeddings: claims where `narrative_point < boundary` and derived standing (02 §2) is `accepted_derived` or `legacy_unclassified` (never `superseded`, `rejected` or `exploratory`), filtered by holder for character knowledge and by `reader_reveal_point < boundary` for reader knowledge.

## 8. Browser acceptance matrix

Evidence needed for each cell: harness exit 0 with `success: true` and a finish timestamp, named screenshots, storage or state assertions, and empty console-error and failed-request arrays. Video only where the run finishes. A timed-out run is recorded as incomplete, never as a pass. Long journeys are split into scenarios under 60 operations so desktop runs can finish within the harness timeout.

| Journey | 1440×900 | 768×1024 | 390×844 reduced motion | Keyboard only | Key assertion |
| --- | --- | --- | --- | --- | --- |
| J0 Discovery | required | required | required | required | Nothing adopted or accepted; composer kept; suggestion append/replace |
| J1 Direction | required | — | required | required | S2 saved, S1 governs; adopt by exact revision |
| J2 Arc 3/5/6 | required | — | required | — | Route text changes with count; no padding |
| J3 Commission | required | required | required | — | One commission decision; provisional selections recorded as commission events; no acceptance |
| J4 Conversation during work | required | — | required | — | "Not used by E2"; apply-to-remaining pauses then resumes |
| J5 Rewrite/undo | required | — | required | required | Unrelated block survives undo; overlap shows three texts; "undone" status |
| J6 Upstream impact | required | required | required | — | Late E3 detached with charge; E2 repaired only; E3 redrafted from current |
| J7 Accept prefix | required | — | required | required | Prose visible; changed-since-selected marks; group refusal on hole |
| J8 Memory | required | — | required | — | Exact spans; planned reveals absent; correction leaves prose |
| J9 Continue | required | — | required | — | Indexed, exact-text and blocked outcomes |
| J10 Return | required | required | required | — | Old canon during staging; commit flags E3 |
| Voice note | required | — | required | — | Evidence types shown; withdrawal flag survives retirement undo |

Current honest status (frozen fixture `6D599039…`): only reduced-motion 390×844 runs completed (planner R3; discovery R and S). Desktop video runs timed out; one phone run stopped on a hidden control. Simulated personas are not human research; worker success is not UX clearance. The design audit (`evals/design-audit.md`, Premium Test) has not been run on pixels for any revision.

## 9. Live-route qualification and spend authority

These are separate gates after backend review, each needing its own explicit authority from Ayan in that session:

1. **Qualification (no spend):** install a qualification supplier recording verified input/output bounds, fee, pricing unit and reasoning setting for one Sonnet drafting route and one Opus planning/review route, matching the checks in `authoring.py` `quote`. Metadata alone is not qualification.
2. **Ledger cutover (no spend):** migrate the legacy ledger into the one application ledger; confirm remaining allowance with existing spent, reserved and uncertain rows preserved.
3. **Spend authority:** a named ceiling (micro-USD) for one bounded live check, for example one `converse` and one single-episode `request_job`, no commission, no retry. Results recorded with receipts; prose quality judged by a human, not by the run's success.

No feasibility claim is made that J0–J10 fits within USD 1.

## 10. Test-first steps

`unittest.TestCase`, temporary directories, `addCleanup`, fake clock, failure triggers and `threading.Barrier` for races. No real provider calls. **Fakes:** one shared `tests/v1_fakes.py` provides `FakeTransport`, a scripted exchange keyed by recipe (`converse`, `sequential_draft`, `polish_rewrite`, `story_rewrite`, `repair`, `promotion`, `review`). Each script entry gives the output text or JSON (claim JSON with exact block ranges for promotion, finding JSON for review), finish reason, accounting, and an optional barrier or raise point. The existing `FakeProvider` (`provider.py:13–38`, `plan`/`draft` only) stays for legacy tests. Fake output is stored with `origin=generated`; `origin=fixture` is reserved for the static fixture and cannot be accepted. Each step: write the RED test, observe it fail for the stated reason, implement the smallest change, observe GREEN, run the whole existing suite. Existing tests are baseline evidence; any that encode replaced behavior are named and changed deliberately (end of section).

| Step | J | RED test (file) | Owner | GREEN means |
| --- | --- | --- | --- | --- |
| T1 | — | `test_v1_open_does_not_mutate_v1_bytes_and_never_upgrades_legacy` (`tests/test_v1_core.py`) | `migrations.py`, `repository.py` | Opening a story with `v1_meta` or a ledger with `ledger_meta` leaves file bytes identical; opening a legacy database through the v1 entry point adds no `v1_` table; v1 schema only via `migrate`, `create_project`, `init_ledger`. Legacy constructors are not asserted byte-stable (they still create legacy schema) |
| T2 | J0 | `test_save_with_block_ids_moves_single_selection_and_records_lineage` (`test_v1_core.py`) | `repository.py` | One selection row; same/edited/inserted/deleted lineage; stale `cas` returns `stale_pointer`; replay returns receipt; changed payload `operation_reused` |
| T3 | J1, J2 | `test_working_chat_does_not_replace_adopted_direction_and_arc_survives_restart` (`test_v1_direction.py`) | `studio/store.py` | S2 saved, S1 governs after reopen; adopt by exact hash; 3 intentions create 3 artifacts; competing adopt from same head: one wins; feedback only via `mark_feedback` |
| T4 | — | `test_commission_ceiling_and_children_share_cap_without_double_hold` (`test_v1_ledger.py`) | `budget.py` | Ceiling not subtracted; Σ children ≤ ceiling; `uncertain` blocks new reservations; `resolve_uncertain` never lowers spent and preserves overcharge; `release_undispatched` refuses `dispatched=1`; missing application ledger fails closed; copied code tree resolves same ledger; two `create_project` calls create no ledger file and share one remaining allowance (second project's reservation fails once the first spent the cap); `UPDATE ledger_meta SET cap=2000000` fails the CHECK; two connections racing a last-fitting reservation: one succeeds; `test_two_in_flight_within_cap_third_refused`: two small reservations succeed, the third refuses `too_many_in_flight` with allowance left |
| T5 | J3, J6 | `test_upstream_edit_during_exchange_detaches_charged_output_and_pauses` (`test_v1_commission.py`) | `authoring.py`, `commission.py`, `runner.py` | Another connection saves E1 while the fake exchange waits on a barrier; E2 output stored, charged, detached; E3 not frozen; reopen preserves all; crash after ledger claim yields `uncertain` with zero further dispatches; crash before claim yields `not_sent` and released reservation; settled receipt imports exactly once after restart. Boundary is deterministic: an edit committed before the story `claiming` write gives zero dispatches and a released reservation; an edit committed after it gives one dispatch and a detached result (never "flaky by design"). `author_selected`: while E2's job is in flight the author selects another E2 alternative; the import is stored detached with `author_selected` and the author's selection stays. A partial fake output (finish reason `length`) is stored as a `partial` detached revision. Recovery: a ledger row of another `story_id` is untouched; an orphan `dispatched=0` row of this story is released, an orphan `dispatched=1` row becomes `uncertain` |
| T6 | J3, J4 | `test_provisional_chain_selects_current_results_sequentially_and_feedback_pauses_at_boundary` (`test_v1_commission.py`) | `commission.py` | E2 predecessors equal E1's selected revision ID/hash; never two chain jobs in flight; `review_each` waits for `select`; new feedback labelled not consumed; apply-to-remaining while E2 is `sent` leaves status `running` with `pause_requested=feedback`, E2 imports **selected**, the commission then pauses with no E3 job, and resume freezes E3 with the feedback under the same ceiling; `pause_commission` with a frozen, unclaimed job yields `not_sent`, a released reservation and a new job on resume; route price change pauses `route_changed`, resume without `accept_quote` refuses `resume_needs_decision`; during a basis pause a review-line job still dispatches and a draft job does not |
| T7 | J5 | `test_block_rewrite_undo_preserves_unrelated_block_and_refuses_overlap` (`test_v1_rewrite.py`) | `rewrite.py` | Candidate changes nothing; apply changes only target block; unrelated block edit survives undo after reopen; edit in target or context block refuses apply and undo; redo uses stored prose with zero dispatches |
| T8 | J5 | `test_ranges_reject_split_graphemes_repeated_blocks_and_locks` (`test_v1_rewrite.py`) | `rewrite.py` | Surrogate split, combining mark, ZWJ boundary refused; repeated paragraph unmapped on ID-less save; lock intersection refused; polish with plot reason refused |
| T9 | J7 | `test_prefix_outbox_failure_rolls_back_every_selected_episode` (`test_v1_accept.py`) | `repository.py` | Fault on last outbox row: nothing accepted; hole or stale slot refuses all; two connections accept same prefix: one acceptance; replay after reopen returns receipt; 250-word and 1,200-word imported pages accepted with a `length_warning` (band 550–900) and their `length_notes` stored; a 700-word episode has no warning; listed episodes get `story_ordinal` 1..n; a hand-written E2 with no job whose save binding predates E1's selection refuses `basis_missing`; an `origin=fixture` revision refuses |
| T10 | J8 | `test_obsolete_promotion_cannot_cover_current_source` (`test_v1_memory.py`) | `memory.py` | Task `awaiting_authority` until authorized; lease expiry on `sent` gives `uncertain`, no resend; result for replaced source stored `obsolete`; snapshot complete only when all hashes imported |
| T11 | J8, J9 | `test_exact_text_fallback_includes_whole_gap_to_boundary_and_overflow_blocks_before_reserve` (`test_v1_context.py`) | `context.py` | Gap included untruncated up to boundary, not beyond; claims from changed sources excluded; overflow names items and makes zero ledger rows |
| T12 | J8 | `test_oren_testimony_hearing_and_later_reveal_stay_separate` (`test_v1_memory.py`) | `memory.py`, `context.py` | Testimony needs speaker; Darin `heard`, not `believes`; later reveal absent from E2 knowledge; claim with wrong quote rejected |
| T13 | J6, J7 | `test_old_review_cannot_certify_new_basis_and_late_finding_does_not_unaccept` (`test_v1_review.py`) | `review.py` | Finding on old hash shown as older; acknowledge leaves impact open; `revalidate` refused while a current serious finding binds the pair; `resolve_finding` kinds clear; late serious finding on canon opens impact, pauses commission, canon unchanged; packet has no write path |
| T14 | side | `test_withdrawn_style_evidence_flags_note_and_generated_acceptance_creates_no_style` (`test_v1_review.py`) | `studio/store.py` | Evidence kinds required; undo of linked rewrite withdraws evidence and flags note; retirement undo keeps flag; accepted generated draft alone cannot be evidence |
| T15 | J10 | `test_change_set_keeps_old_canon_until_commit_and_invalidates_dependent_memory` (`test_v1_accept.py`) | `repository.py`, `memory.py` | Saving and staging new E1/E2 revisions opens no impact and continuation past E3 is not blocked; commit replaces E1/E2 atomically at story ordinals 1 and 2, writes `superseded` claim status rows (claim rows unchanged), invalidates snapshots from E1, flags E3, queues tasks in `awaiting_authority` |
| T16 | — | `test_migration_preserves_accepted_bytes_and_exports` (`test_v1_migration.py`) | `migrations.py` | Byte-identical export; mismatch between accepted text and memory source aborts; legacy facts unclassified; legacy mutations refuse after cutover |
| T17 | J3 | `test_server_handlers_return_while_exchange_waits` (`test_v1_server.py`) | `server.py`, `runner.py` | A save request completes while a fake exchange blocks; runner lease prevents a second runner on the same story |
| T18 | J5, J6 | `test_effective_basis_flags_revalidated_and_jobless_downstream` (`test_v1_core.py`) | `repository.py` | J5→J6 tracer: E2 r1 (job basis E1 r1) revalidated against E1 r5; saving E1 r6 flags E2 (effective basis is the revalidation); a hand edit of E2 inherits basis and stays flagged; an imported E3 with no job binds at save and is flagged when E2 changes; `accept_prefix` and flagging give the same answer for every case; withdrawing the revalidation (`revert_event`) reopens the impact |
| T19 | J5 | `test_reversibility_table_is_enforced` (`test_v1_core.py`) | `repository.py`, `commission.py` | Each "reversible" row in 01 §4 restores the before value through its command; reverting a first selection leaves `revision_id NULL` with `cas` incremented; reverting a revalidation relied on by an acceptance refuses; `revert_event` on an `accept`, `commission_stop` or ledger event refuses |
| T20 | J2, J7, J10 | `test_story_ordinal_stamped_at_acceptance_and_stable_across_replanning` (`test_v1_accept.py`) | `repository.py`, `studio/store.py` | Unaccepted episodes have no story position; acceptance stamps canon cursor + i; re-adopting A1 with a different count keeps accepted positions and renumbers only the unaccepted tail; an arc revision that drops an accepted episode refuses `accepted_conflict`; a change set reuses the ordinal; A2's first accepted episode gets ordinal 4 |
| T21 | J8 | `test_claim_correction_flags_revisions_that_consumed_the_claim` (`test_v1_memory.py`) | `memory.py`, `repository.py` | Correcting "Oren died" by `interpret` leaves the old claim row byte-identical and derives `superseded`; a selected E4 whose job consumed that claim gets a `claim_change` impact; a revision whose job did not consume it is not flagged; retrieval omits the superseded claim |

**Existing tests intentionally changed** (decided here, executed only during authorized implementation):

- `tests/test_merge_review_fixes.py` `test_story_write_lock_covers_paid_dispatch`: replaced by T5/T17 for v1; the legacy confirm path refuses after cutover, asserted in T16.
- `tests/test_merge_authoring.py` `test_competing_connections_cannot_both_reserve` (`:298–315`): **kept unchanged.** Two 600,000 reservations exceed the 1,000,000 cap under either blocking rule, so it asserts cap safety, not serialization, and it already shares one ledger between two stories, which is the owner-decided design. The new in-flight rule gets its own test, `test_two_in_flight_within_cap_third_refused`, in T4.
- Any test asserting that non-eligible output yields `text: None` from `MergeRuntime.exchange` is re-read during T5: it stays for the legacy path, and the v1 path asserts retained content instead (02 §3 step 5).
- 400–700 and padded-plan tests (`tests/test_studio_workflow.py:215–227`) stay green for unmigrated legacy stories; v1 contracts are tested separately.
- Legacy tests that build databases by constructing `SQLiteRepository`, `StudioStore`, `SQLiteBudget` or `ProjectMergeLedger` are unaffected, because those constructors keep their open-time DDL until cutover (§6.7).

## 11. Roadmap exclusions

**Deferred, not dropped:** the roughly 20-minute narrated episode (about 2,500–3,800 words) remains a product goal. It is a later milestone, taken up once the ~700-word initial slice has proven the machinery end to end (owner decision, 2026-10-02). The v1 band 550/700/900 is provisional and lives in one constant so that milestone changes a number, not the contract.

Not in v1: 30–40 episode quality evaluation; embeddings or semantic retrieval; adaptive review tool loops; parallel or branching chains and multiple simultaneous commissions per story; suffix removal; sub-block rebasing; automated or cross-project style learning; streaming output; collaboration; hosting or remote access; real-world fact verification; automatic retry or route fallback.

## 12. Required follow-up

1. **Independent Opus review** of the exact revised 01–04 (revision 3; record their SHA-256) and the revised prototype snapshot, by a reviewer who did not write them. Scope: the `SPEC-FIX-LOG.md` closures of B1–B4 and M1–M13, O1–O11 and S1–S5 closures, the recovery table, the ledger ceiling arithmetic, block identity and range rules, boundary clipping, the acceptance predecessor rule, and the browser matrix. Backend HOLD remains until that reviewer clears its scope.
2. Re-run the browser matrix (§8) on the revised fixture with desktop scenarios split so they finish.
3. Only then start T1 under separate implementation authority. Live qualification and spend remain separate gates (§9).
