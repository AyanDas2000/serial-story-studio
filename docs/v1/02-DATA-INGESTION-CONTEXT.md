# V1 data, ingestion and context

**2026-10-02 · Revision 3, spec-fix of the independent review (`REVIEW-FINDINGS.md`) and the owner decisions of 2026-10-02 (`OWNER-DECISIONS.md`). Source inspection only.** No migrations, tools or runtime qualification exist. Backend implementation remains on HOLD pending review of this exact revision. The finding-by-finding change log is `SPEC-FIX-LOG.md` beside the project.

Companions: [workflow and journey J0–J10](01-WORKFLOW-CONTRACTS.md), [diagrams and UX](03-DIAGRAMS-AND-UX.md), [implementation plan](04-IMPLEMENTATION-PLAN.md).

## 1. Observed seams that drive decisions

Paths are in this source-only copy; behavior is read, not executed.

| Source | Observed | Decision |
| --- | --- | --- |
| `serial_story/repository.py:25–52` | `episodes.number BETWEEN 1 AND 200`; one pending row per number; acceptance tied to `next_episode` | v1 tables; legacy rows read through an adapter only |
| `repository.py:183` | Acceptance requires 400–700 words | Unchanged for unmigrated legacy stories. For v1 stories length is advisory: band floor 550, target 700, ceiling 900 words; outside the band the receipt warns and never refuses (owner decision M10) |
| `repository.py:70–73`; `studio/store.py:76–87`; `budget.py:50–59`, `151–163`; `studio/authoring.py:49` | Constructors and a property run `CREATE TABLE`/`ALTER TABLE`/`INSERT` on open, and the legacy suite builds every database this way | **Legacy constructors stay unchanged until cutover.** The no-mutation rule applies only to a database that already contains `v1_meta` (story) or `ledger_meta` (application ledger): opening one never mutates it. v1 schema is created only by explicit `migrate`, `create_project` or `init_ledger` (04 §6.7) |
| `studio/authoring.py:193–210` | `BEGIN IMMEDIATE` held through `runtime.exchange` | Short transactions before and after; no lock during I/O |
| `studio/authoring.py:231–232` | Changed basis after a charged success raises and saves nothing | Store as detached candidate |
| `studio/server.py:108,327` | One `threading.Lock` around every mutation handler | Handlers stay short; exchanges run on a runner thread outside the lock |
| `budget.py:142–143` | One ledger path relative to the code tree; `CAP = 1_000_000` is a constant; one ledger is shared by every story (`tests/test_merge_authoring.py:298–315`) | One application ledger per user, outside any code tree, shared by every project and story; `project_id` and `story_id` are row columns; cap stays 1,000,000 by CHECK (owner decision B4, §3 "Ledger authority") |
| `studio/merge.py:350–367`; `studio/authoring.py:221–222` | Non-eligible output (finish reason not `stop`, or unverified accounting) is returned as `text: None` and nothing is saved | v1 changes the adapter: non-eligible content is retained, bounded by the route's qualified output bound, and stored as a `partial` or `malformed` result (§3 step 6). Legacy `confirm` keeps current behaviour |
| `studio/merge.py:298`, `:302` `MergeRuntime.validate` | Prompt ≤ 48,000 characters, input ≤ 200,000 tokens, hard refusal | For v1 recipes the character limit is replaced by the context decision (§4); the token check uses the route's qualified `max_input_tokens`. The legacy path keeps both checks |
| `budget.py:194–195` | Any `reserved` or `uncertain` row blocks all reservations; no resolution API | Block only on `uncertain`; add conservative resolution and audited release |
| `budget.py:221–223` | Overcharge sets `uncertain`, `reserved=charge`, `spent=0` | Preserved; conservative resolution moves the full liability to spent |
| `memory.py:74–75` | `one_current_fact(subject,predicate)` | Not copied; claims coexist by holder, stance and narrative point |

## 2. Relational model

Python stdlib `sqlite3`, new `v1_` tables in the story database, opaque text IDs, composite `(story_id, …)` foreign keys so no row references another story. Revisions are immutable. Pointers carry an integer `cas` incremented on every change. JSON columns hold bounded, versioned content only; identity, scope and authority stay relational. Creation order, triggers and indexes are in 04 §5.

### Identity and pointers

| Table | Key columns and constraints |
| --- | --- |
| `v1_meta` | `schema_version`, `story_id`, `project_id`, `migrated_from` (legacy file SHA-256 or null), `history_start` |
| `v1_artifact` | `artifact_id PK`, `kind IN (seed, skeleton, arc, episode, fragment, style)`, `arc_id`, `ordinal` (position in its parent: an episode's position in its arc, an arc's position in the story; **arc-relative for episodes, provisional, never story-wide**), `working_head` (skeleton/arc/style only; NULL for episodes) |
| `v1_revision` | `revision_id PK`, `artifact_id FK`, `parent_id` (same artifact, checked), `seq`, `content_sha256`, `origin IN (human, generated, imported, fixture, merged)`, `job_id`, `origin_ref` (candidate or fragment revision, optional), `reason`; `UQ(artifact_id, seq)` |
| `v1_selection` | `PK(story_id, episode_artifact_id)`, `revision_id FK NULL` (NULL = nothing selected; when set it must belong to that artifact), `cas`, `selected_by IN (author, commission)`, `event_id`. The row is created with `revision_id NULL, cas 0` when the episode artifact is created, so every episode always has a `cas` to compare against |
| `v1_story_position` | `PK(story_id, episode_artifact_id)`, `story_ordinal`, `assigned_acceptance_id`; `UQ(story_id, story_ordinal)`. Written only by `accept_prefix` (see "Ordinals" below) |
| `v1_adoption` / `v1_governing` | Append-only adoption; governing `PK(story_id, scope_kind, scope_id)`, `adoption_id`, `cas` |
| `v1_canon` | `PK(story_id, episode_ordinal)` (story-wide; equals the artifact's `v1_story_position.story_ordinal`), `episode_artifact_id`, `source_id`, `revision_id`, `acceptance_id`; story-level `canon_seq` in `v1_meta` |
| `v1_basis` | Effective-basis rows (below): `downstream_revision_id`, `upstream_artifact_id`, `upstream_revision_id`, `upstream_sha256`, `kind IN (job, inherited, save_binding, revalidate)`, `event_id`, `withdrawn_by_event` (revalidate rows only); `UQ(downstream_revision_id, upstream_artifact_id, kind, event_id)` |

**One authoritative selected pointer per episode artifact.** Episode artifacts have no separate working head. Saving an edit to the selected revision creates a new revision and moves selection in the same transaction. Saving an edit to an unselected alternative creates a new unselected revision. Commission slots are `PK(commission_id, position) → episode_artifact_id`; they are not heads. For an accepted episode, `v1_selection` is the working pointer that feeds `stage_change_set`; canon governs everything else, and moving that pointer flags nothing (see "Effective basis").

**Ordinals.** Drafting and commissioning use the arc-relative `v1_artifact.ordinal`; it may change when an arc is re-adopted and nothing durable depends on it. **Story order** of episodes is: accepted episodes by `story_ordinal`, then unaccepted episodes by (arc `ordinal`, episode `ordinal`). `accept_prefix` stamps `story_ordinal = canon cursor + i` for the *i*-th listed episode; the value never changes afterwards. An unaccepted episode has no `v1_story_position` row, so uniqueness covers accepted canon only. A change set replaces the revision at an existing `story_ordinal` and reuses it; the artifact keeps its position. v1 has no unaccept or suffix-removal path, so a position is never vacated and an episode whose canon revision was superseded and later re-accepted always reuses its ordinal (canon history stays continuous). Re-adopting an arc with a different count (J2) leaves every `story_ordinal` untouched and renumbers only the unaccepted tail's arc ordinals.

**Narrative points** are `(story_ordinal, block ordinal)`. Claims are extracted only from canon (§4 step 3), so every stored claim point uses a story ordinal. A boundary for an unaccepted target is computed per operation as `(canon cursor + k, block ordinal)`, where *k* is the target's 1-based position among unaccepted episodes in story order; it is frozen in the context receipt, labelled provisional, and never stored on a claim.

**Effective basis (one definition, used for flagging and for `accept_prefix`).** For a downstream episode revision *D* and each episode artifact *U* before it in story order, the effective basis `basis(D, U)` is, in priority order:

1. the latest non-withdrawn `revalidate` row for (*D*, *U*);
2. otherwise the `job` rows: the job that produced *D* (draft, or a state-asserting `story_rewrite`/`repair` candidate applied to make *D*) recorded every *U* at freeze (§3 step 1);
3. otherwise the `inherited` rows: a revision made from a parent of the same artifact (hand save, `polish` apply, `revert_event`, `redo_event`) copies its parent's effective basis at save time, because a local edit does not re-read upstream;
4. otherwise the `save_binding` rows: a revision with no job and no parent (first hand-written page, `ingest` into an episode, fragment placed with `save_revision`) binds at save time to each *U*'s canon revision if *U* is accepted, else *U*'s current selection.

How *D* was made fixes which one of rules 2–4 writes rows for it; rule 1 can override any of them per *U*. A *U* that the applicable rule did not record (for example an episode created after *D*'s job froze) has no row.

`basis(D, U)` is **current** when it equals *U*'s canon revision if *U* is accepted, otherwise *U*'s current selection. A missing row is never current. When *U*'s selection moves (any of `select`, `save_revision`, `apply_candidate`, `revert_event`, `redo_event`, commission import) and *U* is unaccepted, every selected downstream *D* whose `basis(D, U)` is not current gets an open `v1_impact`. When *U*'s canon changes (`commit_change_set` only), the same check runs against the new canon revision for every selected or accepted *D*. Staging or saving working revisions of an accepted episode opens no impact (old canon governs). An open `upstream_selection` or `canon_change` impact closes (`revalidated`, `repaired` or `superseded`) when the flagged artifact's selected (or, if accepted, canon) revision's basis for the cause artifact becomes current. `claim_change` impacts close as described in §4 "Claim dependencies". Inheritance (rule 3) is deliberately stricter than binding every new revision at save time: binding a hand edit to current upstream would let any small edit to E2 silently clear its flag against a changed E1.

### Sources, blocks, ranges

| Table | Key columns |
| --- | --- |
| `v1_source` | `source_id PK`, `revision_id UQ`, `sha256`, `kind IN (idea, pages, setup, narrative)`, `declared_authorship IN (author, unknown, generated)` |
| `v1_block` | `PK(source_id, block_id)`, `ordinal`, `text`, `sha256`, `scene_id`; `UQ(source_id, ordinal)` |
| `v1_block_lineage` | `(new_source_id, new_block_id) → (prior_source_id, prior_block_id)`, `relation IN (same, edited, inserted, deleted)` |
| `v1_lock` | `lock_id`, `artifact_id`, `block_id`, `start`, `end`, `text_sha256`, `locked_event`, `unlocked_event` |

**Block identity producer.** A block is a paragraph after line-ending normalization (CRLF/CR to LF) and splitting on blank lines. The browser editor sends `[{block_id | null, text}]` on save. The server checks every submitted ID exists in the base revision and appears at most once. Same ID and same hash records `same`; same ID and new hash records `edited`; null records `inserted`; missing IDs record `deleted`. Plain-text saves without IDs (paste, CLI, import) map a block only when its hash is unique in both base and new source; repeated or ambiguous blocks receive new IDs and stay unmapped. No fuzzy matching.

**Ranges** are half-open Unicode-scalar offsets inside one block. The browser sends UTF-16 offsets plus the exact selected text; the server converts, verifies the text, and refuses a boundary that splits a surrogate pair, precedes a combining mark (`unicodedata.combining > 0`), a variation selector (U+FE00–U+FE0F), an emoji modifier (U+1F3FB–U+1F3FF), a tag character (U+E0020–U+E007F) or U+20E3, sits next to a zero-width joiner, or falls inside a regional-indicator pair (odd count of U+1F1E6–U+1F1FF immediately before it). Python's stdlib has no grapheme segmenter, so this list is the v1 boundary rule; anything it misses is a known gap, not a silent pass. Multi-block selections are ordered lists of whole or partial block ranges.

### Conversation, feedback, style

| Table | Key columns |
| --- | --- |
| `v1_thread` / `v1_message` | Thread: `layer`, `target_revision_id`, `commission_id`. Message: ordered, immutable, sender, content, job ref |
| `v1_feedback` | `message_id`, target revision and optional block range, `scope IN (range, block, episode, arc, remaining, story)`, `status IN (active, retired)`, `marked_event` |
| `v1_consumption` | `UQ(job_id, feedback_id, feedback_version)`; author-recorded `satisfied` separately |
| `v1_style_evidence` | `style_revision_id`, `evidence_kind IN (human_edit, explicit_feedback, chosen_example)`, `event_id`/`message_id`/span, `status IN (active, withdrawn)`, `withdrawn_by_event` |

Feedback is created only by an explicit author mark on a message. `story` scope is still feedback (retirable, versioned), not a style note.

### Jobs, commissions, results

| Table | Key columns |
| --- | --- |
| `v1_commission` | `commission_id PK`, adopted skeleton/arc revisions, slot range, route ID, `ceiling_micro`, `progression IN (provisional_chain, review_each)`, `include_memory`, `include_review`, `status IN (running, paused, stopped, complete)`, `pause_requested IN (NULL, author, feedback)`, `pause_reason`, `checkpoint_position`, `cas` |
| `v1_job` | `job_id PK`, `recipe`, `recipe_version`, `line IN (draft, memory, review, single)`, `context_id`, `commission_id`, `target_artifact_id`, `target_selection_cas` (the target's `v1_selection.cas` at freeze; NULL for jobs that cannot select), `request_sha256`, `ledger_operation_id UQ`, `state IN (frozen, claiming, sent, imported, refused, not_sent, uncertain)` |
| `v1_predecessor` | `PK(job_id, position)`, `upstream_artifact_id`, exact `revision_id` and `sha256`, `role IN (selected, canon)`. One row for **every** episode before the target in story order: the canon revision for accepted episodes, the exact selected revision for unaccepted ones. Copied to `v1_basis` as `job` rows when the result becomes a revision |
| `v1_context_item` | `context_id`, item kind, `claim_id` or `source_id`, hash, included/omitted. Claim and source items are **dependencies** (§4 "Claim dependencies") |
| `v1_result` | `UQ(job_id)`, `output_revision_id` (NULL for `malformed` structured output and `refused`), `raw_text` (bounded; for `malformed`), `completeness IN (complete, partial, refused, malformed)`, `eligibility IN (selected, available, detached, ineligible)`, `detached_reason IN (basis_changed, author_selected, commission_paused, commission_stopped, incomplete)` |

**Job states:** `frozen → claiming` (story txn, §3 step 4) `→ sent` (story txn after the ledger claim commits) `→ imported | refused` (story txn after settle); `frozen | claiming → not_sent` (claim-time refusal, pause, stop, or recovery with `dispatched=0`); `claiming | sent → uncertain` (dispatched, no verified receipt). `refused` means the provider returned an explicit refusal with a settled receipt. Recovery treats `claiming` with `dispatched=1` exactly like `sent`, because the crash may fall between the ledger claim and the `sent` write.

### Rewrites, history, canon

| Table | Key columns |
| --- | --- |
| `v1_rewrite` | Candidate: `base_revision_id`, `intent IN (polish, story_change)`, reason, `context_id`, disposition `IN (open, applied, kept, discarded)` |
| `v1_rewrite_range` | Ordered `block_id`, `start`, `end`, `before_sha256`, replacement text |
| `v1_affected_block` | Per candidate: every target and consumed-context block ID with its hash at freeze time |
| `v1_event` | Append-only: `seq`, `action`, `before_images` / `after_images` (block ID, text, hash), `revert_of`, actor (`author` or `commission:<id>`), reason |
| `v1_operation` | `PK(story_id, operation_id)`, canonical request fingerprint, receipt |
| `v1_acceptance` | Ordered accepted revisions/hashes, prior and new `canon_seq`, finding dispositions |
| `v1_change_set` | Staged before canon/after revisions, impact list, `status IN (staged, committed, discarded)` |
| `v1_impact` | Flagged artifact and revision, `cause_kind IN (upstream_selection, canon_change, claim_change, finding)`, cause artifact or claim, cause event, `state IN (open, revalidated, repaired, superseded)` |

### Memory and review

| Table | Key columns |
| --- | --- |
| `v1_outbox` | `task_id`, `source_id`, `source_sha256`, `recipe_version`, `state IN (awaiting_authority, authorized, leased, sent, imported, failed, obsolete, uncertain)`, `lease_owner`, `lease_expires`, `ledger_operation_id`; `UQ(source_id, source_sha256, recipe_version)` |
| `v1_snapshot` | `snapshot_id`, `through_ordinal`, covered source IDs/hashes, `status IN (complete, invalidated)` |
| `v1_claim` | Immutable revisions: `kind`, `subject`, `about_claim_id`, `speaker`, `holder`, `stance IN (asserts, heard, believes, doubts, knows, unknown)`, `exposure IN (witnessed, told, read, inferred, none)`, `narrative_point` (ordinal, block ordinal), `world_validity IN (unknown, true_in_story, false_in_story)`, `reader_reveal_point`, `base_standing IN (exploratory, accepted_derived, legacy_unclassified)`, `source_id`, `prior_claim_id`. **Every column is immutable**; no row is ever updated |
| `v1_claim_status` | Append-only: `claim_id`, `status IN (superseded, rejected, reinstated)`, `review_state`, `event_id`, `seq` |
| `v1_claim_evidence` | Claim, source span, `relation IN (supports, contradicts, context)` |
| `v1_review` / `v1_finding` / `v1_tool_read` | Review binds target revision hash and context hash; finding severity, confidence, citations, `resolution IN (open, revised, reinterpreted, rejected_with_evidence)`, acknowledgements separately; read receipt per packet item and per omission |

Claim kinds: `event`, `testimony`, `belief`, `knowledge`, `reader_reveal`, `relationship`, `promise`, `summary`, `author_setup`, `future_intention`. Testimony requires `speaker`; belief and knowledge require `holder` and `about_claim_id`. "The witness says Oren died" is `testimony(speaker=witness, about=event(Oren dies), world_validity=unknown)`. "Darin hears it" is `belief(holder=Darin, about=testimony, stance=heard, exposure=told)`. Absence of a claim never implies its negation. `accepted_derived` means provenance, not objective truth.

**Standing is derived, never stored on the claim.** Current standing of claim *c* is: `superseded` if any claim row has `prior_claim_id = c` (a correction by `interpret` writes such a row); otherwise the `status` of the highest-`seq` `v1_claim_status` row for *c*, treating `reinstated` as "no status"; otherwise `base_standing`. As SQL: `COALESCE(CASE WHEN EXISTS(successor) THEN 'superseded' END, NULLIF(latest_status, 'reinstated'), base_standing)`. `commit_change_set` writes `superseded` status rows for claims from replaced sources (§4 step 6). There is no `provisional_selected` standing: claims come only from canon.

## 3. Transactions, dispatch and recovery

**Short story transactions** (`BEGIN IMMEDIATE`, existing savepoint mechanism at `repository.py:82–97`) wrap every mutation: verify expected `cas` and fingerprints, insert immutable rows, move pointers, write events, impacts and the operation receipt.

**Dispatch protocol** for every paid job, including chat, memory and review:

1. *Freeze* (story txn): check basis; write `v1_context` and `v1_context_item`, one `v1_predecessor` row per earlier episode in story order (§2), `target_selection_cas` (the target's current `v1_selection.cas`), and job `frozen` with request hash. A refreeze (resume, feedback applied, new basis) always writes a **new** job with a new `ledger_operation_id`; the superseded job becomes `not_sent`.
2. *Quote* (no txn): compute reservation from the qualified route (existing `quote` logic, `authoring.py:95–144`).
3. *Reserve* (ledger txn): fingerprint replay; refuse if any `uncertain` row exists anywhere in the application ledger, if `amount > cap − Σspent − Σreserved` (all projects), if the commission sum `spent + reserved + amount > ceiling`, or if the number of `reserved` rows in the application ledger (dispatched or not) is already `MAX_IN_FLIGHT = 2`.
4. *Claim* (story txn, then ledger txn): recheck in the story txn the gate for the job's line (below), basis currency of every `v1_predecessor` row, and `target_selection_cas`; set job `claiming`; commit. **The committed story-side `claiming` write is the safe boundary.** Any edit, select, pause or stop that commits before it prevents dispatch: the runner, in the same runner step, sets the job `not_sent` and calls `release_undispatched` on its reservation, so no paused commission holds allowance. Anything that commits after it cannot stop the call; its result is stored and detached by step 6. Then ledger `claim_dispatch`; then story txn sets job `sent`. If `claim_dispatch` refuses (row no longer `reserved`), the job becomes `not_sent` and nothing is sent.
5. *Exchange*: runner thread, no SQLite transaction, no server lock. The v1 adapter retains non-eligible content (finish reason other than `stop`, or unparseable structured output), bounded by the route's qualified output tokens, instead of returning `text: None` (`merge.py:350–367`); eligibility is decided at import, not by discarding text.
6. *Settle* (ledger txn) then *import* (story txn). Import is idempotent on `UQ(job_id)`. Classification:
   - Prose recipes: complete output becomes a revision with `completeness=complete`; partial output (finish reason other than `stop`) becomes a revision with `completeness=partial`, always `detached` with reason `incomplete`. Structured recipes (promotion, review): output that fails the JSON schema is stored as `raw_text` with `completeness=malformed`, `ineligible`, and writes no claims or findings. A provider refusal is `completeness=refused`, job `refused`.
   - **The single import-selection rule.** A complete draft result is `selected` (selection moves with `selected_by=commission` and an event) **iff all four hold**: (a) the commission has `progression=provisional_chain`; (b) its `status` is `running` (a set `pause_requested` does not prevent selection); (c) every `v1_predecessor` row of the job is still current (§2 "Effective basis"); (d) the target's `v1_selection.cas` still equals `target_selection_cas`. Otherwise: under `review_each`, a result that passes (b)–(d) is stored unselected with `eligibility=available` and the commission waits for the author's `select`; every other case is `detached` with the first failing reason in the order `basis_changed` (c), `author_selected` (d), `commission_stopped` / `commission_paused` (b). The causal reasons come first because a basis change also pauses the commission, and the desk must say "made from an older version", not "paused". A single job's draft or candidate never selects; it is `available`.
   - **Checkpoint.** After an import, if the commission is `running` and the result was selected: if `pause_requested` is set, the commission becomes `paused` with `pause_reason` = that value and `pause_requested` is cleared, and no successor is frozen; otherwise the next slot is frozen (step 1). A detached result never freezes a successor: if the commission is still `running` when a draft imports unselected (`partial`, `author_selected`, refused), it becomes `paused` with `pause_reason=result_not_selected` and `pause_requested` is cleared.
   - Every gate pause (changed basis, serious finding, overflow, uncertain charge, ceiling, route change, ledger missing) sets `status=paused` directly, so the in-flight draft, if any, imports detached. The author can still choose it with one `select`.

**Gates by job line.** Draft jobs (the commission's chain) claim only when the commission `status=running` with no `pause_requested`. Memory and review jobs of a commission (`line=memory|review`) claim while the commission is `running` or `paused` for any reason except `route_changed` and `ledger_missing`, and never once it is `stopped`; they still pass every ledger check in step 3, including the commission ceiling. They never move a selection, so letting them run during a basis or finding pause cannot advance the chain (needed by J6, where the review line checks E2 after the E1 r6 save has paused the commission). Single jobs (`request_job`, `request_rewrite`, `request_repair`) have no commission gate.

**Pause requests.** `pause_commission` and `mark_feedback(apply=remaining)` do not set `paused` while a draft job is `claiming` or `sent`. They set `pause_requested` (`author` or `feedback`), which takes effect at the commission's next checkpoint, the moment after the in-flight draft imports (step 6 "Checkpoint"). Because chain jobs are sequential, no other draft job can be frozen meanwhile. With no draft job `claiming` or `sent`, both commands set `paused` immediately (with `pause_reason` `author` or `feedback`), and a `frozen` draft job then fails its claim-step recheck and becomes `not_sent`.

**Recovery across two databases** (no atomic commit exists between them). The runner considers only ledger rows whose `story_id` is its own story; it never touches, releases or classifies another story's or project's row.

| Story job state | Ledger row (this story) | Recovery action |
| --- | --- | --- |
| `frozen`, no ledger row | none | Nothing sent; job stays frozen; commission paused (`recovered`) |
| `frozen` or `claiming` | `reserved`, `dispatched=0` | Demonstrably unsent: audited `release_undispatched`; job `not_sent`; commission paused |
| `claiming` or `sent` | `reserved`, `dispatched=1`, no receipt | Ledger row and job `uncertain`. Never resent. Author may `resolve_uncertain` |
| any | settled receipt with output | Import once per step 6. The ledger receipt retains the output text, including retained non-eligible text (step 5), so a crash between settle and import loses nothing |
| any | `uncertain` with receipt above reservation | Liability retained; blocks all new reservations until resolved |
| **no job with that `ledger_operation_id`** | `reserved`, `dispatched=0` | Orphan from a restored or copied story file: audited `release_undispatched` with reason `orphan` |
| **no job with that `ledger_operation_id`** | `reserved`, `dispatched=1` | Ledger row `uncertain` with reason `orphan`; never released |
| — | row of another story or project | Ignored by this runner |
| — | legacy-imported row (`story_id` NULL) | Classified once by `migrate --ledger` (04 §6.4): `reserved, dispatched=1 → uncertain`, `reserved, dispatched=0 → released`; never touched by a runner afterwards |

**Ledger authority (owner decision B4).** One application ledger per user at `%LOCALAPPDATA%\serial-story\ledger.db` (POSIX: `$XDG_DATA_HOME/serial-story/ledger.db`), outside any code tree, shared by every project and story. `project_id` and `story_id` are columns of every ledger row; there is never a ledger file per project. `ledger_meta.cap` is `CHECK (cap = 1000000)`, and code uses the constant `CAP = 1_000_000`, so the USD 1 ceiling is the whole application's ceiling and cannot be raised by data. The file is created only by explicit `init_ledger` or `migrate --ledger`; `create_project` registers a `ledger_project` row inside the existing ledger and never creates a file. A missing ledger for a story whose jobs reference ledger operations fails closed. Copying code or story files resolves the same ledger. The legacy `local/merge-project-ledger.db` is imported once by explicit migration, with its SHA-256 recorded; it is never deleted.

**Ledger states:** `reserved → succeeded | uncertain`, `uncertain → resolved_conservative`, `reserved (dispatched=0) → released`. `resolve_uncertain` sets `spent = max(reserved, reported_charge)`, `reserved = 0`, keeps the receipt and the author's reason. Both `resolved_conservative` and `released` are terminal. v1 has no provider receipt lookup, so no "late receipt" can arrive after `uncertain`; the only exit is `resolve_uncertain`. The commission ceiling is a limit on the sum of its children, never a separate hold.

## 4. Ingestion to source-backed continuation

1. **Capture:** declared kind and authorship; normalize line endings only; keep the import identity and original bytes hash. Without `target_artifact_id` (J0, before any arc exists), `ingest` creates a `fragment` artifact: exploration, never selectable or acceptable. With `target_artifact_id` naming an episode artifact, it creates a revision of that episode (`origin=imported`) and moves the selection only if the payload says `select: true` with the expected `selection_cas`; this is an author action, not an automatic pointer movement. A fragment becomes episode text by `save_revision` on the episode with `origin_ref` = the fragment revision (blocks mapped by unique hash, §2).
2. **Version:** blocks and immutable source hash per revision (§2 producer).
3. **Provisional reading:** none required. Pending memory is never invented; linked drafts use full predecessor text.
4. **Finalize:** acceptance stores the exact saved revision text. Extraction from an earlier generated revision is never reused unless source hashes match exactly.
5. **Promote:** leased outbox tasks read exact canon source. A result whose source is no longer current canon is stored `obsolete` and covers nothing. An expired lease on a `sent` task becomes `uncertain`, never resent.
6. **Revise history:** committing a change set writes `superseded` `v1_claim_status` rows for claims from replaced sources (claim rows are never updated, §2), invalidates snapshots whose `through_ordinal ≥` the earliest changed episode, opens canon-change impacts (§2 "Effective basis") and claim-change impacts (below), and queues new tasks. Unchanged quoted sentences in a changed source are re-extracted too, because surrounding meaning may have changed. Tasks queued by a change set start `awaiting_authority` (01 §2 memory line).

**Claim dependencies.** Claim and source items in `v1_context_item` are dependencies of the job that consumed them and of every revision whose effective basis comes from that job. In the same transaction that makes a claim `superseded` or `rejected` (by `interpret`, `resolve_finding(reinterpreted)` or `commit_change_set`), the writer opens a `v1_impact` with `cause_kind=claim_change` on every currently selected or accepted revision whose producing job consumed that claim, and, for a change set, every one whose job consumed a replaced source as an exact-text item. Such an impact pauses dependent continuation past it like any impact. It closes by `revalidate` with payload `claim_id` (the author attests the prose still fits the corrected reading; recorded as the impact's state change and event, not as a `v1_basis` row), by a repair, or when the flagged artifact's selected revision is replaced by one whose job did not consume the superseded claim. It never changes prose or unaccepts. Revisions with no job have no claim dependencies; they are covered only by the effective-basis rule.

### Context recipes

Every recipe freezes adopted versions, items with hashes, omissions, temporal boundary, mode and input hash. **Boundary** = the narrative point of the operation's target, never the manuscript endpoint. Later material enters only as labelled `protected_outcome` items, never as character or reader knowledge.

| Recipe | State-asserting | Mandatory items |
| --- | --- | --- |
| `converse` | No (claims about the story cite sources) | Target revision, selected messages, governing direction shown separately |
| `arc_planning` | Yes | Skeleton, purpose/end state, accepted context to boundary, open promises, applicable feedback |
| `sequential_draft` | Yes | Skeleton, arc intention for the slot, accepted context to boundary, exact selected predecessors since the accepted boundary, locks, kept passages, active style notes, feedback |
| `polish_rewrite` | No | Target blocks, one neighbour block each side, locks, voice notes. Discloses "no story state supplied". A reason mentioning plot, motive, knowledge or a contradiction is refused as polish and must use `story_rewrite` |
| `story_rewrite` / `repair` | Yes | Full target episode, requested change, prefix context to boundary, later dependent passages as protected outcomes |
| `promotion` | Yes | Exact final source, claims to its boundary, claim vocabulary |
| `review` | Yes | Target revision, frozen direction, server-assembled packet to boundary |

**Accepted context to boundary B** for a state-asserting recipe:

- *Indexed* when a `complete` snapshot covers every canon source before B: snapshot claims plus essential passages.
- *Exact-text fallback* otherwise: the complete snapshot through ordinal *k* (or nothing), plus **every accepted source from *k*+1 up to B, untruncated**, excluding claims and summaries derived from sources changed after *k*. The receipt lists missing coverage and hashes and the desk says "Memory updating; using exact accepted pages."
- *Blocked* when mandatory items exceed **100%** of the route's qualified `max_input_tokens` under the existing strategy (UTF-8 bytes + 1,024; `authoring.py:87`), or an open conflict (open impact or current serious finding on a revision before B) sits before B. The 85% figure below governs optional fill only: the bytes-based estimate already overcounts tokens, and blocking mandatory items at 85% would end exact-text fallback earlier for no safety gain. The refusal names the offending items. It fires **before** any reservation. The author can narrow, split, update memory, or choose a separately qualified route. No silent truncation, summarization or model switch.

Optional items are added in fixed priority order (feedback, kept passages, style notes, neighbour summaries) until a recipe budget of 85% of the qualified input bound; dropped optional items are listed as omissions.

### Review packet (no adaptive tool loop in v1)

The server assembles a packet for one review job: target text, predecessors to the boundary, claims with citations, open threads, up to 12 cited passages and at most 24,000 returned Unicode scalars. Each included or omitted item writes a `v1_tool_read` row. Findings disclose coverage, confidence and omissions. A review job has no capability to write prose, canon, pointers or files, and cannot read other stories, the filesystem, SQL, URLs or credentials. Story text is inert data. Real-world claims are flagged "not verifiable here".

A finding binds the target revision hash. It blocks dependent continuation only while that hash is a current selection or canon. Otherwise it is shown as "about an older version". A late serious finding on an accepted hash opens `v1_impact` and pauses commissions past it; it never unaccepts.

## 5. Migration

Explicit `migrate` command, transactional, after writing a non-overwriting copy of the database file beside it. Steps and the cutover checklist are in 04 §6. Rules:

- Preserve legacy IDs through a mapping table and preserve accepted text byte-for-byte (no `_bounded` normalization, `studio/store.py:61–66`). If `episodes.accepted_text` and `memory_sources.final_text` differ for any episode, stop and report.
- Pending, rejected, receipts, feedback versions and provenance carry over. Mutable draft history is lost: set `history_start` and never invent earlier edits, consumption or adoption.
- Legacy facts become `legacy_unclassified` claims with original confirmation. Approved plans stay historical intent; they are not adopted skeletons until the author adopts.
- After cutover `v1_canon` is the only writer; legacy mutation paths, including CLI acceptance, refuse migrated stories. Snapshot, export and studio read through the canonical adapter without writing.
