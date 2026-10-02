# Serial Story Studio

> **v1 slice — read this first.** A working authoring engine now lives in
> `serial_story/v1/`. It runs the real loop against a live model: adopt a direction,
> commission linked episode drafts, revise a passage, undo, approve a prefix into canon,
> and continue with the next episode written against accepted canon. Verified live with
> Opus 5.5 — two linked episodes, 757 and 828 words, no canon contradictions.
> The specification it implements is in `docs/v1/`.
> Everything below this line describes the earlier legacy scaffold, which is unchanged and
> still passes its own tests.

An interactive environment for writing a long story with an AI: you adopt an overall
direction, commission linked episode drafts, revise passages selectively, undo safely, and
approve what becomes canon. The system keeps provisional material separate from accepted
story data, and never promotes anything on its own.

## v1 — tests, architecture, and constraints

```
uv run --offline --locked python -m unittest \
  tests.test_v1_http tests.test_v1_slice tests.test_v1_journey tests.test_v1_prompt_contract
```

32 tests. The wider suite also carries 11 pre-existing environmental errors
(`FileNotFoundError` on a missing `local/test-runs` directory), unrelated to v1.

- **SQLite on a local filesystem, deliberately.** Story state lives in a local database;
  six triggers make accepted canon immutable, and story and ledger coordinate across two
  databases. This is the main deployment constraint — it does not run on serverless
  platforms with ephemeral filesystems (Vercel, Netlify functions) without first porting
  storage to a durable database and the server to a long-lived process. That port is a
  separate project, not a deployment step.
- **Generation sits behind a provider seam.** `v1/provider.py` defines the protocol and
  `ScriptedProvider` is the deterministic offline default; a live provider implements the
  same interface and is injected, so no call site changes.
- **The prompt contract is code.** `draft_prompt()` in `v1/desk.py` assembles every
  generation prompt with explicit precedence — spine and arc outrank established story
  data, which outranks adopted voice notes — and puts output rules last so thousands of
  characters of prior prose cannot become the final instruction. Asserted in
  `tests/test_v1_prompt_contract.py`.
- **Cost grows with the story,** because each episode carries the canon before it. Two live
  episodes cost about $0.09; a 15-episode arc would far exceed a $1 allowance, so batch
  drafting carries a ceiling checked before any request is dispatched.
- **Interface:** `serial_story/v1/web/` (`v1.html`, `v1.css`, `v1.js`), served by the v1
  routes. Exercised against a real running server: 31/31 steps, 0 overflow violations, 0
  controls without focus rings, 0 console errors, state surviving refresh and restart.

**Not yet proven:** rewrite, undo and memory operations against live multi-episode prose;
and no human usability testing has been done.

---

## Legacy scaffold (below)

A local, fake-only scaffold for learning human-directed serial generation. It does not call an LLM, read credentials, or produce submission-quality fiction. The fake plan has 200 indexed placeholder beats; it is not a developed 200-episode arc.

## Setup and offline tests
Requires `uv` and an already installed Python 3.14.7. This workstation has both. The isolated `.venv` is created locally; no global packages are changed. Runtime dependencies and third-party development dependencies are empty. Standard-library `unittest` supplies the test harness; `.python-version` and `uv.lock` pin the development setup.

PowerShell:

```powershell
Set-Location 'C:\Users\ayan1\Downloads\serial-story-studio'
uv sync --offline --locked
uv run --offline --locked python -m unittest discover -s tests -v
```

Git Bash, if preferred:

```bash
cd 'C:/Users/ayan1/Downloads/serial-story-studio'
uv sync --offline --locked
uv run --offline --locked python -m unittest discover -s tests -v
```

This milestone uses a module entry point, not an installed console script. From this folder, `.venv/Scripts/python.exe -m serial_story` also works. Python version portability and clean-machine installation are not yet validated. No network downloads are needed on the verified workstation.

## One fake cycle you control
Each command is a separate process, so leaving the terminal between commands is safe. Defaults: provider `fake`, database `local/story.db`, three calls per episode, zero micro-USD cap. Existing environment keys cannot change the provider.

```powershell
uv run --offline --locked python -m serial_story init --premise "A cartographer discovers a room missing from every map."
uv run --offline --locked python -m serial_story plan
```

Read the proposed plan. On a fresh database its ID is 1; use the ID actually displayed:

```powershell
uv run --offline --locked python -m serial_story approve-plan 1
uv run --offline --locked python -m serial_story draft --out local/review-001.txt
```

Read `local/review-001.txt`. Edit that file in your editor if you want different final prose, keeping 400-700 words. The counting rule is `len(text.split())`: whitespace-separated units, not a language-aware tokenizer. Then accept the displayed draft revision ID (1 on a fresh database):

```powershell
uv run --offline --locked python -m serial_story accept 1 --text-file local/review-001.txt
uv run --offline --locked python -m serial_story read 1 --out local/accepted-001.txt
uv run --offline --locked python -m serial_story status
uv run --offline --locked python -m serial_story trace
```

Close the process or terminal. Reopen it, return to this folder, and run `read 1` again. The accepted prose is saved in SQLite; the text file is an export, not a second authority. Editing an export after acceptance does not change canon.

To reject instead of accept:

```powershell
uv run --offline --locked python -m serial_story reject 1 --note "I want a different opening."
uv run --offline --locked python -m serial_story draft --out local/review-001-attempt-2.txt
```

A new draft gets a new revision ID while staying at the same episode number. Rejection notes are audit records, NOT implemented future-story directions. Use a different review-output filename for a new attempt; exports never overwrite different existing text. Exports stage complete text beside the target and publish with an exclusive hard link. This is verified on the local Windows filesystem; a filesystem without hard-link support refuses the export rather than weakening the no-overwrite rule.

Re-running `draft` while review is pending returns the same draft without another call. Re-running an acceptance returns the same receipt without advancing again. Supplying different prose for an already accepted revision is refused. Plan editing and historical editing remain unavailable. Scoped future directions now exist; changing memory or directions invalidates acceptance of a pending draft based on older state.

For a separate experiment, specify `--db local/another-story.db` BEFORE the subcommand. Initializing an existing database with a different premise is refused; there is no reset/clean command.

## What each component owns
| File | Why it exists |
| --- | --- |
| `records.py` | Small immutable records and actionable workflow errors |
| `repository.py` | SQL persistence, plan gate, revision status, acceptance transaction and uniqueness rules |
| `provider.py` | Story-material protocol and deterministic fixture provider; no SDK or environment lookup |
| `budget.py` | Persistent reservations, settlements, unresolved charges and attempt limits; a seam for later real accounting |
| `service.py` | Plan/draft workflow, source-linked bounded context, and provider calls outside write transactions |
| `memory.py` | Registry, exact accepted evidence, human confirmation, explicit fact development, situations, directions and consistent snapshots |
| `graph.py` / `assets/` | Self-contained read-only SVG evidence view, bundled font/license and CSP |
| `cli.py` / `__main__.py` | Arguments, printing, local text import/export; no story business decisions in prompts |

Start reading with `StoryService.draft`, then `SQLiteRepository.accept`. The first decides when a draft can be made. The second checks the pending revision and writes final prose, memory source, review event and cursor atomically.

## Honest capability boundary
Works: plan proposal/approval; pending-draft recovery; edited acceptance; rejection; duplicate-approval safety; 400-700-word acceptance gate; durable call records/limits; explicit unresolved reservations; accepted text reopen/export; bounded recent-text context and inclusion manifest.

Stub: the provider is deterministic repetitive prose; the plan is indexed placeholders. Memory stores final accepted-text provenance PLUS a human-confirmed entity/fact/situation ledger. Extraction is manual, not automatic or exhaustive. Cost arithmetic is a tested reservation interface, not validated provider billing. The example configuration is documentation-only and is not loaded.

Not implemented: real provider adapter, actual token usage/pricing, request timeouts/retries for a network SDK, semantic checks/critic, layered summaries, typed knowledge/thread retrieval and future-beat reconciliation, plan editing, retroactive invalidation, interactive review wizard, editable web UI, 15 real episodes, intervention evidence, cost forecast, recording, deployment or submission.

The fake provider does not interpret story instructions or prove feedback changes narrative output. Tests prove edited text enters later context, not story quality. Its context bound is characters, not model tokens. Confirmed relevant facts and applicable directions now precede optional recent prose in context. Selected-cast filtering does not yet retrieve all location/thread/knowledge constraints, and fact coverage is manual. This is not episode-150 consistency proof; see `docs/FRAMEWORK.md`.

## Local safety
A new local Git repository was initialized without commits or remotes. No paid model calls, uploads, deployment or publication occurred. Databases, local review/export files, raw traces, `.env`, keys and private inputs are ignored. `.gitignore` is not encryption or a complete secret scanner. Keep private material outside the repo and inspect any future export before sharing. Local SQLite contains unencrypted story material.

## Discuss before extending
Read `PRODUCT.md`, `MEMORY-SLICE-PLAN.md`, `docs/FRAMEWORK.md`, `docs/diagrams.html`, `docs/SECURITY-REVIEW.md` and `VERIFICATION.md`. The graph prototype is read-only/offline. The larger planner/writer/reviewer flow is a proposal, not implemented real model generation or a claim of complete employer deliverables.

## Source-linked memory and the storyboard
Start with `entity-add` for author-approved characters and places. Character roles are `protagonist`, `core`, `supporting`; omit role for locations. Limits: 30 total characters, ten major INCLUDING the one protagonist. Selected active cast has a maximum of ten; five is a creative target, not a forced minimum. The selected-cast limit does not count actual names in prose.

A fact is initially a proposal, not history. `fact-confirm` promotes its human interpretation. Evidence must occur exactly once in the FINAL accepted text; use a longer passage when ambiguous. Confirmation proves provenance, not logical entailment. `fact-reject` leaves it outside writing context. `fact-show ID` reads a saved proposal, including rejection status. `storyboard` shows current confirmed facts, pending fact proposals, author setup and active future directions from one consistent database read. Direction ranges determine which intentions apply to the next episode.

Illustrative commands BELOW assume you already accepted the exact passage `Ivo is alive. Ivo waits at the harbor.` in the episode's edited final prose. Use the actual entity/revision/fact IDs printed, not guessed IDs. Do not insert fixture facts into a different story.
```powershell
uv run --offline --locked python -m serial_story entity-add --name Ivo --kind character --role protagonist
uv run --offline --locked python -m serial_story entity-add --name Harbor --kind location
uv run --offline --locked python -m serial_story fact-propose --subject 1 --predicate status --value alive --revision 1 --evidence "Ivo is alive. Ivo waits at the harbor."
uv run --offline --locked python -m serial_story fact-show 1
uv run --offline --locked python -m serial_story fact-confirm 1
uv run --offline --locked python -m serial_story facts --subject 1
uv run --offline --locked python -m serial_story facts --history --search alive
uv run --offline --locked python -m serial_story direction-set --key relationship-pace --text "Build trust before romance." --subject 1
uv run --offline --locked python -m serial_story storyboard
uv run --offline --locked python -m serial_story context --character 1
uv run --offline --locked python -m serial_story graph --out local/memory-view-001.html
```
For a location relationship, add `--object LOCATION_ID`; for scene context, first `situation-add --title TITLE --revision REVISION_ID --evidence PASSAGE`, then add `--situation SITUATION_ID` on the fact proposal. To replace a current property with LATER accepted evidence, `fact-confirm NEW_FACT_ID --supersedes CURRENT_FACT_ID`. Earlier versions are retained. Different predicates are different slots: typed semantic contradiction detection is NOT implemented.

Before a NEW draft, add repeated `--character ID` selections as needed. This selects relevant facts/directions, not a verified list of everybody appearing in prose. Recent prose may be omitted for space. The manifest records included fact/direction IDs and included/omitted prose revision IDs; it does not enumerate every omitted fact.

## Open a separately saved, explicitly fake graph fixture
```powershell
uv run --offline --locked python preview_memory.py
```
This script creates a NEW uniquely named folder under this project's ignored `local/`, never overwrites an existing story, makes an automated accepted fixture and prints its HTML path. It is not a real human intervention or story demo. The graph has character/place, fact, situation, episode and future-direction nodes. Select a fact and Inspect a source; read its exact accepted passage and full source episode. Filters, query, history toggle and keyboard Enter/Space are supported. All node relationships remain in SQLite; the graph is not another editable authority.

A CLI graph export with `--subject ENTITY_ID` includes facts about that entity or referencing it as their object. Supersession links to facts outside that selected view are omitted, not deleted from the ledger. Use an unfiltered export (omit `--subject`) to inspect the full recorded supersession chain; filtered snapshot warning metadata records this limitation.

The exported HTML is a SAVED SNAPSHOT, not a live database client. Re-export to a NEW filename after changing records or graph assets. The browser uses no network calls or remote scripts/fonts. It includes full accepted source prose, so do not publish it without inspecting it. Desktop-first: phone layout keeps the body within the viewport while the graph scrolls, but mobile source navigation needs further product design. The viewer displays at most 250 nodes and explicitly asks you to narrow filters; a production-scale viewport is deferred.

## Open the local live review
A read-only review workspace now provides episode prose, storyboard intentions, source-linked memory, quality-review prompts, receipts and sanitized Merge model discovery. It refreshes database observations every three seconds while visible. It does **not** edit/approve stories, stream model output or make inference calls. The initial selection is an explicitly labeled existing offline fixture.

```powershell
.\.venv\Scripts\python.exe -m serial_story.review_web --db local/memory-preview-76cf1f82e6fc/fixture.db --fixture --port 8765 --provider-receipt local/merge-review-metadata.json
```

Then open `http://127.0.0.1:8765`. Full usage, restart, security scope, read-only Sonnet 5.5 discovery and remaining real-generation/cache-budget gates: `docs/LOCAL-REVIEW.md`. This local development view is not a hosted or finished writing product.

## Budget boundary
`status` now includes a persistent USD 1 aggregate ceiling for all episodes and stages WITHIN ONE DATABASE. Live and uncertain reservations remain ceiling consumers; invalid fractional/negative monetary values are refused. Nonzero accounting amounts in tests are artificial, not real spending. Fake calls spend USD 0. No real adapter exists. Before any real gateway call, use one shared project ledger across ALL demo databases, approved access/model, verified token prices and maximum charges, and provider billing reconciliation. A new database must not create a second real dollar allowance.

