# Offline verification receipt

Checked on 2026-10-01. The original 14-test receipt below is preserved as history. Initial independent review of the offline memory slice found one graph correctness defect. After the parent correction, the separately authorized targeted independent re-review passed: 32 tests, 17-file compilation and 149 targeted assertions across 31 child processes. This closes the reported defect; it is not general product/security/provider certification.

## Actual execution
- `uv sync --offline --locked`: isolated local environment, no third-party runtime/dev packages.
- `uv run --offline --locked python -m unittest discover -s tests -v`: 14 tests passed after two export regression fixes; latest final parent run completed in 8.936 seconds. Clock check: October 1, 2026, 10:51:46 IST.
- `uv run --offline --locked python -m compileall -q serial_story tests`: passed.
- Initial features were introduced through failing then passing vertical service/CLI tests; later regression tests exercise rollback, uncertainty and export safety.
- `git diff --check`: passed for tracked diff (currently empty because files remain untracked); it is NOT a review of the new source files. AST parsing and manual review cover the new files.

## Fresh-process walkthrough, not a real story demo
`local/verify_walkthrough.py` launched 12 separate CLI processes. It created a fixture plan, refused drafting before approval, approved it, generated a draft, reopened the same pending review, accepted edited fixture prose, repeated acceptance, exported accepted prose, and read progress/trace.

Observed results:
- 200 indexed placeholder beats. Not a developed story arc.
- 435 words in the accepted edited fixture. Not real model generation.
- Same pending revision on reopen, with one draft attempt.
- Exactly one accepted review event; next eligible episode 2; history revision 1.
- Two recorded zero-cost fake calls: plan and draft.
- Final accepted text reopened and matched the saved text export.
- No observed human interventions are claimed from automated acceptance commands.

Local evidence: `local/verification-evidence.json` contains the actual command receipts and file paths. Fake smoke outputs remain under ignored `local/`. The default `local/story.db` remains available for the user's own first walkthrough.

## Test coverage
1. Accepted episode survives database reopen.
2. Final edited acceptance supplies memory and subsequent recent context.
3. Duplicate acceptance creates no second event, memory update or cursor advancement.
4. Rejection excludes prose from accepted history and requires an explicit new draft.
5. Acceptance refuses prose outside 400-700 whitespace-separated words.
6. Context stays within its configured character limit and refuses essential overflow.
7. Three-attempt fake budget remains exhausted after a fresh process.
8. CLI pending review, edited acceptance and export survive fresh processes.
9. Injected acceptance failure rolls back text, memory, review event and cursor together.
10. Artificial reservation/settlement and uncertain usage survive a fresh process with their original policy.
11. Injected offline timeout leaves no canon and stops automatic regeneration.
12. Different existing export text is never overwritten.
13. An injected partial export write leaves no published destination; retry succeeds.
14. Identical LF and CRLF exports can be repeated without changing bytes.

## Security / EM self-review
No eval/exec or shell=True found by the scoped AST scan of new Python sources. SQL values use placeholders. No HTTP adapter, dotenv loader, SDK, environment credential lookup, remote or public surface exists. Exports use explicit user paths and refuse different existing content. Local data is unencrypted; this boundary is a single-user development scaffold, not a hosted security claim. No high/medium issues identified in the parent's implemented-path review.

Initial independent read-only review found two export defects: partial writes obstructed retry, and universal-newline comparison rejected identical CRLF text. Both were reproduced with failing tests before the fixes. Exports now stage complete text and publish without replacement, and comparison disables newline translation. No security concerns were reported. Follow-up independent review passed with no security concerns, logic errors or suggestions. The reviewer reran all 14 tests and additionally probed fsync failure, publication failure and staging collisions; no blocking regressions were found.

## Git and file boundaries
New local repository, zero commits, no remotes. Ignore rules were exercised for `.env`, `.env.production`, key files, local DBs, raw traces, private input and `.venv`. Private preparation and memory stores were read only where requested and were not copied into the repository. No upload, deployment, portfolio change or submission occurred.

## Not verified / not implemented
A clean-machine under-five-minute installation; a genuine 200-episode narrative plan; real provider token/cost/timeout accounting; full persistent character/fact/thread memory; layered summaries; future directions/beat reconciliation; plan editing; episode-40 repair; episode-150 retrieval; 15 real episodes/two observed interventions; stop-after-12/continue-to-15 real demonstration; screen recording; graphical UI or design screenshot audit. No completion claim applies to these.

## Release Manager
Authorized original scaffold verified, including its independent follow-up review. The later approved memory slice is documented next; the original verdict must not be applied to it. Hold for any product release or submission.

## Approved source-linked memory slice, October 1, 2026
- Latest parent complete suite: **32 tests passed in 36.433 seconds** after the filtered-supersession correction; 17 application/test/preview Python files compiled in memory. The earlier 31-test parent run passed in 22.426 seconds with compileall and locked offline synchronization. No global package changes or additional runtime/dev dependencies.
- New CLI commands provide author setup, accepted-source situations, fact proposal/show/confirmation/rejection, explicit supersession, searches/history, scoped directions, selected-cast context, a consistent storyboard and JSON/HTML graph export.
- Canonical facts require final accepted evidence. Proposed/rejected facts stay outside context; quotes establish provenance, not semantic truth. Old fact versions remain queryable; earlier accepted prose remains immutable.
- A second-writer probe demonstrated a consistent storyboard snapshot and visible pending fact proposals. Essential context overflow stopped before another attempt. A changed direction refused stale-draft acceptance.
- Persistent project ceiling tests cover cross-episode/stage settlement, restart/uncertainty and integer validation. This applies to one ledger/database, not every separate database; real multi-story accounting is a release gate. Real provider spending remains USD 0 because the only used provider is fake.
- Graph fixture created in its own ignored project-local folder: 13 snapshot nodes, 17 edges, five confirmed facts, two future intentions. Initial protagonist-filtered view showed ten nodes. Not a real story demo or observed human intervention.
- Actual native browser checks passed: desktop 1440px; emulated mobile page width 390px with internal graph scrolling; bundled font; keyboard source inspection; no-match/empty/corrupt-file states; script-shaped labels inert; reduced motion; no uncaught runtime exceptions. Network probe was blocked with an explicit connect-src CSP violation.
- Parent manual/static security review: ten application modules, standard-library-only imports, no detected high-risk call/interpolated SQL/credential-literal patterns. Font/license bundle hashes matched their provenance ledger. No broad credential search was performed.
- Framework prose and three rendered diagrams are `docs/FRAMEWORK.md` and `docs/diagrams.html`. Screenshot/DOM inspection caught and corrected a budget-stop arrow: it now returns the saved draft to human review, never directly to memory confirmation. Feedback routes and unique SVG marker identifiers are included.
- Browser receipt: `local/memory-preview-76cf1f82e6fc/browser-verification.json`. Static receipt: `local/security-scan.json`. Checked screenshots in `docs/design/`.
- Initial independent review returned **passed=false**, zero security concerns and one medium correctness finding: dangling supersession edges in location-filtered exports. Parent reproduced/fixed it without changing renderer/UI validation. Separately authorized **targeted post-fix review passed**, with empty security/logic findings: 32 tests in 23.719 seconds, 17 in-memory compilations and 149 assertions across 31 child processes. Source hashes corroborate the reviewed code; exports were independently tested after the fixture-builder process exited, and an in-memory guard mutation reproduced the original defect. Full findings: `docs/SECURITY-REVIEW.md`; independent evidence: `C:/Users/ayan1/AppData/Local/hermes/cache/scratch/filtered-supersession-rereview-20261001-165346-23c6f706/review.json`; parent confirmation: `local/filtered-graph-rereview-confirmation.json`. Two non-blocking test/UI suggestions remain recorded, not implemented. No full vulnerability certification or hosted-release claim.
- Still deferred: real gateway adapter/model/pricing preflight, developed macro arc/premise, episode alternatives and writer/critic loop, automatic memory digestion/coverage gates, typed knowledge/thread/timeline schema, historical repair, editable/storyboard conversation UI, mobile polish and 200-episode graph performance.
- Git remains without commits or remotes. No public repo, upload, deploy, website edit or submission occurred.

## Later local read-only review and provider discovery
Parent-verified extension, not covered by the preceding independent review: local loopback review server, live read-only SQLite observation, six review sections and sanitized Merge model metadata. Current complete suite: **37 tests passed in 42.280 seconds**; JavaScript syntax check passed and 18 application/test modules parsed. Isolated native Edge checks passed at 1440px and emulated 390px, including live refresh, source highlighting, literal malicious labels, CSP egress rejection, meaningful empty/error/shaped-loading states and unchanged original database bytes. New server-disconnect regression passes. Details, screenshots, boundaries and conservative visual audit: `docs/LOCAL-REVIEW-VERIFICATION.md`; restart/use: `docs/LOCAL-REVIEW.md`.

Read-only exact lookup returned `anthropic/claude-sonnet-5-5` and advertised streaming/cache pricing. The returned listing scope is not treated as a complete global catalog. No inference, credential-file searches, key changes or measured cache reuse. CLI/default provider remains fake. Real generation, provider-side/shared-project USD 1 enforcement, web decisions and public release remain gated. Earlier statements about absent GUI/server refer to their historical milestone, not this extension.

