# Independent product-idea review: Droid / Opus 5.5

Scope: review of the prepared product proposal, not app inspection, security certification, implementation approval or release clearance.
Date: 2026-10-01. Native CLI version: 0.230.0. Requested and session-verified model: `claude-opus-5-5`; high reasoning. New session: `2cd59c56-f919-45c6-880d-35963b58c683`.
Result: CLI success, exit 0, nonempty result; owned process cleanup verified. No fallback or automatic retry. Existing native Droid allowance used separately from the USD 1 story-generation budget.
Input: initial `PRODUCT-VISION-PROPOSAL.md`, SHA-256 `a562ce9e4521cd93d9e2868009683d6d82fee59e7a250a1f6e3ad9b3d1428d86`, plus scoped context. The revised product-direction document is the parent's synthesis afterward, not a second reviewed draft.

Raw usage counters (scope retained as returned, not converted to dollars):
```json
{
  "input_tokens": 4,
  "output_tokens": 6891,
  "cache_read_input_tokens": 0,
  "cache_creation_input_tokens": 23818,
  "factory_credits": 102771,
  "thinking_tokens": 2081,
  "ttft_ms": 2255
}
```

## Reading this review

The reviewer is advisory. Its broad comparisons with other tools were not independently researched. Its proposed assertion-mode vocabulary does not by itself establish truth; narrated prose can also be unreliable. Its proposed review-item cap is a hypothesis, not a reason to discard important changes. Its manual/human-prose route is useful for product testing but must not be represented as satisfying a requirement for model-generated demonstration material.

## Subsequent code-review status

The separate code review later returned passed=false: zero security concerns and one medium filtered-graph correctness defect. Parent reproduced/fixed it; the separately authorized targeted independent re-review then passed with 32 tests, 17-file compilation and 149 assertions across 31 child processes. This closes the reported code correction only, not the full product or hosted/provider release. The original product reviewer response below is preserved verbatim, including its then-current pending status; this update is not an Opus re-review.

## Reviewer response, verbatim

# Serial Story Studio: product direction review

## 1. Verdict: coherent, but changes are needed

The core direction holds up. You stay the author. The system carries continuity, evidence and workflow state. Most tools that try this either generate everything or become a story database. This proposal correctly rejects both.

Whether it genuinely helps a writer is still unproven. The current build is a strong backend for a loop that no writer has run yet. It has approval, acceptance, history, stale-draft refusal and accounting, but no writing surface. That makes it useful to you as an architecture exercise, not yet as a writing tool. It becomes useful at one specific point: after accepting episode 9, you open episode 10 and can trust what the system says it knows, and why.

Two parts of the thesis overreach:

- **"See the consequences of a change before approving it."** This needs dependency tracking between facts, threads and planned episodes. Nothing in the slice supports that. Drop it from the thesis until invalidation actually works.
- **"Understand what the story has established."** Today the ledger records which source supports a fact. It does not record what kind of claim the fact is (see Must-change 1).

## 2. The strongest interaction and who it is for

The strongest interaction is the **post-acceptance memory delta**. You accept final prose. The system proposes the changes it believes happened, each next to its exact passage. You confirm, correct, or explicitly record "no change." The next episode's brief then shows what the model will be told and what was left out (the context receipt).

This interaction is for a single author of a long serial, at 15 episodes or more. That author forgets what was set up in episode 4 and does not trust a model's implicit memory.

The graph supports this interaction. It is not the interaction. "Why does the system believe this?" is a good secondary feature, and it only matters once the delta review produces facts worth trusting.

## 3. Top five conceptual risks

**1. Treating provenance as truth.** Today a "fact" is backed by an accepted passage. A lie in dialogue therefore becomes canon with a source link that looks authoritative. The fix does not need the full belief model. Each fact needs a minimal **assertion mode**:
- narrated, meaning true in the story world;
- claimed by a character;
- believed by a character;
- author-only setup.

Without this field, every adversarial test involving a lie or rumor fails by design.

**2. Secrets, knowledge and what the reader has seen.** Modeling who knows what for every fact grows combinatorially, and you will spend sessions maintaining it. Limit it to things you designate as secrets:
- a hidden author-only bible entry;
- a list of characters who know it;
- the episode where the reader first sees it.

Ordinary facts do not get knowledge tracking. The rule to enforce is narrow: a secret's text never enters a drafting context unless the brief explicitly authorizes the reveal.

**3. Flashbacks overwriting the present.** A full model of in-world time and valid-time windows is overkill for v1. Use one flag per episode or scene: present or flashback. Facts from a flashback never replace present-state facts. The simplest option is to disallow flashbacks in the 15-episode demo, which is a legitimate creative choice. Decide this deliberately rather than leaving it unhandled.

**4. Extraction coverage.** A review screen only shows what was proposed, so it cannot reveal what the extractor missed. Source-link completeness says nothing about what was never recorded. Coverage has to be measured as recall against hand-labeled expectations from the adversarial corpus. If that is not measured, bulk approval creates false confidence.

**5. Review fatigue.** In fiction, almost everything belongs in the proposal's "high-impact" categories: beliefs, relationships, location and secrets. Mandatory individual review of all of them could take longer than writing the episode, multiplied across 15 episodes. Set a target, such as at most about 8 reviewed items per episode, and measure actual minutes. Also allow an explicit "nothing else changed" attestation, which is stronger and faster than ticking every item.

## 4. The smallest useful slice

**One complete episode loop, run twice, with a restart in between.** It needs:

1. A human-written brief.
2. Draft prose, from the fake provider or written by you.
3. Edit, then accept.
4. A manual memory delta with assertion modes, or an explicit no-change receipt.
5. Scoped feedback.
6. A next-brief context receipt.
7. A restart while memory review is pending, which resumes correctly.

**Change the sequence in two ways:**

- **Move the writing surface earlier.** Reviewing deltas from a command line is not a writing experience, and Milestone C comes too late to shape the domain model. An editable local server adds attack surface you have not reviewed: loopback binding, CSRF protection and path handling. A file round-trip avoids that: export the episode and delta as Markdown, edit them in your own editor, and re-import with a hash and basis check. It also matches how writers already work.
- **Check feasibility before the memory schema.** Once pricing and access are approved, a single bounded preflight call tells you whether USD1 covers model drafting at all. If it does not, the product becomes "human prose, with the model used for memory and briefs, or not at all." Learn that before building typed memory for a model-written workflow.

**Delay:**
- typed chronology and valid-time;
- a general knowledge model;
- the model critic and automatic rewrite;
- generated alternatives;
- consequence preview;
- the conversational patch command;
- graph polish beyond the local-neighborhood view.

## 5. Core workflow

Each episode moves through these states:

| State | What happens |
| --- | --- |
| BRIEF_DRAFT | You write or edit the brief. |
| BRIEF_APPROVED | The basis snapshot (memory, history, directions) is frozen. |
| RESERVED → DRAFT_READY | A charge is reserved and the draft is produced. |
| (edit, redraft or reject) | Rejection keeps the candidate and its feedback. |
| ACCEPTED_MEMORY_PENDING | Final prose is committed. |
| MEMORY_REVIEWED | A delta or an explicit no-change receipt is recorded. |
| READY | The next episode can start. |

**Feedback** is a stored record with: target revision, scope (this sentence, this episode, future until episode N, or standing style), reason, and status (active, applied or retired). Active future-scoped feedback must appear in the next context receipt. The author either carries it forward or retires it. It never silently disappears and is never recorded as a story fact.

**Approvals that can be combined:**
- Brief approval with context-receipt review, because both answer "what is the model told?"
- Brief approval with authorizing a stated maximum reservation, because it is the same decision moment and shows an explicit amount.
- Batch confirmation of low-risk narrated facts.

**Approvals that must stay separate:**
- Prose acceptance and memory confirmation. Accepting text and interpreting it are different kinds of authority. They can sit on one screen, but prose must be committed first.
- Degraded continuation. It is always its own named decision.
- Edits to history. These are never part of a future-direction change.

**Failures:**
- *Provider error or timeout:* the reservation stays marked uncertain until it is settled, the state returns to BRIEF_APPROVED, and a retry needs a new reservation.
- *Partial output:* it is kept as an incomplete candidate and never accepted automatically.
- *Budget stop:* paid calls are refused, and the loop continues manually (human prose, manual delta). The receipts show which episodes were written that way.
- *Crash during memory review:* the system resumes the pending delta.
- *Basis changed after the draft:* the stale draft is refused.

## 6. Demo and evaluation

| Status | Item |
| --- | --- |
| **Requirements** (assignment) | Developed 200-episode arc; 15 sequential accepted episodes; 2 observable interventions; resume after episode 12; recorded spend kept separate from the assistant allowance. |
| **Requirement I am adding** | Disclose how much of the prose and arc was written by a person and how much by the model. Without it, the demo cannot honestly be read. |
| **Code correctness** (testable) | Idempotent acceptance; stale refusal; no duplicate charges; budget does not reset with a new database; checkpoint resume; inert graph labels. |
| **Memory quality** (measurable) | Recall and precision of deltas against the hand-labeled adversarial corpus; lies and secrets do not leak into narrated canon. |
| **Product usefulness** (hypothesis) | Review minutes per episode; time to locate a fact's source; continuity errors found by an independent read-through of all 15 episodes. |
| **Writing quality** (human judgment, not tests) | A short versioned rubric scored by you and ideally one other reader. Passing tests says nothing here. |
| **Unresolved creative choices** | Premise, tone, whether flashbacks are allowed, how much of the arc is hand-authored, acceptable review load. |

A "developed" 200-episode arc can honestly be about 10 to 15 arc bands with turning points, plus one-line purposes per episode, expanded only near drafting time. Labeling it as that is better than claiming more detail.

## 7. What USD1 implies

These implications hold without assuming any prices, models or provider permissions:

- **The ledger location contradicts the requirement.** It currently lives inside one database, so a new database could reset the budget. This is Must-change 2.
- **Paid calls per episode are a design variable, not a constant.** Every critic, alternative, rewrite, extraction and retry competes with drafting.
- **Conservative reservations stop work early.** The system may halt before real spend reaches USD1. That is the right trade-off, but it must be visible.
- **Uncertain timeouts permanently use up allowance** until they are reconciled.
- **The local ledger is not the provider's bill.** Reconcile against a provider-side record if one becomes available, and say so if it is not.
- **Default to no critic and no alternatives.** Add them only if measured spend leaves room.
- **Real-provider test runs count against the same USD1.**

## 8. Revised thesis, next milestone and avoid-for-now list

**Thesis:** *A local tool that helps one author write a long serial episode by episode. After every accepted episode, it records what changed, what kind of claim each change is, and where it came from. It always shows what the next draft will rely on.*

**Next milestone:** run the slice from section 4 twice, with a restart after the first memory-pending checkpoint. Use the fake provider or human prose, and a file-based edit round-trip. Fix the ledger location and add assertion modes. Run 10 hand-labeled adversarial cases. Record review minutes.

**Avoid for now:**
- a full knowledge or belief model;
- valid-time chronology;
- consequence preview;
- automatic retcon repair;
- model critic and automatic rewrite;
- generated alternatives;
- the conversational operator;
- an editable local server;
- graph beautification;
- a workflow framework;
- new dependencies;
- any real provider call without explicit approval;
- hosting, collaboration and publication.

### Must-change

1. Facts need an assertion mode (narrated, claimed, believed, author-only). A source link is not narrative truth.
2. Move the budget ledger out of the per-story database. It must be project-wide.
3. Take "consequence preview" out of the thesis until invalidation exists.
4. Keep prose acceptance and memory confirmation as separate decisions.
5. Measure extraction recall against expectations you label by hand, not source-link completeness.
6. Disclose the share of human-written and model-written work in the demo.

### Optional later

Limited secret tracking with reader visibility, the flashback flag, batch review of low-risk facts, the critic, alternatives, the editable workspace, and graph thread views.

This review does not approve implementation, real provider use or release. The separate independent code review is still pending.
