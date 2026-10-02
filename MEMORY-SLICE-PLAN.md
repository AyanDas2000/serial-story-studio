# Source-linked memory slice

## Outcome and bounded scope
The writer can inspect which confirmed facts concern each character and situation, see accepted evidence, record future directions separately, and reopen the same state after exiting. This is an offline learning slice, not the complete serial generator or a public website.

Assumptions to discuss: at most 30 characters; at most 10 major characters including one protagonist; typically 5-10 active per episode, 10 maximum when selecting a cast. Do not manufacture a full cast before selecting a premise. Locations are a human-approved registry, not automatically invented by a model. Registry identity/role is author setup, not proof an event happened.

## Surfaces and actions
- CLI: register entities, propose a fact with evidence, confirm/reject it, query current/history, record future direction, export a graph.
- Read-only local graph: select a character or situation, inspect links and accepted evidence. Primary action: inspect a source. No editing, account, network, paid calls or deployed UI.
- Storyboard snapshot: accepted current facts versus separately labelled desired direction. Manual CLI changes update directions immediately; factual changes require accepted evidence and human confirmation. Historical prose edits remain refused.
- Diagram artifacts: explain the full proposed pipeline and relational storage; distinguish implemented from future stages.

## Files
Add memory records/store/service boundary in serial_story/memory.py and records.py; narrow SQLiteRepository and StoryService hooks; CLI subcommands; graph renderer/template/assets with no JavaScript package; project-wide budget policy in budget.py; tests/test_memory.py, tests/test_graph.py and tests/test_project_budget.py; docs/FRAMEWORK.md and diagrams; README, PRODUCT, verification receipt and configuration notes.

## Data and state
Entities (character/location); accepted-source situations; fact proposals (proposed/confirmed/rejected, source revision, exact evidence span, optional object and situation); explicit supersession links with history preserved; append-only direction revisions (active/retired, future scope); memory revision; persistent project budget. Foreign keys and short immediate transactions. A graph is a read model of SQLite, never another authority.

Confirming a fact twice is idempotent. A changed single-value fact requires an explicit supersession of the current fact and later accepted evidence; obsolete or retroactive replacements are refused. Human confirmation verifies interpretation; matching an evidence quote does not prove semantic truth.

Context contains confirmed relevant facts and applicable directions before optional recent prose, under a hard bound. Essential overflow refuses generation. Memory/direction changes invalidate a pending draft's acceptance basis; no automatic paid redraft. Record included fact/direction IDs and memory revision. Completeness of manual extraction remains a limitation: the graph is not a proof every story fact has been captured.

## Tests and security
Vertical test-first slices: accepted edited evidence -> confirmation -> query -> restart; rejected/draft/absent/ambiguous evidence refusal; registry limits; same-slot supersession and stale rejection; situation linkage; directions in later context; pending draft invalidation; SQL input and HTML script escaping; graph-source clicks; project cap across episodes/all stages; unresolved reservations after restart; cap cannot silently reset on reopen. Retain all 14 existing workflow tests. Run fresh CLI processes and independent read-only review. No credentials or private hiring material in packets.

## UI/design boundary
Graph is a local explanation prototype, not a shipped website. Follow project tokens, keyboard access, text wrapping, reduced motion, browser inspection, empty/error states and screenshot evidence. No graph framework/CDN/runtime downloads. Only a licensed font asset from a known official publisher may be bundled with provenance; no external source project imported.

## Plan reviews
CEO: keep. Inspectable evidence and lasting directions directly improve the outcome metric.
EM: 8/10. Additive schema, original files preserved, narrow offline operations, tested rejection boundaries. Storage/accounting need independent review. Rollback uses backed-up original code and additive tables, never destroys a user's database.
Designer: information architecture 8, states 8, template-risk 8, accessibility 8, responsive 8, edge cases 8, contract consistency 8. A 10 needs usability testing with a real story; do not claim that here.
Release Manager: hold publication. No commits/remotes/deploys are authorized. Real semantic extraction, episode direction alternatives, judge/redraft loop, automatic digestion, full 200-episode arc, 15 real episodes and historical repair are deferred.
