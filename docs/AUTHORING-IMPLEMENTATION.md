# Authoring studio implementation record

Date: 2026-10-02. Scope: `docs/AUTHORING-UPGRADE.md` authorized NEW loopback studio slice.
Status: working development slice, not a production or release certification.

## Run it

```
uv run --offline --locked python -m serial_story.studio_web --db local/test-runs/<your-new-db>/studio.db --port 8766 --enable-writes
```

- Without `--enable-writes` the studio is strictly read-only (writes return 403).
- `--enable-merge-catalog` additionally allows the read-only Merge model catalog check.
- Real paid generation is blocked in code (`GenerationBlocked`); see "Missing pieces".

## Touched files

New:
- `serial_story/studio/__init__.py` — package marker.
- `serial_story/studio/store.py` — studio records over the canonical DB: settings (versioned CAS), plan revisions with CAS and explicit "not yet planned" padding, draft edit versions (`episodes.text_version` migration, added only by the studio), revision-scoped feedback, generation receipts.
- `serial_story/studio/server.py` — writable loopback boundary: fixed routes/assets, per-request DB connections, write serialization lock, bounded JSON (256 KiB), session CSRF token on every mutation, Host/Origin/Referer/Sec-Fetch and duplicate-header checks, generic error bodies (no exception dumps), 409 for stale compare-and-swap writes.
- `serial_story/studio/merge.py` — Merge gateway: fixed official origin `https://api.merge.dev/api/llm`, lazily read `MERGE_GATEWAY_API_KEY` (never at import/startup, never exposed), injectable transport, no redirects, no retry/fallback, generation permanently blocked in this build.
- `serial_story/studio_web.py` — entrypoint (default port 8766).
- `serial_story/assets/studio.html`, `studio.css`, `studio.js` — writing desk UI: dominant manuscript editor, narrow planning/settings/memory panel, one primary action per state, labeled native controls, visible focus, 390px single-column layout, no polling (explicit Refresh), unsaved editor text never overwritten.
- `tests/test_studio_boundary.py` (8 tests), `tests/test_studio_workflow.py` (9), `tests/test_merge_gateway.py` (5).
- `local/test-runs/authoring-20261002-01/` — RED/GREEN and suite logs.

Unchanged: all existing review server, assets, service, repository, memory, budget code and tests.

## TDD evidence (vertical slices, logs in local/test-runs/authoring-20261002-01/)

- Slice A (boundary): `red-slice-a.log` — 8 tests RED (module missing). `green-slice-a.log` — 8/8 OK. Fixes made under RED: renamed `setup` handler that shadowed `BaseHTTPRequestHandler.setup`; `MUTATIONS` lookup; drain oversized bodies before 413 to avoid RST; guard memory snapshot before story exists.
- Slice B (workflow): `red-slice-b.log` — RED on plan response contract and missing memory proposal routes. `green-slice-b.log` — 9/9 OK. Honest deviation: plan/settings/draft/accept route skeletons existed from slice A before these tests ran; the tests then locked the behaviors (plan CAS 409, unplanned padding, approval of latest plan only, stale draft edit 409, exactly-once acceptance with idempotent identical retry, 400-700 word gate kept (a too-short fixture draft was refused, not trimmed), rejection, receipt with provider/model/prompt-version/feedback-count, settings CAS and validation).
- Slice C (Merge): `red-slice-c.log` — RED (module missing). `green-slice-c.log` — 5/5 OK: no key read at construction, no-call-without-key with actionable message, official origin + Bearer header only, redirects refused, single attempt, `chat()` blocked before any transport use.

## Full suite

`uv run --offline --locked python -m unittest discover -s tests -q` → `full-suite.log`: **Ran 78 tests, OK** (all pre-existing tests pass unmodified). `node --check serial_story/assets/studio.js` → OK (`node-check.log`).

## Honest missing pieces

- **Real Merge generation is not implemented.** `chat()` raises `GenerationBlocked` citing the unwired prerequisites: validated pricing/output/context limits and the project-shared USD 1 reserve/settle/uncertain ledger. The existing `SQLiteBudget` ledger (USD 1 cap) is reused but no paid call ever reserves or settles, so nothing pretends to be zero-cost. `urllib_transport` exists for the parent's explicit catalog check; the worker made no network calls and read no keys. A user choosing Merge in settings sees a truthful blocking note.
- The browser UI was not yet exercised in a real browser by this worker (parent owns Edge verification); the UI is served and JS is syntax-checked, but visual/interaction polish (premium audit, screenshots) is outstanding.
- Plan feedback is recorded and shown, but the planner view does not yet diff plan versions.
- Receipt includes provider/model/prompt/settings/feedback, but no per-episode provider output log (none exists; no provider was called).
- Duplicate-header checks cover Host/Origin/Referer/Sec-Fetch-Site/Content-Type; other headers are not deduplicated.
- The fixture provider's 200 placeholder beats remain what they were (offline plumbing fixture); the studio's default journey is user-entered setup, planning, and pasted/written prose.
