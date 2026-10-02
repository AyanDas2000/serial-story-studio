# Authoring audit fixes, 2026-10-02

## Outcome

Corrected the five requested source/transport findings. Fresh final offline command `python -m unittest discover -s tests -q`: **97 tests, 89.143 seconds, OK**. Native Node syntax check passed. No historical 90-test result is used as current evidence. Node-only DOM tests now run inside Python unittest.

**Independent static HOLD remains standing.** Parent must independently re-review corrected source and repeat browser/network checks. This report does not clear HOLD or claim production readiness. Paid Merge POST remains disabled.

## Exact changes

- `serial_story/assets/studio.js`: acceptance disabled and guarded while setup, prose, plan, settings or feedback is dirty, with actionable save guidance. Acceptance/rejection no longer blanket-clear feedback/plan or overwrite prose typed during a pending response. Each form counts editing events; actions capture its submitted counter. A successful response clears only that captured version, preserving newer input. Dirty forms advance only mutation-acknowledged CAS fields: saved prose version, settings version, plan ID/status, feedback revision. Unrelated dirty memory forms survive refresh. Inputs remain editable and their events remain tracked.
- `serial_story/studio/server.py`: reject requires exact revision/text-version/basis fields (optional note), checks loaded basis and current pending text within the same repository transaction as canonical rejection. Reject intentionally permits a current loaded draft whose original generation settings/plan have changed, so the author can discard obsolete candidates, but never ignores loaded CAS. Canonical CLI rejection signature is unchanged. Plan feedback requires an explicit integer plan ID and passes that ID unchanged to the transactional stale-plan guard. Draft-feedback response supplies the acknowledged feedback revision.
- `serial_story/studio/store.py`: plan-feedback IDs also validated at the store boundary, excluding booleans, floats and strings.
- `serial_story/studio/merge.py`: object-pairs decoding rejects duplicate keys at every nesting level before normalization, including pricing. Capability arrays remain separate from numeric pricing.
- `tests/test_studio_workflow.py`: HTTP stale rejection/missing fields/settings basis regressions, strict legacy rejection payload, explicit plan feedback attribution with actual SQLite row assertions and unchanged state after stale requests.
- `tests/test_merge_gateway.py`: offline injected transport duplicate top-level/nested-pricing tests, one request and no fallback.
- `tests/studio_race_test.js`, `tests/test_studio_dom.py`: controllable successful async response races for prose/settings/plan/feedback, acknowledged CAS on the next save, dirty acceptance guards and memory preservation. Existing conflict DOM test included too.
- `tests/test_studio_boundary.py`: repeated refusal/no-database/provider-access checks and repeated positive reads after successful setup.

## Windows diagnosis and evidence

Early Host/Origin/token rejection wrote an HTTP response then closed with unread POST bytes. Windows intermittently aborted the client receive before HTTP status delivery. The pre-change tight loop ran 60 cases in 42.265 seconds, six WinError10053 errors; its outer command hit 45 seconds after printing the result. This is failed transport, not a fabricated HTTP403.

`respond` now flushes the refusal, then drains inbound bytes with a **0.15-second absolute deadline and 2 * MAX_BODY byte ceiling**, regardless of rejected Content-Length/framing. It does not parse, authorize, open SQLite or contact a provider during cleanup. All POST error paths receive this cleanup, including the previously special oversized-body path. No sleeps, retries, generic test-side OSError acceptance or security allowlist relaxation. Cleanup OSError is ignored only in server transport cleanup, never converted into a successful test/HTTP status. Slow/body framing tests remain bounded. The post-change 32-case loop (including eight valid setup requests) passed in 25.607 seconds. Final suite also includes 40 strict unauthorized refusals with no DB creation, guarded provider access, a valid setup and 20 successful state reads.

## Retained RED to GREEN logs

Directory: `C:\Users\ayan1\Downloads\serial-story-studio\local\test-runs\audit-fixes-20261002-02`.

- `01-boundary-red.log`: actual WinError10053 failures; `01-boundary-green.log`: 32 cases OK.
- `02-reject-red.log`: stale rejection returned 200 instead of 409; `02-reject-green.log`: strict/stale rejection tests OK.
- `03-plan-red.log`: stale plan feedback returned 200 instead of 409; `03-plan-green.log`: explicit attribution test OK.
- `04-merge-red.log`: duplicate JSON did not raise; `04-merge-green.log`: all Merge tests OK.
- `05-ui-accept-red.log`: dirty plan did not disable acceptance. After guard fix, `05-ui-race-red.log`: submitted A overwrote newer B. `05-ui-green.log`: guards, all successful-response races/CAS and memory preservation PASS.
- `06-full-suite.log`: fresh 97 tests OK. `07-node-syntax.log`: empty output, exit 0. PowerShell native stderr formatting may say RemoteException/command exit 1 around narrow green runs; their retained unittest result is OK, not a test failure. Final command captured the actual process exit code, 0.

The additional repeated boundary test is supplementary verification, not a separately failed-first new behavior. No per-function universal strict-TDD claim.

## Remaining gates

Parent owns independent corrected-source re-review (especially successful-response CAS and rejection transaction), real Edge re-verification, screenshots/design audit and network/catalog verification. These were not performed here. Existing servers were not touched. No provider calls, credentials/environment reads, dependencies, private/existing databases, commits or deployment. All synthetic test DBs created under new local/test-runs temporary directories. No real Merge POST enablement added. Existing real-generation preflight/ledger/settlement and production release gates remain unresolved.
