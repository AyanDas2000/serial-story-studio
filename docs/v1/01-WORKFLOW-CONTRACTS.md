# V1 workflow contracts

**2026-10-02 · Revision 3: spec-fix of the independent review (`REVIEW-FINDINGS.md`, verdict BLOCKED) and the binding owner decisions of 2026-10-02 (`OWNER-DECISIONS.md`). Change log: `SPEC-FIX-LOG.md`.** Revision 2 reconciled the frozen revision 1 (manifest `07-08-frozen-inputs`), the early Opus architecture review, the Sonnet backend trial receipt, two simulated persona critiques and the integration/test-gap audit. It is not implementation, runtime proof or review clearance. **Backend implementation remains on HOLD** until a separate Opus review of this exact revision and the revised prototype clears it.

Companions: [data and context](02-DATA-INGESTION-CONTEXT.md), [diagrams and UX](03-DIAGRAMS-AND-UX.md), [implementation plan and disposition](04-IMPLEMENTATION-PLAN.md). All four documents describe the same reference journey **J0–J10** in §3. Commands are proposed, not existing endpoints.

## 1. Authority

| Material | Authority | Who can change it |
| --- | --- | --- |
| Idea, pasted pages, chat, suggestion, working proposal | Exploration. Governs nothing. | Anyone; models may propose |
| Adopted skeleton, adopted arc, adopted style note | Author intent for a named scope. Never a fictional event. | Author `adopt` only |
| Selected episode revision | Provisional working chain. One pointer per episode. Not canon. | Author `select`, `save_revision` (when the base is selected), `apply_candidate`, `revert_event`/`redo_event`, `ingest` with `select: true`; or a commission the author explicitly authorized for provisional progression. A repair never selects by itself; its candidate needs `apply_candidate` |
| Accepted narrative (`v1_canon`) | Primary narrative authority, exact final words | Author `accept_prefix` or `commit_change_set` only |
| Interpretation (claim), review finding | Source-linked reading with provenance, scope, standing and uncertainty. Cannot change prose. | Promotion/review jobs propose; author `interpret` corrects |
| Feedback | Local, scoped instruction consumed by named operations. Never a permanent preference by itself. | Author marks a message "use for next"; author retires |

### Invariants

1. **Writer's room, not a wizard.** Free writing, pasting and conversation never require an outline. Direction-led bulk drafting requires an adopted skeleton and an adopted arc.
2. **Every proposal offers Adopt as is, Edit and adopt, and Discuss.** Editing saves a revision first. Chat after adoption never moves the governing pointer.
3. **Generate, keep and chat never adopt direction or accept prose.** The only automatic pointer movement in v1 is provisional selection inside an explicitly authorized commission (§2).
4. **Linked drafts are sequential.** Episode *n+1* is prepared only after episode *n*'s selection commits, from the exact selected revision IDs and hashes. Never in parallel, never from an unrelated alternative.
5. **No lock is held across a network exchange.** Paid results are always stored. A late or changed-basis result is a durable detached candidate and never triggers dependent continuation.
6. **Rewrites are candidates.** Exact block/Unicode ranges, locks and consumed-context hashes are enforced. Semantic equivalence is advisory.
7. **Accepted text changes only through a staged change set** with visible impact. Ordinary save affects working revisions only.
8. **Serious current findings pause dependent continuation at the next safe boundary.** They never unaccept text. Acknowledging is not repairing.
9. **Accounting.** USD 1 (1,000,000 micro-USD) is the ceiling for the **whole application**, across every project and story, in one shared ledger (02 §3 "Ledger authority"). It covers all application inference, including chat, planning, extraction and review. No automatic retry, route substitution or fixture fallback; a revision with `origin=fixture` can never be accepted into canon. Development-agent usage is separate. Live routes and spend need separate qualification and authority (04 §9).

## 2. The commission: one decision, bounded authority

Persona runs showed that supervising each episode feels like babysitting a chain. Authority is preserved by one deliberate, inspectable decision instead of many routine ones.

`commission_arc` names: adopted skeleton and arc revisions, the slot range (for example E1–E3 of A1), the accepted boundary, the route and its qualified bounds, a **ceiling** in micro-USD, and two options:

- **Progression:** `provisional_chain` (each complete, validated, current-basis draft is selected provisionally and the next episode starts from it) or `review_each` (the commission waits for the author's `select` before each successor).
- **Included work:** an optional *memory* line and an optional *review* line (one quiet review per draft, and one per episode flagged by an upstream change). Both draw from the same ceiling. **Memory line scope (chosen reading):** it authorizes promotion tasks only for sources created when the author accepts revisions of this commission's slots with `accept_prefix`, and it stays valid after drafting completes (status `complete`) until the ceiling is used up or the author runs `stop_commission`. It does **not** authorize tasks queued by a later `commit_change_set` (J10): those wait in `awaiting_authority` until a `request_job` or a new commission authorizes them, and continuation meanwhile uses exact-text fallback. Reason: J8 needs memory after J7's acceptance, which comes after drafting completes; but a change set weeks later is a new author action at possibly different prices, and standing spend authority across it would be a surprise.
- **Line gates:** memory and review jobs keep running while the commission is paused for any reason except a route change or a missing ledger, because they never move a selection (02 §3 "Gates by job line"). Only the draft chain stops at a pause.

The commission never accepts prose, never adopts direction and never picks among alternatives the author created: an in-flight draft is selected only if the target episode's selection is unchanged since its job was frozen (02 §3 step 6, rule d). Each provisional selection is an event attributed to the commission, and is undone with `revert_event` like any selection (§4 "Reversibility").

It pauses **only** at real gates: changed basis (an upstream edit, alternative switch or new adopted direction), a current serious finding, an open impact before the next slot, context overflow, an uncertain or over-reservation charge, ceiling exhaustion, a changed route price or bound, a missing ledger, or an author or feedback pause request. Gate pauses take effect immediately and detach any in-flight draft. **Author and feedback pauses are requests** (`pause_requested`): while a draft is already sent, the commission stays `running` until its next checkpoint, the moment after that draft imports, so the draft is still selected under the single import rule (02 §3 step 6) and no successor is sent. With no draft sent, the pause is immediate. Everything else proceeds.

A paused commission resumes from its checkpoint with an explicit `resume_commission`. Resuming under an unchanged route price and ceiling needs no new spending decision. A changed price or a raised ceiling is a new spending decision carried by the same command: the payload names `new_ceiling_micro` (at least the amount already used, at most used + application remaining) and/or `accept_quote` (the new per-call quote shown to the author); without them a `route_changed` or `ceiling_exceeded` pause refuses to resume. A different route ID is not a resume: the author stops the commission and commissions again, because the route is part of the commission's frozen identity.

`request_job` remains the single-operation alternative (one chat reply, one rewrite, one memory update) with its own quoted bound.

## 3. Reference journey J0–J10

Reference case: *The Borrowed Witness*. Hearing clerk **Leena Vale** has a recorder that replays one sentence in another person's voice, changing listeners' perceived memories, not physical records. Each use erases one of Leena's memories. Investigator **Darin Saye** pursues impossible witness agreements. Skeleton S1: expose coercion; Leena moves from "useful lies are justice" toward accountable uncertainty.

Arc A1 purpose: *make Darin suspect a manufactured witness*. End state: *he obtains an ordinary record the recorder cannot alter*. Three episodes are the proof size, not a limit; five and six are equally valid routes:

1. Leena stages a witness interview; the reader sees her memory cost, not her target.
2. A witness says courier **Oren** died in a lockhouse fire. Darin hears the claim. Leena knows the recorder was used but not whether Oren survived.
3. Darin obtains the original dispatch ledger. The reader learns it predates the alleged death. Neither survival nor death is established.

Adversarial expectations: "the witness says Oren died" is testimony; hearing is not believing; the ledger is not survival proof; a later "Oren is alive" reveal cannot enter episode-2 character knowledge; a sentence repeated in two scenes is never a guessed rewrite anchor.

| Step | Author does | Command (basis) | Stored outcome | Gate or recovery |
| --- | --- | --- | --- | --- |
| **J0 Discovery** | Pastes a hearing scene, asks "What conflict is here?", rotates suggestions, writes a paragraph by hand | `ingest(kind=pages, origin=declared)`; `converse(thread, target)`; `save_revision` for manual prose | Source with blocks; thread messages; exploratory episode revision. Nothing adopted or accepted. | A failed reply leaves the question saved, not a fake answer. Suggestions fill the composer only on explicit choice; a nonempty composer offers append or replace with undo. |
| **J1 Direction** | Asks for a reverse outline, edits it, adopts S1. Later brainstorms S2. | `propose(layer=skeleton, feedback_ids)`; `save_revision`; `adopt(revision, expected_governing=null)` | S1 governs. S2 is a working revision; S1 still governs. | Stale adopt conflicts and keeps the proposal. Closing chat never adopts. |
| **J2 Arc** | Compares 3, 5 and 6 routes, adopts 3 | `propose_arc(S1, purpose, end_state)`; `adopt(arc revision)` | A1 with three intentions and count rationale. Three episode artifacts created, no padding. | Changing count later flags affected slots instead of rewriting them. |
| **J3 Commission** | Chooses "continue through the arc using each draft provisionally", ceiling, memory updates and quiet review included | `commission_arc(S1, A1, E1–E3, route, ceiling, provisional_chain, include=[memory, review])` | Commission record, frozen E1 job. E1 draft arrives, is selected provisionally; E2 job is frozen from E1's exact revision; and so on. | Overflow or missing qualification blocks before any reservation; plan and manual work remain. |
| **J4 Conversation during work** | While E2 drafts, discusses E1's interview, marks one message "use for the remaining episodes" | `converse(target=E1 rev)`; `mark_feedback(message, scope=remaining, apply=remaining)` | Feedback labelled "not used by E2 (already sent)". Applying to remaining sets `pause_requested=feedback`; the commission stays `running`, so E2 imports and is selected, and at that checkpoint it pauses instead of freezing E3. `resume_commission` then freezes E3 with the feedback within the same ceiling. | Feedback not marked is conversation only. It never becomes a style note. |
| **J5 Scoped rewrite and undo** | During the J4 pause: rewrites E1's opening paragraph (r3), edits E1's last paragraph by hand (r4), undoes the rewrite (r5). Confirms "E2 still fits E1 as now written" and resumes. | `request_rewrite(blocks, ranges, hashes, locks, intent=polish)`; `apply_candidate`; `save_revision`; `revert_event`; `revalidate(E2 ← E1 r5)`; `resume_commission` | Candidate, then selected E1 revisions changing only the target block; the hand edit survives undo. E2 is flagged at r3 (its effective basis for E1 is its job predecessor E1 r1), then the author revalidates E2 r1 against E1 r5, which becomes E2's effective basis for E1. E3 is frozen from E1 r5 and E2 r1. | An edit in a target or consumed-context block refuses apply/undo and opens before/AI/now comparison. Redo reuses stored prose; no model call. |
| **J6 Upstream impact** | Edits E1 by hand so Leena loses her mother's face instead of a street name, while E3 is in flight | `save_revision(E1, expected_selected)` | E1 r6 selected. E2 is flagged because its effective basis for E1 is the J5 revalidation (E1 r5), not E1 r6; the commission pauses (changed basis). E3 has no selection yet, so its in-flight job alone records the stale basis. The late E3 r1 is stored, charged and detached with `basis_changed` ("made from an older E1"). The review line runs during the pause (memory and review lines are not gated by a basis pause) and finds E2 still cites the street name. | Revalidating E2 is refused while that finding is open. Author runs `request_repair(E2)` (a single job with its own quote), then `apply_candidate` on the repair candidate to make E2 r2, whose effective basis is the repair job's predecessors (E1 r6); then resumes so E3 is redrafted from E1 r6 and E2 r2 (E3 r2). Acknowledge does not clear. |
| **J7 Accept prefix** | Reads E1–E3 prose with "changed since selected" marks, accepts | `accept_prefix([E1 r6, E2 r2, E3 r2] with hashes, expected_canon_seq, finding_dispositions)` | One acceptance group: exact final sources, story ordinals 1–3 stamped, canon pointers, history sequence, memory tasks. | Any stale slot (an effective basis not equal to the earlier listed or accepted revision, or missing), hole or open serious finding refuses the whole group. Length is advisory: outside 550–900 words the receipt warns and never refuses. |
| **J8 Memory** | Sees "Memory updating; using exact accepted pages." Corrects a reading that Oren died | Memory tasks run under the commission's memory line; `interpret(claim, source span, correction)` | Claims tied to exact accepted spans. Correction records attributed testimony and "survival unknown" as a new claim revision; the old claim's standing becomes `superseded` (derived). Any selected or accepted revision whose job consumed the old claim is flagged (`claim_change`). Prose unchanged. | Promotion failure leaves acceptance intact; continuation uses exact-text fallback. |
| **J9 Continue** | Plans arc A2 | `prepare_context(recipe=arc_planning, boundary=after E3)` | Context receipt: indexed or exact-text mode, items, omissions, temporal boundary | Overflow or an open conflict blocks dependent generation only; conversation and manual writing stay open. |
| **J10 Return and revise accepted pages** | Weeks later, revises accepted E1 and repairs accepted E2 | `stage_change_set(before=[E1,E2 canon], after=[revisions])`; `commit_change_set(expected_canon_seq)` | Old canon governs while staged: saving or staging working revisions of accepted E1/E2 opens no impact. Commit replaces both atomically at their existing story ordinals, supersedes claims from replaced sources, opens impacts, queues memory tasks (`awaiting_authority`, §2). | At commit, accepted E3 is flagged (its effective basis names the replaced E1/E2 canon revisions), not unaccepted; continuation past E3 blocks until it is revalidated or repaired. |

**Side journey, voice note:** after J5, the author proposes a note from evidence they choose (their own hand edit in J5 and one explicit feedback message), sees before/after for each, edits and adopts it for Leena's POV. Undoing the J5 rewrite does not remove the hand-edit evidence; undoing a linked rewrite marks that evidence withdrawn and flags the note for reaffirm or retire. Redoing that rewrite does not silently reactivate the evidence; the flag stays until the author reaffirms. Undoing a retirement restores the note with its flag intact. A generated draft that was merely accepted is never style evidence, and casual chat never becomes a style note.

**Resolution, not dismissal:** Oren's death finding is resolved by source-supported attribution (`interpret`), prose revision, or an evidence-cited rejection of a false positive. It is never resolved by declaring survival true or by "I understand".

## 4. Operation contracts

Every mutation carries `operation_id`, `story_id` and expected pointer values. An identical replay returns the original receipt; the same ID with a different payload is a conflict. Full DTOs, error codes and replay rules are in 04 §4.

| Command | Preconditions | Writes | Refusals |
| --- | --- | --- | --- |
| `ingest` | Declared kind and origin; size bounds; optional episode target with expected `selection_cas` | Source, blocks, fragment or episode revision; selection only with explicit `select: true` (02 §4 step 1) | Oversize keeps entered text and suggests splitting |
| `converse` / `mark_feedback` | Thread target revision exists | Message; feedback only on explicit mark; `apply=remaining` sets `pause_requested=feedback` | Unqualified route leaves message pending |
| `propose`, `propose_arc` | Named basis revisions and feedback IDs | Proposal revision, consumption rows | Missing applicable feedback blocks preparation |
| `save_revision` | Expected selected/working pointer; client block IDs | Immutable revision, block lineage, effective-basis rows (inherited or save binding, 02 §2), impact rows | Stale pointer returns comparison |
| `adopt` | Saved revision hash; expected governing | Adoption, governing pointer, impact | **Deterministic check (only one):** an arc revision for an arc that already has accepted episodes must keep those episode artifacts as its first *k* slots, in order; otherwise `accepted_conflict`. Any other conflict with accepted reality is advisory (a review may flag it); skeleton adoption has no deterministic check |
| `select` | Revision of that episode artifact; expected selection | Selection pointer and event; downstream flags | None beyond CAS |
| `commission_arc`, `pause_commission`, `resume_commission`, `stop_commission` | Adopted S/A, qualified route, ceiling within application remaining; resume may carry `new_ceiling_micro` / `accept_quote` (§2) | Commission, checkpoint, jobs; pause sets `pause_requested` while a draft is in flight | Overflow, unresolved charge, missing qualification; resume after `route_changed`/`ceiling_exceeded` without a new spending decision |
| `request_job` | Exact quote, TTL 120 s | One job | Expired or changed quote |
| `request_rewrite`, `apply_candidate`, `keep`, `discard`, `revert_event`, `redo_event` | Block IDs, ranges, hashes, locks | Candidate; revision and event; disposition | Lock, overlap, ambiguous anchor, changed consumed context |
| `request_repair` | Flagged edge, current upstream, exact quote (TTL 120 s) | A single job whose output is a `v1_rewrite` candidate with `intent=story_change`, recipe `repair`, ranges covering every block of the base revision. It never selects; the author applies it with `apply_candidate`, which runs the same overlap, lock and consumed-context checks | Same as `request_job`; `apply_candidate` refusals as above |
| `revalidate` | Flagged edge, current upstream. The author's free attestation that the downstream text still fits; the system cannot judge meaning itself | A `revalidate` effective-basis row binding the downstream revision and hash to the upstream revision and hash | Refused while a current serious finding binds that pair |
| `accept_prefix` | Contiguous next episodes in story order, each the current selection, each effective basis current against earlier listed or accepted revisions, no open serious finding, no `origin=fixture` | Story ordinals, canon, acceptance, outbox; length warnings in the receipt | Whole group rolls back |
| `interpret`, `resolve_finding` | Exact source span or finding; evidence | New claim revision (the prior becomes `superseded` by derivation) or resolution; `claim_change` impacts on revisions whose jobs consumed the prior claim (02 §4) | Acknowledgement is recorded but never resolves |
| `stage_change_set`, `commit_change_set`, `discard_change_set` | Accepted before-versions; expected canon sequence | Staged set (no impacts); on commit new canon at the same story ordinals, claim status rows, canon-change and claim-change impacts | Partial overlap with another staged set |
| `propose_style`, `adopt_style`, `retire_style`, `revert_style` | Author-chosen evidence; expected note head | Style revision and status events | Evidence from generated acceptance alone |
| `resolve_uncertain`, `release_undispatched` | `operation_id`, `story_id`; ledger row state and row version as `expected` | Conservative spend or audited release | Never refunds; never releases a dispatched call; stale row version |

### Reversibility

Revisions, messages, sources, events and ledger rows are never deleted, so "undo" always means a new event that moves a pointer or status back. Every undo below carries an expected `cas` and refuses with `stale_pointer` if the pointer moved since the event being undone.

| Action | Reversible? | Undone by | Notes |
| --- | --- | --- | --- |
| `select` (author or commission) | Yes | `revert_event(select event)` | Restores the event's before value. For a first selection that value is `revision_id NULL` (02 §2), so the episode returns to "nothing selected". Opens downstream impacts as any selection move does |
| `save_revision`, `ingest` with `select` | Pointer yes; revision stays | `revert_event(save event)` | Moves the selection back to the parent; refused if the selection is no longer the saved revision |
| `apply_candidate`, `repair_apply` | Yes | `revert_event` / `redo_event` | Block-image rule (03 §4); refuses on overlap |
| `keep`, `discard` (candidate) | Yes | `revert_event` | Returns the disposition to `open`; candidate text is immutable |
| `revalidate` | Yes | `revert_event(revalidate event)` | Sets `withdrawn_by_event`; the effective basis falls back (02 §2) and the impact reopens. Refused once a group that relied on it is accepted: then only a change set can supersede |
| `resolve_finding` | Yes, until acceptance relies on it | `revert_event` | The finding is open again and re-pauses dependent continuation |
| `adopt` | Partly | `adopt` of the earlier revision | A scope that has been governed never returns to "nothing governs", because commissions and jobs reference it |
| `mark_feedback` | Partly | `retire_feedback`; `revert_event(retire)` restores it | Consumption by jobs already sent is a fact and is permanent |
| `lock` / `unlock`, `pause_commission` / `resume_commission`, `stage_change_set` / `discard_change_set` | Yes | Each other | — |
| `interpret` | Yes | Another `interpret` | Writes a further claim revision; never deletes |
| Style commands | Yes | `revert_style` | Withdrawal flags follow the side journey (§3) |
| `stop_commission` | **Terminal** | — | Commission again; spend already made is not returned |
| `accept_prefix`, `commit_change_set` | **Terminal** | A later change set | Story ordinals never move; old text can be re-staged as a new change set |
| `discard_change_set` | **Terminal** | Stage again | — |
| `resolve_uncertain`, `release_undispatched` | **Terminal** | — | Ledger-only, never refunds |
| `converse` messages, `ingest` sources | **Terminal** as records | — | Nothing governs because of them alone |

## 5. Smallest connected slice and exclusions

The slice is J0–J10 for one story with fakes: adopted skeleton, variable arc, one commission with provisional progression, conversation during work, block-scoped rewrite and durable undo, upstream impact with selective repair, exact prefix acceptance, source-current memory with exact-text fallback, continuation, and one multi-episode change set. Voice notes are in the slice in their manual, evidence-chosen form.

Excluded from v1 (04 §11): 30–40 episode quality evaluation, adaptive review tool loops, branching and parallel chains, suffix removal, sub-block edit rebasing, automated style learning, cross-project style, streaming, collaboration and hosting. Nothing here claims the slice fits within USD 1 or that model prose is good.
