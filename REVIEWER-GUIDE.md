# Serial Story Studio: review and try it
Ayan Das | Current development snapshot, 8 October 2026

## What it does

Serial Story Studio is a local app for writing a serial story with AI assistance while keeping the author in control. The author sets the direction and episode plan, requests sequential drafts, edits them, approves what becomes established story text, and confirms a memory of quoted facts. Suggestions and drafts do not become accepted story material automatically.

The source, runnable app, demonstration and existing live prose are included. This is the current development state, with unfinished work described below.

## Run the code

Requirements: Python 3.14 and a modern browser. Runtime dependencies are standard-library only; there is no npm install or frontend build. Setup time assumes Python is already installed. Windows is the tested platform; macOS/Linux launch scripts exist but have not been verified on those systems.

Open a terminal in the included `source` folder and run:

```text
python try_it.py --open
```

Alternatively, double-click `try-it.bat` on Windows. The app opens at `http://127.0.0.1:8766/`. If that port is occupied, use `python try_it.py --port 8800 --open`. Stop the server with Ctrl+C. Your new stories are saved in a `stories` folder beside the launcher.

**Practice mode is free and offline.** It uses fixed scripted prose so you can inspect the workflow without a key, account or network calls. It does not test creative output or adherence to an arbitrary premise. The sample story is installed on first run.

For optional real generation with the separately supplied evaluation key, follow `LIVE-EVALUATION.md`. No credential is stored in this repository. Provider spend limits reset periodically and can be exceeded by the request that crosses the threshold. The review key must be revoked before its reset to keep this a one-time trial. The app's per-series cap is a local guard, not a provider-side billing guarantee. Existing live outputs in `demo/` can be read without making any calls.

## A ten-minute walkthrough

| Step | Try | What to check |
|---|---|---|
| 1 | Open the sample series; browse Plan, Write, Memory and Studio | The direction, planned future, prose and extracted facts have distinct views. |
| 2 | Create a series; write a premise and spine; adopt the direction | Saving or receiving a suggestion is separate from adopting governing direction. |
| 3 | Fill episode plan lines and adopt the plan | An empty episode line prevents adoption with a message. |
| 4 | Start drafting a few episodes | Practice/free is labelled; drafts arrive without becoming approved text. |
| 5 | Edit and save a paragraph in episode 1 after later drafts exist | The saved revision changes, and later episodes receive a warning to review. |
| 6 | Approve episode 1 through Finish | Approval locks the saved text. It does not silently save model-proposed facts. |
| 7 | Preview and explicitly save the story facts | Each saved fact links to a quoted source; selecting it opens the source paragraph. |
| 8 | Refresh the page | Adopted direction/plan, saved prose, approval and confirmed facts survive. Fresh smoke testing verified reload, not a server restart mid-job. |
| 9 | Inspect Studio: Length, Money, History and Support | Length settings, practice/no-charge state, revision history and frozen writer-request details are available. |

The included `verification/offline-hitl-demo.webm` shows the main flow in 4 minutes 10 seconds. It is a silent recording with the scripted writer. The fresh smoke report separates observed results from untested coverage.

## Overall logic

```text
Author adopts direction and plan
                 |
                 v
Freeze a writer request: direction + plan job + style + earlier prose
                 |
                 v
Writer returns a draft -> local checks -> working revision
                 |
                 v
Author edits and approves exact prose -> immutable accepted text
                 |
                 v
Read accepted prose for facts -> check quoted evidence -> author confirms
                 |
                 v
Source-linked memory for the author
```

The key separation is between planned future, working drafts, accepted prose and extracted claims. Immutable revisions record what changed. Version checks reject stale edits; an old result cannot silently replace accepted text. Editing an earlier unapproved episode flags later work for human review.

**Memory currently does not feed the writer.** Drafting uses all preceding prose, plus the governing direction, episode job and style instructions. The Memory ledger lets the author inspect facts and their sources; it is not a retrieval system. Draft requests exclude private author notes, the Secrets store and chat history. Chat is a separate advisory call with its own context and cannot perform author-only adoption, approval or memory confirmation.

Generation happens outside the database transaction. Requests are frozen before sending, then outputs are validated before selection. A call known not to have been sent differs from an unknown outcome and from a completed but unusable answer. Unknown outcomes pause for author resolution and are not automatically retried. Live calls reserve estimated worst-case cost before sending and settle afterwards.

## Implementation status

| Area | Implemented now | Evidence / boundary |
|---|---|---|
| Story shelf | Separate series folders and SQLite state; sample story; practice/live choice | Creation and sample exercised in the fresh browser smoke. Rename/delete controls are not built. |
| Direction and plan | Editable premise/spine and episode plan; explicit adoption gates | Fresh surface check passed. A 100-entry live plan exists; no complete 200-entry demo arc is included. |
| Sequential drafting | Provider interface, commissions, pause/resume, frozen context and result validation | Practice batch passed; earlier live outputs included. Live failure recovery was not freshly exercised. |
| Author editing | Paragraph saves, revisions, undo/history, rewrite suggestions and downstream warnings | Edit/save and downstream warning passed fresh smoke. Canonical retcon is not implemented. |
| Approval | Accepted text is distinct and immutable; explicit approval action | Fresh smoke locked the exact edited words. |
| Story memory | Extraction preview, exact quote anchoring, explicit confirmation and source navigation | Seven fixture facts saved and source quote inspected in fresh smoke. Quote matching does not prove semantic entailment. |
| Chat and assistance | Separate advisory conversation; Copy/Ask again; direction context and recent browser chat history | Implemented in current source and earlier live checks. Chat history lives in the browser. No fresh live-chat test here. |
| Length and titles | Per-series shortest/aim/longest, warnings and set-aside threshold; episode titles | Automated coverage plus prior live checks. Warnings do not ensure assignment word counts. |
| Observability and costs | Frozen writer requests, history, call metadata, per-series spend reservations, uncertain-call handling | Automated tests and prior live records. No fresh paid-budget exhaustion or billing reconciliation test. |
| Local persistence | SQLite story state and durable per-series accounting | Browser refresh passed; existing author runs demonstrate saved state. Cross-process/mid-call edge cases are not all resolved or newly tested. |
| Local access controls | Loopback server, host/origin/token checks and port exclusivity | Automated tests. Not a public hosting or production security certification. |

## What is still unfinished

- Bounded retrieval or summaries for long stories. Full preceding prose gets larger and more expensive; consistency at episode 150 has not been established.
- A semantic continuity and repetition checker. New-name warnings and exact quotes are implemented, but wrong dates, relationships, dropped threads and paraphrased secrets can still pass.
- Full 200-episode arc/demo coverage. Ron has 15 unapproved drafts of 746–980 words, generated with a longer configured range. Length is intentionally configurable: Studio → Length can set shortest 400, aim 550 and longest 700 for future drafts. This does not rewrite existing prose or guarantee output compliance. Tide Ledger has ten approved episodes and a 100-entry plan.
- Named arcs, compact memory views, general export controls and shelf rename/delete controls.
- Editing already-approved prose as a retcon, choosing kept alternative drafts, and stopping an active call through the UI.
- A public deployment and broad cross-platform/accessibility testing. This handoff is local; a browser refresh test is not proof of restart recovery during a paid call.

The literary review included with Tide Ledger returned **REVISE**. The app makes decisions and evidence inspectable; it does not guarantee correct or publishable fiction.

## Where to start reading the code

All paths in this table are inside the included `source` folder.

| File | Responsibility |
|---|---|
| `try_it.py` | Starts the offline practice desk and sample shelf. |
| `run_shelf_live.py` | Starts the optional live shelf. |
| `serial_story/v1/desk.py` | Story rules, revisions, governing direction/plan, drafting, approval and memory gates. |
| `serial_story/v1/api.py` | HTTP command validation and mapping errors to responses. |
| `serial_story/v1/shelf.py` | Separate story folders, writer selection and series state. |
| `serial_story/v1/provider.py` | Provider protocol, scripted implementation and failure categories. |
| `serial_story/v1/merge_provider.py` | Live model calls, model routes, spend reservations and response cleanup. |
| `serial_story/studio/server.py` | Local HTTP serving and access checks. |
| `serial_story/v1/web/` and `serial_story/assets/` | UI source and served copies; no frontend build. |
| `scripts/author_client.py` | Terminal client for the same author commands as the browser. |
| `tests/` | Automated workflow, persistence, validation and provider-boundary tests. |

Earlier top-level registry/CLI modules are legacy components. Start with the v1 paths above for the current app.

The original development checkout passed **354 tests**. A prior clean source snapshot passed **36 targeted title/UI/shelf tests**. Fresh verification of this publication is recorded separately in `verification/publication-tests.txt`.
