# Development so far
Ayan Das | Serial Story Studio | 8 October 2026

The current product is a local authoring desk with a shelf of separate stories. An author adopts a direction and episode plan, requests sequential drafts, edits paragraphs, accepts prose and confirms quoted story facts. The workflow runs free with a scripted practice writer or against live models through Merge Gateway. This handoff preserves the current implementation without sharing credentials, story databases, recruitment notes or the original repository's private history.

## Progression
1. A Python/SQLite engine established persistent revisions, named author actions and separate draft/accepted state. Earlier CLI and registry code remains in the source as legacy material.
2. The v1 desk added a browser interface, planning/review gates, paragraph editing, undo, source-linked facts and explicit future-impact warnings.
3. Independent reviews drove fixes to approval races, stale results, recovery, provenance, secret checks and malformed provider answers. The current illustrated report describes the changes and distinguishes live retests from automated coverage.
4. The shelf added independent stories and per-series spending limits. Numeric length controls, a first-run walkthrough and explanatory diagrams followed.
5. The latest build added episode titles, retry after completed-but-unusable answers, cleaner rewrite suggestions, real chat history and Windows port exclusivity.

## Evidence included
- Fresh main workflow smoke test and 4:10 silent recording: actual rendered app, isolated practice shelf, no paid calls.
- 354 tests passed on the current development checkout; 36 targeted tests passed after cloning the packaged source Git bundle.
- Ron: 15 saved live drafts, 15-entry adopted plan, author direction and precise word-count manifest. No approval is claimed.
- Tide Ledger: 100-entry plan, ten approved episodes, one later unapproved draft, and an independent literary verdict of REVISE. Read-only prose exports preserve the originals.
- Two saved author edits were included in later frozen writer requests. The evidence shows context propagation; it is not a guarantee of narrative compliance.

## Working versus unfinished
The fresh surface test verified creation, plan validation/adoption, drafting, saving edits, downstream warnings, approval, separate memory confirmation, source quotes and browser-refresh persistence. Practice output is deliberately fixed and does not follow arbitrary premises. It also warns on out-of-range word counts rather than demonstrating assignment-quality prose.

There is no complete 200-episode arc, no proven episode-150 consistency, no semantic contradiction/repetition critic and no public hosted deployment. The existing drafts use a longer configured word range. Episode length is intentionally adjustable per series via Studio → Length; changing it guides future requests without rewriting existing prose. Memory is an author-facing fact ledger; it does not feed the writer. Current drafting uses full preceding prose, so scale needs a bounded context approach. Live failure paths, other operating systems and physical-device/accessibility coverage remain limited; see the test report.

## Try it
Use the root README and the source folder to run free practice mode. The shipped sample lets a reviewer inspect the interface immediately. To inspect real writing, open the exported Markdown episodes; no account or API key is needed. Optional live mode with the separately supplied review key is documented in LIVE-EVALUATION.md. No credential is stored in the repository.

DESIGN-VISION.md describes the broader design and its current implementation boundaries. No output here certifies completion of all employer deliverables.
