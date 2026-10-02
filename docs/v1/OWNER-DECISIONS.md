# Owner decisions — recorded 2026-10-02

Source: independent review `10-review`, `REVIEW-FINDINGS.md` (verdict BLOCKED).
Decided by Ayan directly. These bind the next spec-fix stage.

## B4 — spending ledger

**Decision: one shared ledger for the whole application. Not per-project.**

Rationale: a per-project ledger mints a fresh USD 1 per story, so the stated total
ceiling silently multiplies. `docs/PRODUCT-DIRECTION.md:182` calls USD 1 the whole
real story-generation ceiling, so a per-project design contradicts the product's own
statement.

Binding constraints:

- One canonical ledger file for the entire application, per user.
- `project_id` is a row column, never a separate file.
- `cap = 1_000_000` enforced by a CHECK constraint or a code constant, never a freely
  writable column.
- `create_project` registers a project inside that ledger. It must never create a new
  ledger file.
- Recovery must never call `release_undispatched` on another project's row.

Supersedes: `02-DATA-INGESTION-CONTEXT.md` section 3, "Ledger authority" per-project
file design.

## M10 — episode length gate

**Decision (superseded once, on 2026-10-02): target ~700 words for the initial version.**

History of this decision, kept because the reversal matters:

1. First answer was "roughly 20-minute episodes", band 2500 / 3000 / 3800 words.
2. Ayan then judged a 20-minute episode "a huge commitment to begin with" and cut it
   to ~700 words for the initial version.

Current provisional band: floor 550, target 700, ceiling 900 words.

At ~150 words per minute of spoken narration this is roughly a 4-6 minute episode. The
20-minute runtime goal is **deferred, not abandoned** — it becomes a later milestone once
the initial slice has proven the machinery end to end.

This also dissolves most of the review's M10 finding. `docs/PRODUCT-DIRECTION.md:163`
asks for "fifteen sequential accepted 400-700 word episodes"; a 700-word target is
consistent with that again, where a 3000-word target was not. The spec's decision to make
the length check advisory rather than a hard refusal still stands, and is worth keeping:
it lets a deliberately long or short episode through with a recorded reason instead of
forcing the author to abandon a scene they want.

Binding constraints:

- Outside the band: warn, never refuse. The author may always accept an over- or
  under-length episode with a recorded reason.
- No hard refusal on length in v1.
- `repository.py:183` legacy 400-700 refusal behaviour must remain intact for
  unmigrated legacy stories.

## M6 — canon ordinal vs artifact ordinal (parent implementation choice, NOT an owner decision)

**Choice: assign the story-wide ordinal at acceptance time, not at commissioning time.**

Ayan was shown this and said he was unsure how to call it, so the parent made the
implementation choice and flagged it. It is reversible and cheap to change while no
accepted canon exists yet.

The problem in plain terms: an arc's episodes are numbered 1..n inside that arc, but the
story needs one continuous numbering across every arc. Arc 2's first episode is
arc-ordinal 1 and story-ordinal 4. `v1_artifact.ordinal` holds the arc-relative number;
`v1_canon` is keyed on the story-wide number. Nothing currently stores the story-wide one,
so accepting an episode has no value to key canon on. Re-commissioning a different arc
length (J2, "flags affected slots") has no defined reassignment rule either.

The rule:

- Drafting and commissioning use arc-relative numbering. It is provisional, may change
  freely, and nothing durable depends on it.
- Accepting an episode stamps a story-wide ordinal. It is stable from that point,
  because an accepted position must not move when the author re-plans an arc.
- An unaccepted revision therefore has NO story-wide ordinal yet. This is intentional and
  is what makes re-planning safe.
- The uniqueness constraint applies over accepted/live episode canon only, never over
  every artifact row.

Consequences this settles:

- J2 ("flags affected slots"): re-commissioning a different arc length leaves accepted
  story positions untouched and renumbers only the unaccepted tail.
- Narrative points keyed on (ordinal, block ordinal) must use the story-wide ordinal once
  accepted, and must state which one they use before acceptance.
- `v1_canon.episode_ordinal` remains the story-wide position. `v1_artifact.ordinal`
  remains arc-relative. The new story-wide value is stored separately; do not overload
  either existing column, because they are both already load-bearing.

Open sub-question for whoever implements: whether a superseded-then-reaccepted episode
reuses its old story ordinal or receives a new one. Recommend reusing it, so canon
history stays continuous, but this needs stating explicitly in the spec.

## Reconciliation note

`09-backend` is still building against the pre-decision documents. Its output on ledger
scoping and length gating must be reconciled against this file before it is accepted.