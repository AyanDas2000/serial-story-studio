# Writer loop, states and authority

This is the intended storyboard, not a claim that these states exist today.

| Checkpoint | Writer sees and does | Authority and receipt |
| --- | --- | --- |
| Episode direction | Purpose, stakes, active cast, last hook, relevant accepted evidence, scoped feedback and intended reveal boundary. Review included and omitted context. Primary: Approve episode direction. | Save versioned intention separately from established history. Freeze the approved basis. |
| Draft authorization | Exact request and source, model/route if applicable, input/output bounds, reservation and shared remaining allowance. Primary: Confirm one request, only when permitted. | Call consent is not prose acceptance. Manual and synthetic routes are separate explicit choices, never silent fallbacks. |
| Draft pending | Candidate prose dominates. Always-visible provenance and incomplete/stale status; source/context details on demand. Edit without losing saved copy. | Candidate is not canon. Preserve request, candidate, saved version and human edits. Disable acceptance when unsaved or stale and explain why. |
| Feedback saved | Selected passage, requested change, target revision, scope and reason. Primary: Save feedback, then Review revision request. | A line edit applies to that revision; a series direction persists until explicitly retired. Neither becomes a fact. |
| Revision pending | Prior version and changed passages reachable without losing reading position. Writer checks whether the requested change worked. | New candidate retains parent and feedback lineage. Do not overwrite accepted history or claim feedback applied merely because it was appended to text. |
| Prose accepted, memory pending | Immutable final prose and its revision. Primary task switches to Review story changes. | Acceptance says “these words are final,” not “all memory is correct.” Restart resumes this checkpoint. |
| Memory review | Additions, changes, supersession and promises with exact final passages; claim kind, attribution and uncertainty. Show remaining review work. | Writer confirms interpretations or records explicit no-change against that final revision. A quoted report is not objective truth. Do not infer extraction completeness from confirmation. |
| Ready for next episode | Confirmed memory receipt, continuing feedback, prior hook and next intended purpose. Primary: Review next episode direction. | Enable normal continuation only after durable completion. Any degraded continuation requires separate authorization and persistent risk labeling. |

## Complete state coverage

For each checkpoint document empty, initial loading, working/saving, success and failure, plus applicable:
- Unsaved prose or forms: keep inputs, saved copy and original version; never refresh over them.
- Stale basis: explain which direction/history/memory changed, preserve candidate and offer explicit re-review. Do not auto-regenerate.
- Rejected draft: outside accepted history; no story advancement.
- Partial/refused output: incomplete candidate or retained receipt, never eligible final prose by default.
- Uncertain call: keep reservation and uncertainty; no automatic retry or fallback. Recover saved output only without another call and with a matching receipt.
- Budget exhaustion: pause paid work; preserve reading and editing. Do not replace model output with synthetic material to claim success.
- Restart: restore pending candidate or pending memory task, not a fresh draft.
- No memory change: explicit revision-bound decision, not an empty list interpreted as completion.
- Unsupported secrets/chronology: show the limit and stop the unsupported action; do not invent certainty.

## Tailored bad / good interactions

| Bad | Good |
| --- | --- |
| “Generate episode” beside a 200-line plan with no local goal. | “Episode 7: make Ivo suspect Mara, but do not reveal the survivor.” Review this intention and context before authorizing a draft. |
| “Draft generated” over deterministic prose. | “Synthetic workflow material, not model writing.” A real result shows actual source/model receipt; pasted material says “Pasted prose, origin not verified.” |
| Feedback “Make Mara less honest” silently becomes world truth. | Select her claim, request a more evasive answer, choose this-revision scope; separately decide whether a future direction should persist. |
| “Revision complete” because feedback text was appended to a fixture. | Preserve both candidates and the targeted feedback; the writer inspects the changed conversation before judging whether revision succeeded. |
| “Accept and continue” advances to Episode 8 while memory is pending. | Accept final words once; show “Episode 7 accepted. Review its story changes before Episode 8.” |
| Source “Mara said the captain died” becomes `captain = dead`. | Propose “Mara reports the captain dead,” attributed to Mara, cite the final passage, and mark actual survival unknown unless separately established. |
| Green “All clear” after confirming two proposals. | “2 changes confirmed; 1 unresolved. Confirmation does not establish that every change was found.” |
| Restart triggers another paid draft. | Resume the saved candidate or memory task. Where a successful charged receipt already exists, inspect/recover it without generating again. |

## Provenance language

Use separate origin and editorial-status fields:
- **Synthetic workflow material:** deterministic/local fixture; never writing-quality evidence.
- **Pasted prose:** supplied through the manual route; authorship/model origin unknown unless explicitly supplied and evidenced.
- **Model-produced candidate:** provider receipt, exact model/route, request identity, completion and accounting evidence required.
- **Human-edited model candidate:** original model receipt plus final version and edit lineage.
- **Accepted final prose:** approval status, not an origin label.

`synthetic: false` is insufficient: the existing manual route uses it too. Show provenance near the prose, not only inside raw receipt JSON.
