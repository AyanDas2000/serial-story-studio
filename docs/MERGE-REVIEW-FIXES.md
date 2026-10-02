# Merge independent-review corrections

## Status and authority

Offline implementation and regression evidence only. **Independent HOLD and LIVE_HOLD remain.** Parent owns independent test execution, actual Edge screenshots and frozen-source re-review. No live provider qualification or production readiness is asserted.

Historical evidence is unchanged: `C:/Users/ayan1/AppData/Local/hermes/data/droid-bridge/story-authoring/merge-review-811155f4f8/result.md` and the existing initial integration report. The fix plan is `docs/MERGE-REVIEW-FIX-PLAN.md`.

## Exact changes

- `serial_story/studio/authoring.py`: production routes cannot preflight without a trusted Python-only `qualification_supplier(model, vendor)`. No HTTP field, startup Boolean, absent reasoning metadata or catalog access supplies qualification. The contract must explicitly qualify input/output bounds, `utf8_bytes_plus_1024`, `max_tokens_total_billable`, supported maximum input/output tokens, observed per-million price fields, disabled reasoning and an integer account fee bound. No supplier is installed in production. Missing/unknown reasoning and vendor/model-level default reasoning refuse. Synthetic injection is not provider evidence.
- `serial_story/studio/merge.py`: preserves complete pricing snapshots, including nulls and unsupported schedules, and separate caching metadata. Known unselected batch/flex/priority/ultrafast schedules remain inspectable and fingerprinted, but do not affect standard-tier reservation. Non-null unsupported standard schedules and separate caching schedules refuse. Both observed unit labels use explicitly qualified `*_per_million` fields, not inferred multiplication; ambiguous alternate fields refuse. All four input/output/cache-read/cache-write rates are required, never defaulted to zero. Reservation covers the greater of input plus cache-write and cache-read exposure, plus output and the supplied fee bound.
- Runtime charge extraction is independent of prose validation. `accounting_verified`, `output_eligible` and `output_disposition` are separate receipt fields. Only complete `finish_reason=stop`, bounded text without refusal or tools is eligible. Rejected tool/nontext/truncated/filtered/refused output retains verified costs and fees and settles the charge without saving prose. Invalid route/usage retains reported charge evidence but remains uncertain. Missing/null cost or fee never becomes zero or settlement.
- `serial_story/budget.py`: over-reservation receipts retain actual reported exposure as the held amount, block new dispatch and remain uncertain. `confirmation` is durably stored with the original reservation, not reconstructed from the newest preflight. New ledger initialization supports this column; no existing/private ledger was opened in this work.
- Final source CAS and expiry run after metadata and credential preparation. SQLite `BEGIN IMMEDIATE` remains held across reservation, ownership claim and provider exchange, coordinating writers across connections/processes. Expiry is checked again after the ownership claim before POST. If expiry occurs during reservation, no POST occurs; the durable reservation remains held for explicit inspection rather than automatic retry. This is conservative at-most-once dispatch, not exactly-once delivery.
- Frozen payloads, confirmation payloads, qualification results and runtime request snapshots are deep-copied before callbacks. A metadata/key callback cannot rebind the original operation or change wire/receipt identity.
- Recovery filters by workspace before `LIMIT 50` and returns the original persisted confirmation. Rejected output has no recovery confirmation. Older ledger records without original identity are not guessed.
- `serial_story/studio/store.py`: read-only legacy feedback selects available columns and supplies compatibility source version 1 without migration or writes. Accepted-history and acceptance behavior is unchanged.
- `serial_story/assets/studio.js`, `studio.html`, `studio.css`: concise model/vendor/standard-tier, input/output token limits, USD reservation, shared remaining USD, fee note and no-retry warning precede confirmation. Full frozen instructions/prices remain inert text behind collapsed Inspect details. Edit epochs invalidate late async preflight results, including edit then discard. Acknowledged confirmation clears consent. Call review distinguishes settled, reported and held USD; unknown charge stays unknown.
- Baseline synthetic fixtures now explicitly supply test-only qualification, nonreasoning metadata, all four prices and successful completion reason. Existing 111 test methods and their protection assertions remain; none were removed or loosened. The parent's corrected `include_routing_metadata` and its exact wire assertion remain unchanged.

## Executed RED to GREEN evidence

Vertical behavior slices were executed before their corresponding fixes:

| Slice | Observed failure | After fix |
|---|---|---|
| Qualification | Unqualified route did not raise `StoryError` | Pass |
| Pricing | Reservation 35,935 understated expensive cache-read exposure | Pass |
| Charge/prose | Tool output lost the reported receipt | Pass for tools, nontext, length, content_filter, refusal, invalid usage/route and overcharge |
| Preparation/CAS | Settings changed through a second connection, but POST was recorded | Pass: no POST and no reservation |
| Story lock | Second connection wrote during POST; transport assertion was sanitized into uncertain call error | Pass: second SQLite writer is locked during exchange |
| Copy boundary | Caller mutation changed frozen settings version from 2 to 999 | Pass |
| Recovery | Global limit hid recovery; separate run returned newer, wrong confirmation | Pass after 51 unrelated calls and reopened ledger |
| Legacy compatibility | SQLite `no such column: source_text_version` | Pass with identical bytes and schema |
| Async consent | Late preflight resurrected discarded consent | Pass |
| UI checks | Initial new DOM test expected undefined `open`; corrected to assert actual collapsed false. Baseline DOM fixture lacked new required summary fields and failed; fixture supplied them, protection assertions retained | Pass |
| Final expiry | Expiry advanced during ownership claim, but confirmation dispatched | Pass: no POST |
| Model reasoning | Model-level default reasoning did not raise | Pass |
| Callback identity | Metadata callback changed returned operation to mutated-action | Pass |
| Nested prices | Cache-duration schedule was sanitized away | Pass: preserved and refused |
| Accounting display | Uncertain overcharge displayed only charged 0 micro-USD | Pass: reported and held USD 2.000050 visible |

Two actual synthetic story databases were then exercised through real repository/store/controller paths and separate ledger connections. One confirmation paused during dispatch; the other story was refused while the first reservation was unresolved. After settlement the second original confirmation succeeded. Reopening retained combined spend 800,100 micro-USD, remaining 199,900, workspace-isolated recovery, one pending draft per story, no accepted prose and no advancement. An additional 200,000 reservation refused. This already-supported accounting behavior needed proof, not a code relaxation.

Initial unchanged full-suite attempt reached the 90-second command timeout, with no completed result. It is not counted as a baseline pass. A later intermediate run passed 123 tests. Final verification after the last source edit:

- `.venv/Scripts/python.exe -m unittest discover -s tests -p test_merge_review_fixes.py -v`: **14 tests, 8.416 seconds, OK**.
- `.venv/Scripts/python.exe -m unittest discover -s tests -v`: **125 tests, 103.954 seconds, OK**. Includes all 111 baseline tests plus 14 review regressions.
- `node --check serial_story/assets/studio.js`: exit 0.
- Native Node `studio_dom_test.js`, `studio_race_test.js`, `studio_merge_test.js`, `studio_merge_review_test.js`: all exit 0. These are synthetic DOM tests, not actual Edge validation.

## Durable proof paths

All final command output is under `local/test-runs/merge-review-fixes-20261002/`: `targeted-final.log`, `full-final.log`, `node-syntax.log`, and each `studio_*test.js.log`. The initial qualification RED/GREEN logs are retained. Other RED outputs were observed in-session and enumerated above, not retroactively presented as captured log files.

Actual database proof: `local/test-runs/merge-review-fixes-20261002/actual-databases-proof.json`, with exact paths, row counts, spending and SHA-256 hashes. Latest retained two-story files:

- `C:\Users\ayan1\Downloads\serial-story-studio\local\test-runs\merge-review-fixes-20261002\synthetic-_2bhb3ev\story.db`
- `C:\Users\ayan1\Downloads\serial-story-studio\local\test-runs\merge-review-fixes-20261002\synthetic-_2bhb3ev\story-two.db`
- `C:\Users\ayan1\Downloads\serial-story-studio\local\test-runs\merge-review-fixes-20261002\synthetic-_2bhb3ev\ledger.db`

## Self-review and remaining gates

Source review checked callback identity, SQLite writer ownership, receipt settlement before story persistence, exact confirmation fingerprints, retained `include_routing_metadata`, inert DOM sinks and existing server permission controls. No network, credentials, environment values, auth/config files, private database reads, dependencies, shared settings, other workers, commits or existing server restarts were used. Existing 8765/8766 and protected fixtures remain untouched.

Live writing remains fail-closed until independently qualified account/fee terms, tokenizer/framing input bound, total billable output and reasoning semantics, route entitlement, standard pricing schema and transport behavior are supplied through trusted code after separate authorization. Socket timeout remains a socket timeout, not a proven total DNS/slow-drip deadline. Crashes after dispatch claim cannot be retried automatically. Uncertain accounting requires explicit reconciliation. A long exchange holds the story writer lock deliberately; there is no new automatic retry policy.

Actual Edge screenshots, responsive pixel review and Premium Test score were not executed by this worker. Parent owns these; no screenshot or design-audit completion claim is made. Installed Impeccable Operate and craft-floor references and local design tokens were read; the unavailable launcher was not installed.

This artifact cannot clear the independent HOLD. Green tests do not waive source findings.
