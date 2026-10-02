# Sol 6.1 authoring recovery report

## Outcome and boundary

Implemented and exercised the offline/manual authoring slice. This is **synthetic workflow material**, not real-model prose-quality evidence or a production certification. Paid Merge generation remains OFF. No existing review database/assets, credential files, private scripts, global settings, skills or memory were modified. No live provider/network request, delegation, installation, commit, server restart, publication or deployment was performed. Test servers used new temporary databases under local/test-runs.

The parent owns real Edge QA/screenshots and live authenticated catalog GET. I did not launch a browser, restart the parent's servers, or certify visual quality.

## Implemented behavior

- New HTTP Generate and Revise actions invoke the canonical FakeProvider through the existing operation/accounting seam. Frozen context includes approved intention, canonical memory/history selection, saved writer prompt, word limit, saved parent prose and scoped feedback. Synthetic output includes a deterministic request fingerprint and feedback text. This demonstrates consumption, not semantic rewriting quality.
- This-revision feedback applies to that source revision. Series feedback also enters future requests. Each note records its exact source text version. Draft run records preserve immutable source, settings, approved plan, parent revision/version, frozen prompt, feedback IDs/notes and context selection. Reset writer instructions persists the default and advances its version.
- Manual prose is recorded as manual with no model attribution even when Merge is selected. Author-edited synthetic final prose retains its original synthetic lineage and explicitly records the edit plus final-text hash.
- Acceptance requires saved text version plus loaded history/memory/plan/settings/feedback versions. It also checks the draft's original plan/configuration basis. Canonical acceptance, accepted final text/memory source and the immutable acceptance receipt commit together. Exact original retry returns the original receipt; a different retry refuses. A receipt-insert failure regression proves canonical rollback.
- Plan responses expose the full 200-beat content, established read-only intentions and editable future intentions. Saved plan versions cannot rewrite accepted intentions. More than 200 supplied beats and non-boolean unplanned flags are refused.
- The desk preserves dirty manuscript, settings, plan, feedback, registry and fact inputs during refresh. Dirty forms retain their ORIGINAL loaded versions rather than rebasing to unseen edits. A saved-copy comparison panel and explicit discard-all-unsaved action provide conflict recovery. Saving pasted prose never inserts a placeholder. Accept/reject clear the selected prose and next-episode state on success.
- Memory has actual registry and fact proposal forms, exact accepted source inspection, proposal evidence, separate confirm/reject actions, and no Confirm for rejected facts. Acceptance receipts remain explicitly memory-not-reviewed. No automatic semantic extraction is claimed.
- The studio serves the incumbent review stylesheet, which was previously missing from its fixed routes. It preserves the bundled IBM Plex Sans and editorial tokens. HTML and model content render through textContent, not HTML.
- Mutations require exact same Origin/Host, session capability and JSON content type. Duplicate security/framing headers, transfer encoding, JSON duplicate keys/constants, malformed/oversized bodies are refused. Network bodies are read outside the write lock with a 1.5-second total deadline and 0.5-second idle timeout. Oversized refusals use only a 0.15-second bounded post-response drain to deliver the response on Windows, never the arbitrary declared length.
- Read-only studio reads use mode=ro and never initialize canonical/studio/memory/budget schemas. A missing database returns an empty read-only state without creation. Existing canonical-only database bytes remain unchanged. The original read-only review server and routes are unchanged.
- Merge catalog origin is https://api-gateway.merge.dev. Discovery uses model, not id, strict typed public vendor/price/limit metadata, bounded pages/models/responses, repeated cursor/model refusal, and exact single-model-object lookup. Listing scope is explicitly not global inventory. The page loads selectable model/vendor metadata and displays its current rates/units/limits before saving selection.
- Removed the permanent chat stub. The separate MergeChatContract has a narrow bounded non-streaming request/response exchange, tested only with injected synthetic transport. Runtime transport itself allows model GET only. No paid path can read a key or call a transport while disabled.

## Intentional HTTP contract changes

New draft save: `{text, basis}`. Generate: `{basis, operation_id}`. Revise: `{basis, operation_id, revision_id, expected_text_version}`. Feedback: `{basis, revision_id, expected_text_version, scope, note}`. Acceptance: `{basis, revision_id, expected_text_version}`. The basis contains exactly history_revision, memory_revision, plan_id, settings_version, feedback_revision and next_episode. These required version fields strengthen the original weak studio tests; they are not optional compatibility fallbacks. Canonical CLI signatures and all original 56 baseline tests remain intact.

Generation operation IDs deduplicate identical original HTTP retries in SQLite. The UI currently creates a fresh operation ID on a new click; after a lost response the author must refresh and inspect the pending result rather than blindly re-clicking. Pending-draft refusal prevents creating a second initial draft.

## Touched files

- serial_story/repository.py: backwards-compatible read-only open and nested savepoint transaction composition.
- serial_story/studio/store.py: settings, plan bounds/history, feedback versions, offline generation, immutable run/acceptance records and CAS.
- serial_story/studio/server.py: new actions, consistent state/source inspection, read-only connection path, fixed stylesheet route, bounded HTTP validation.
- serial_story/studio/merge.py: corrected discovery and unconnected injected chat contract.
- serial_story/assets/studio.html, studio.js, studio.css: working desk controls, dirty-form preservation, model/vendor metadata, source and receipt inspection.
- tests/test_studio_workflow.py, test_studio_boundary.py, test_merge_gateway.py: strengthened actual HTTP/SQLite tests and synthetic transport contracts.
- tests/studio_dom_test.js: behavioral headless DOM conflict test, not browser QA.
- docs/AUTHORING-SOL61-REPORT.md: this report.

## Evidence

Retained logs: local/test-runs/sol61-recovery-20261002-01/.

| Slice | RED | GREEN |
| --- | --- | --- |
| Acceptance CAS | 01-accept-red.log (missing loaded basis) | 01-accept-green.log |
| Generate/feedback/revise | 02-generation-red.log (404) | 02-generation-green-fixed.log |
| Full saved/historical plan | 03-plan-red.log (missing content) | 03-plan-green.log |
| Read-only creation / Origin | 04-boundary-red.log, 04-origin-red.log | 04-boundary-green.log plus 04-drain-green.log and full-suite.log |
| Correct Merge schema | 05-merge-red.log (missing injected key seam) | 05-merge-green.log |
| Dirty forms retain original versions | 06-ui-red.log (no working refresh action) | 06-ui-green.log, ui-final.log |
| Vendor/manual provenance/reset | 07-settings-red.log (vendor refused) | 07-settings-green.log |

The first generation GREEN run exposed a Windows test connection cleanup error, retained in 02-generation-green.log. Closing that test-owned SQLite connection fixed the error without changing assertions. The first HTTP GREEN run exposed oversized-response delivery failure on Windows, retained in 04-boundary-green.log. A bounded drain fixed it, verified by 04-drain-green.log and the full suite. Additional rollback/adversarial/chat-contract tests passed on their first run, so they are validation evidence, **not** strict RED-to-GREEN evidence. Strict per-function TDD coverage is not claimed.

Fresh full offline result: **90 tests passed in 82.293 seconds**, full-suite.log. This includes all original 56 baseline tests and strengthened studio tests. Node syntax check passed for studio.js; ui-final.log records passing dirty prose/settings/plan/feedback preservation with original versions after refresh/conflict. No tests were weakened to obtain screenshots.

Independently runnable from PowerShell:

```powershell
Set-Location 'C:\Users\ayan1\Downloads\serial-story-studio'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
node --check serial_story/assets/studio.js
node tests/studio_dom_test.js serial_story/assets/studio.js
```

Parent launch example, only with a NEW chosen database and an unused port:

```powershell
.\.venv\Scripts\python.exe -m serial_story.studio_web --db local/test-runs/NEW-parent-qa/story.db --enable-writes --port 8766
```

Parent may separately add --enable-merge-catalog with its already configured environment after choosing to perform the authorized GET. No paid startup flag exists.

## Incomplete acceptance/release gates, do not certify

1. **Real paid provider integration is incomplete and deliberately blocked.** No live route/vendor semantics, tokenizer/context accounting, current price expiry, provider usage/cost reconciliation or project-shared reserve/settle/uncertain budget integration is connected to runtime. Local fake accounting is not provider-side billing enforcement. The chat wire contract is an offline planned contract, not implemented paid runtime support.
2. **Live catalog schema confirmation remains with parent.** Synthetic tests match the schema facts supplied in the task. The public metadata allowlist supports named scalar/nested pricing and limit fields, but live vendor field names and routing identities still need verification. Unknown fields are dropped rather than interpreted, and missing metadata never enables generation. No live completeness/access/pricing claim is made.
3. **Browser QA/screenshots/Premium Test not performed.** Parent must exercise 390/768/1440 layouts, keyboard focus, real select behavior, loading/error states, save/reload, rejection and next-episode navigation, feedback revision and memory source forms. Premium Test score: not assessed, no screenshot. Built and headless-tested, not visually certified.
4. **Additional hardening remains.** Rejection currently uses canonical rejection but does not require text-version CAS at the HTTP route. Memory mutations use canonical atomic validation but lack a separate optimistic memory-form review version. Plan feedback remains an API-only supporting action, not a visible form. Independent security review is still a release gate. These gaps must not be described as complete.
5. **Conflict UX is conservative.** Dirty forms never rebase. The explicit recovery action discards all forms after confirmation; there is no three-way merge. Copy work before loading saved copies. A plan/settings change invalidates the earlier draft; reject and create a fresh draft to use new directions.
6. The per-function strict TDD gate was not fully satisfied for supplementary contract/hardening code, although the key vertical defects have retained RED/GREEN proof and all 90 tests pass.

No production/public release approval is implied. Stop here for parent independent rerun, live catalog verification and real Edge author-journey review.
