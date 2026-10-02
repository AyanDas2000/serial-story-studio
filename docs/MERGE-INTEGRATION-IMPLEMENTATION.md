# Guarded Merge authoring implementation

## Outcome and boundary

A callable authenticated runtime adapter is connected to explicit author preflight and one-shot confirmation. Paid startup defaults OFF. Enabling it does not generate prose. No application provider call, metadata network request, environment-value read, private database inspection, browser session, installer, dependency addition, commit or server restart was performed during this implementation. Ports 8765 and 8766 were not contacted. Tests used new synthetic databases and injected transports only.

This is a working offline-tested implementation, not production certification or verified live inference. Parent must independently review source, run these commands and verify real Edge before enabling any paid application test. Existing live settings were not switched.

## Exact runtime interfaces

- `serial_story.studio.merge.MergeRuntime(enabled=False, transport=None, key_supplier=None)` is the callable adapter. `prepare(request)` validates text and privately resolves authentication before reservation; `exchange(request)` sends one bounded POST. Internal authoring uses the prepared request without repeating key resolution.
- `serial_story.studio.authoring.MergeAuthoring(enabled=False, ...)` owns `preflight(store, service, payload)` and `confirm(store, service, payload)`. Test dependencies are injected in Python only, not through HTTP or CLI.
- `POST /api/merge/preflight`: exactly `basis` and `operation_id`; revision additionally needs `revision_id` and `expected_text_version`. Requires saved Merge settings and approved, planned intention. Freezes settings, prompt, prose, feedback, history/memory versions and included source IDs. Retrieves exact current metadata and stores a 120-second preflight in the project ledger.
- `POST /api/merge/confirm`: exactly `preflight_id`, `operation_id`, and Boolean `confirm: true`. Rechecks source/CAS and current metadata/prices before reserving. A model or vendor change, expired preflight, missing pricing, dirty revision or unavailable allowance refuses before dispatch.
- Both mutation routes retain the existing loopback Host/Origin, explicit writes, session capability, bounded body and duplicate-JSON checks. `/api/draft/generate` and `/api/draft/revise` remain the synthetic path and cannot silently dispatch Merge.
- `GET /api/merge/model?model=provider%2Fconcrete-id` adds exact-ID lookup alongside scoped `GET /api/merge/catalog`. Exact result must match requested canonical ID. Inspection preserves current selections; author must select and save explicitly. Metadata is not inference entitlement.
- Enabled `/api/state` includes `merge_accounting`: shared allowance and workspace-filtered call receipts with the exact recovery confirmation. UI renders all provider content with `textContent`, not HTML. Recovery explicitly replays the charged success, never resends it.

## Fixed wire and accounting

Runtime origin is `https://api-gateway.merge.dev`; path is `/v1/chat/completions`. Auth is the configured `MERGE_GATEWAY_API_KEY`, resolved only by application runtime after a gate. Request fields are `model`, one `vendor`, one text `messages` entry, `max_tokens`, `stream: false`, `service_tier: "standard"`, `service_tier_fallback: false`, and `include_routing: true`. No tools, stop sequences, policies, priority lists, media, fallback or retries. Parent must confirm the precise `include_routing` request option against the official reference before live use; this session had only the provided contract summary, not an independently retrieved schema.

Request text is at most 48,000 characters, encoded body at most 262,144 bytes, output at most 4,096 tokens, response at most 2 MiB, inert returned prose at most 200,000 characters. Native urllib uses a 30-second socket timeout and disables redirects. This is not a separately proven total wall-clock deadline, particularly for DNS or a slow-drip upstream.

Only bounded `x-merge-model`, `x-merge-vendor`, and `x-request-id` response header values enter receipts. Native HTTP header lookup is case-insensitive. Serving model/vendor must match exactly. No mandatory body routing model/vendor fields were fabricated. Bounded integer prompt/completion/total usage must agree. `usage.cost` and separate `routing.merge_fee_usd` must each be finite, nonnegative numbers; missing/null values never become zero. Their sum rounds UP to integer micro-USD for settlement. Unknown usage, timeout, redirects, denied access, malformed/duplicate JSON, route mismatch and over-reservation cost hold the allowance and block future dispatches. Error bodies and authentication are not echoed.

Canonical ledger: `C:\Users\ayan1\Downloads\serial-story-studio\local\merge-project-ledger.db`, independent of story path. Cap is fixed in code at 1,000,000 micro-USD, with no HTTP/CLI cap/path/rate override. Synthetic story accounting stays separate, with no historical charges copied into the real ledger. SQLite `BEGIN IMMEDIATE`, FULL synchronous commits, exact operation fingerprint replay and an atomic permanent dispatch claim prevent concurrent double dispatch. Reserved/crashed/uncertain calls block new reservations. There is deliberately no automatic reconciliation/refund endpoint.

Reservation uses UTF-8 prompt bytes plus 1,024 framing tokens as a conservative input assumption, plus up to four output tokens per requested word, capped at 4,096. It sums input and possible cache-write rates, then adds the published Pro 5% fee assumption. This is not verified account pricing or provider-side enforcement. Missing required rates refuse preflight. Reasoning enabled by default refuses preflight until its billable output limit is independently established. Consequently both observed Opus/Sonnet 5.5 routes in the parent's receipt remain gated, not silently selected or paid-tested.

After a verified provider success the ledger stores charged cost and actual prose BEFORE writing the story. A story insert/run receipt failure rolls back only the story mutation. The original confirmation can recover after process reopen and even preflight expiry, without metadata/key/transport access. A changed CAS refuses automatic attachment but retains inspectable charged prose. Acceptance remains a separate author action; generation does not advance canon, memory or episode cursor.

## CLI gates and independent commands

Run from PowerShell, using absolute paths. These commands are offline and independently runnable:

```powershell
Set-Location 'C:\Users\ayan1\Downloads\serial-story-studio'
& 'C:\Users\ayan1\Downloads\serial-story-studio\.venv\Scripts\python.exe' -m unittest discover -s tests -p test_merge_authoring.py -v
& 'C:\Users\ayan1\Downloads\serial-story-studio\.venv\Scripts\python.exe' -m unittest discover -s tests -q
node --check 'C:\Users\ayan1\Downloads\serial-story-studio\serial_story\assets\studio.js'
node 'C:\Users\ayan1\Downloads\serial-story-studio\tests\studio_dom_test.js' 'C:\Users\ayan1\Downloads\serial-story-studio\serial_story\assets\studio.js'
node 'C:\Users\ayan1\Downloads\serial-story-studio\tests\studio_race_test.js' 'C:\Users\ayan1\Downloads\serial-story-studio\serial_story\assets\studio.js'
node 'C:\Users\ayan1\Downloads\serial-story-studio\tests\studio_merge_test.js' 'C:\Users\ayan1\Downloads\serial-story-studio\serial_story\assets\studio.js'
& 'C:\Users\ayan1\Downloads\serial-story-studio\.venv\Scripts\python.exe' -m serial_story.studio_web --help
```

After separate approval ONLY, a new chosen workspace/unused port can use `--enable-writes --enable-merge-catalog --enable-merge-generation`. Generation startup requires the other two flags. There is no ledger/rate/cap flag. Do not restart either protected/live server. Review Merge request is metadata-only; Confirm one paid Merge request plus the explicit confirmation prompt authorizes that exact one call. Existing fake and manual authoring work without this flag.

## Actual validation

Evidence directory: `C:\Users\ayan1\Downloads\serial-story-studio\local\test-runs\merge-integration-20261002-guarded`.

- Vertical RED/GREEN receipts: `01` through `15` log files record ledger, adapter, consent-bound authoring, dispatch ownership/recovery, server and DOM slices. The `13-safety-red.log` checks existing guards and is green despite its historical filename; `14-auth-red.log` catches the missing secret-safe supplier boundary.
- Final targeted suite: **14 tests, 6.714 seconds, OK, exit 0**, `15-targeted-green.log`.
- Complete offline suite: **111 tests, 88.198 seconds, OK, exit 0**, `16-full-offline.log`. All 97 baseline tests remain; 14 new tests were added.
- Native Node syntax, original dirty-control DOM, successful-response race/selection DOM and new explicit Merge-consent DOM: **all passed, exit 0**, `17-node-checks.log`.
- CLI help advertises the default-off generation flag: exit 0, `18-cli-help.log`.
- PowerShell formats unittest stderr as a NativeCommandError diagnostic even on successful runs. Recorded process exit codes and unittest results above are authoritative.

Coverage includes two workspace identities sharing separate ledger connections/cap, competing threaded reservations, exact replay, permanently claimed dispatch, reserved/crashed uncertainty, held overcharge receipt, current price/settings/expiry refusal, paid-off before provider/ledger access, actual inert prose and receipt persistence without acceptance, failed local receipt insertion and restart recovery, missing/null charges, missing fee, wrong serving route, excessive usage, duplicate JSON, timeout, secret-safe errors, reasoning gate and explicit/dirty UI consent. It does not claim a complete two-real-story-database paid journey, a live model-change race, or complete browser/layout/accessibility certification.

## Remaining gates and parent verification

1. Review exact request schema, especially `include_routing`, standard-tier billing and whether `max_tokens` bounds ALL billable output/reasoning. The supplied official response-header/cost details were implemented, not independently network-verified.
2. Establish account-specific fee terms and validate conservative input/framing/output assumptions. The 5% published assumption is not a guaranteed fee ceiling. Invoice reconciliation stays authoritative; the local ledger cannot prevent an upstream charge exceeding its reservation.
3. Independently run the full suite and review the source manifest. Expand adversarial coverage for two actual story databases, stale success during dispatch, revision lineage, metadata/model changes and transport timing/header bounds as appropriate.
4. Parent owns real Edge QA, screenshots and Premium Test. No browser was used here, so no screenshot/design-audit score is claimed. Specifically inspect the long preflight, mobile layout, saved selection/dirty lookup race, confirmation cancellation, edits during pending generation and recovery controls.
5. Both verified observed 5.5 routes advertise default reasoning and intentionally fail closed. No paid writing evaluation is authorized by this handoff. Resolve the output-contract gate before any separately approved small live test.
6. Uncertain calls require explicit owner reconciliation, with no retry/fallback or guessed refund. Charged success with stale story directions is readable in receipts but cannot be automatically attached to changed canon. Ledger-write/storage failure after upstream success cannot promise recovered prose, but retains an unresolved reservation.

Release Manager: HOLD for production/live inference and visual verification. Offline working source is delivered. No native inference review was launched, no external worker was used, and shared memory/global settings were unchanged.
