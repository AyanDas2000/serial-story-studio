# Spec-fix log: finding → change → location

Source findings: `REVIEW-FINDINGS.md`. Binding decisions: `OWNER-DECISIONS.md`. Documents: `project/docs/v1/01-WORKFLOW-CONTRACTS.md` (01), `02-DATA-INGESTION-CONTEXT.md` (02), `03-DIAGRAMS-AND-UX.md` (03), `04-IMPLEMENTATION-PLAN.md` (04). All four headers now say revision 3.

## Blockers

| ID | Status | What changed | Where |
| --- | --- | --- | --- |
| B1 | Resolved, with one deliberate refinement | Defined one effective basis per (downstream revision, upstream artifact) pair. The priority order is revalidate, then job, then inherited, then save_binding, and a missing row is never current. It is stored in the new `v1_basis` table. `v1_predecessor` now has one row per earlier episode (`role` selected or canon). The same rule is used for flagging and for `accept_prefix` (`basis_missing` / `basis_stale`). J5/J6 were re-traced. Refinement: hand edits inherit the parent's basis instead of binding at save time (reason in the handoff) | 02 §2 "Effective basis", job tables; 04 §4 `save_revision`, `apply_candidate`, `accept_prefix`, error codes, §5 tables/indexes/triggers; 01 J5, J6, J7, §4 `save_revision`/`revalidate`/`accept_prefix`; 03 §3; 04 T18, T9 |
| B2 | Resolved | Added `v1_job.target_selection_cas` at freeze. Import selection requires an unchanged `cas`; otherwise the result is detached with `author_selected`. `v1_selection.revision_id` is nullable and created at `cas 0` | 02 §2, §3 steps 1, 4, 6; 01 §2; 04 O1, T5 |
| B3 | Resolved | `pause_requested IN (author, feedback)` while the status stays `running`, effective at the next checkpoint. One import-selection rule. Gate pauses detach the in-flight draft. 02 §3 step 6 was rewritten, and 04 "Pause rules" now refers to it | 02 §2 commission, §3 step 6, "Pause requests"; 01 §2, J4; 03 §2, §3; 04 O9, §4 pause rules and `resume_commission`/`pause_commission`, T6 |
| B4 | Resolved per owner decision | One application ledger per user. `project_id`/`story_id` are row columns. `CHECK (cap = 1000000)`. `init_ledger`/`migrate --ledger` create the file; `create_project` registers a row. Recovery is scoped to the runner's own story. Supersedes the per-project file design | 01 §1.9; 02 §1, §3 "Ledger authority", step 3, recovery; 03 §1; 04 S2, O2d, §3 budget row, §4 commission DTO, §5 ledger DDL, §6.4, §9.2, T4 |

## Major

| ID | Status | What changed | Where |
| --- | --- | --- | --- |
| M1 | Resolved | The safe boundary is the story-side `claiming` commit. Before it: no dispatch and the reservation is released. After it: the result is detached. Test made deterministic | 02 §3 step 4; 03 §2, §3; 04 T5 |
| M2 | Resolved | A claim-time refusal releases the reservation in the same runner step. A refreeze always creates a new job and a new ledger operation | 02 §3 steps 1, 4; 04 §4 pause rules, `resume_commission`; T6 |
| M3 | Resolved | Memory and review lines are gated only by `route_changed`, `ledger_missing` and `stopped`, and stay under ledger and ceiling checks. Attack surface recorded: spend during a pause, bounded by the ceiling | 02 §3 "Gates by job line"; 01 §2, J6; 03 §2, §3; 04 T6 |
| M4 | Resolved | Claim and source items in `v1_context_item` count as dependencies. Supersession, rejection or a change set opens `claim_change` impacts | 02 §2 `v1_context_item`, `v1_impact`, §4 "Claim dependencies"; 01 J8, §4 `interpret`; 04 T21 |
| M5 | Resolved | `v1_claim` rows are fully immutable with `base_standing`. Standing is derived from successors and the append-only `v1_claim_status` table, and the SQL is stated. Retrieval uses derived standing | 02 §2 memory, §4 step 6; 04 §5, §7 retrieval, T15, T21 |
| M6 | Resolved per parent choice | New `v1_story_position`, stamped at acceptance with uniqueness over accepted episodes only. Story order, narrative points and J2 re-planning are defined. Superseded-then-reaccepted episodes reuse their ordinal, and v1 cannot vacate a position | 02 §2 "Ordinals", `v1_canon`; 01 J7, J10; 04 §4 `accept_prefix`, §5, T20 |
| M7 | Resolved | Canon impacts open at commit. Saving or staging working revisions of an accepted episode opens no impact and no pause | 02 §2 "Effective basis"; 01 J10, §4; 03 §5; 04 §4 `save_revision`, T15 |
| M8 | Resolved | `request_repair` is a single quoted job that produces a whole-episode `story_change` candidate. Only `apply_candidate` selects it. The decision count was corrected | 01 §1 table, §4, J6; 03 §3, §6 table; 04 §1, §4 `apply_candidate` |
| M9 | Resolved | Added a reversibility table (reversible / partly / terminal, with the command for each). `revert_event` is limited to the listed kinds | 01 §4 "Reversibility"; 03 §6 table; 04 §4 events, T19 |
| M10 | Resolved per owner decision | v1 band 550/700/900, warn and never refuse, with optional stored `length_notes`; the desk asks for a reason. Legacy 400–700 refusal kept. The 20-minute goal is stated as deferred | 02 §1; 01 J7; 03 §6 table; 04 O6, §4 `accept_prefix`, §11, T9 |
| M11 | Resolved | No-mutation-on-open applies only to databases with `v1_meta`/`ledger_meta`. All four legacy constructors are listed and stay unchanged until cutover | 02 §1; 04 §3 repository row, §6.7, T1, §10 existing-tests list |
| M12 | Resolved by *retain* | The v1 adapter retains bounded non-eligible content: `partial` becomes a detached revision, `malformed` becomes `raw_text` only. Disclosed as a change to `merge.py:350–367` on the v1 path | 02 §1, §2 `v1_result`, §3 steps 5–6, recovery; 03 §2; 04 T5, §10 existing-tests list |
| M13 | Resolved | Recovery rows for orphans (`dispatched=0` released, `dispatched=1` uncertain), other stories' rows (ignored) and legacy rows (classified once at migration) | 02 §3 recovery; 04 S1, §6.4, T5 |

## Minor

| Finding | Status | Change / location |
| --- | --- | --- |
| Job diagram: `sent` never written; `refused` and `not_sent` transitions missing | Fixed | 02 §2 "Job states"; 03 §2 job diagram |
| `Uncertain → Imported` unreachable | Fixed (dropped) | 03 §2; 02 §3 ledger states; 04 `resolve_uncertain` |
| `provisional_selected` has no producer | Fixed (removed) | 02 §2 standing; 04 §7 retrieval |
| `resolve_uncertain` DTO lacks envelope/CAS | Fixed | 04 §4 DTO with `row_version`; 01 §4; 04 §5 `row_version` column |
| Vacuous decision rule for `test_competing_connections_cannot_both_reserve` | Fixed | 04 §10: the test is kept (it proves cap safety across two stories in one ledger); a separate `test_two_in_flight_within_cap_third_refused` was added to T4 |
| Authority table omits pointer movers | Fixed | 01 §1 table |
| No fakes for converse/promotion/review/rewrite; fixture acceptance unspecified | Fixed | 04 §10 `tests/v1_fakes.py` `FakeTransport`; 01 §1.9 and 04 §4 `accept_prefix`: `origin=fixture` cannot be accepted |
| Spec-vs-code table: `merge.py:298/302` limits ambiguous | Fixed | 02 §1; 04 §7 |
| Range rule vs emoji modifiers / regional indicators (reviewer suspicion, not verified) | Partly fixed | 02 §2 "Ranges" adds modifiers, tags, keycap and RI pairs. Full grapheme segmentation is deliberately left out (no stdlib support), and the gap is stated |

## Ambiguous clauses

All ten rows in the reviewer's table were resolved, each with one reading and its reason, in 04 §2 "Independent review: ambiguous clauses resolved", and stated at the rule's home section (01 §2, 01 §4, 02 §2, 02 §3, 02 §4, 04 §4, 04 §7).

## Deliberately not done

- No prototype, browser-matrix or design-audit work. That is out of scope, and `docs/v1/prototype/` is absent.
- I did not assess security of the `/api/v1/*` routes, migration details (export byte-identity, `v1_legacy_map`) or memory.py beyond line 74. The reviewer also did not assess these, and they are unchanged.
