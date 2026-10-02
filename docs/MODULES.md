# Module map

The application remains plain Python, SQLite and native browser JavaScript. No new application dependencies, framework, plugin registry or generated boilerplate was introduced.

## Writing and persistent state

- `serial_story/records.py`: shared typed records and domain errors.
- `repository.py`: story/plan/episode persistence, acceptance and rejection transactions. Owns canonical accepted prose, review records and cursor movement.
- `memory.py`: source-linked entity/fact/situation/direction ledger, human confirmation, explicit supersession, context selection and graph read model. Retained as one cohesive ledger instead of mechanically splitting every class.
- `budget.py`: durable reservations, settlement and unresolved-call limits. Still per database; not a real cross-database/provider spending enforcement system.
- `provider.py`: narrow story-material protocol and deterministic fake implementation. No real writer adapter.
- `service.py`: application orchestration and bounded context selection; independent of terminal/browser rendering.
- `cli.py`: local command parsing, application calls and non-overwriting file exports. Human edits and approvals remain here.

Do not introduce HTTP or DOM concerns into these modules. A future model adapter must return measured usage/cost and define fail-closed budget settlement; plugging it into the current zero-cost fake operation is not production integration.

## Read-only review backend

- `review_web.py`: compatible CLI entrypoint and reexports of the prior public review API.
- `review/snapshot.py`: read-only SQLite connections, consistent story observations and graph adaptation without schema initialization.
- `review/provider.py`: typed, scalar-only public catalog metadata; excludes arbitrary nested receipt data and forces generation off.
- `review/server.py`: loopback transport, host/origin checks, generic errors, fixed routes and CSP/security headers.

The server cannot approve, edit, generate or publish. Do not extend it into a generic file server. A writing API needs a separate explicit design and authorization boundary.

## Browser review

- `assets/review.html`: document, six review sections, native mobile selector and skip link.
- `assets/review.css`: readable editorial styling and named tokens; responsive layouts and reduced-motion behavior.
- `assets/review.js`: navigation, session-local selections, polling, catalog loading, recovery and focus restoration.
- `assets/ui/dom.js`: safe DOM/text construction, table semantics and focus helpers.
- `assets/ui/reader.js`: revision selection and prose/evidence reader.
- `assets/ui/planning.js`: planned intentions, range/search controls and future directions.
- `assets/ui/evidence.js`: memory-state filtering, exact Unicode evidence highlights, source links and lazy graph disclosure.
- `assets/ui/review-details.js`: quality prompts, recorded decisions/accounting and honest model metadata states.

The existing standalone graph exporter (`graph.py` and graph assets) remains self-contained. Its graph contains confirmed interpretations and their history, not proposed/rejected facts. The memory list separately exposes all fact states.

## Edit and test loop

1. Change the responsible module, not a parallel copy of its logic.
2. Add a regression at its behavioral boundary and observe RED before the fix.
3. Run `uv run --offline --locked python -m unittest discover -s tests -v`.
4. For UI changes, inspect real Edge rendering and interactions; the synthetic Node DOM harness does not prove layout or accessibility.
5. Restart the local server after Python backend changes. Browser assets are served without caching.

The repository had no commits before this work. Original source rollback snapshot: `C:/Users/ayan1/AppData/Local/hermes/cache/scratch/story-polish-20261001/baseline`. No reset, clean, commit, push or deployment was performed.
