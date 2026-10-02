# Story review polish and modularity pass

Date: 2026-10-01. Target: a reliable local review workspace before Ayan's 22:30 IST prompt-tuning session, not a public production release.

## Approved scope

Ayan requested UI/UX and usability review, polish, understandable module boundaries, security scrutiny and removal of unnecessary code. This authorizes local changes to Serial Story Studio. It does not enable inference, spending, deployment, publication, accounts, browser approvals or a writing/editing backend.

## Baseline and rollback

The repository has no commits; existing files are untracked. Preserve them, do not reset, clean or silently create a first commit. A source-only snapshot and SHA-256 manifest are at `C:/Users/ayan1/AppData/Local/hermes/cache/scratch/story-polish-20261001/baseline` and `baseline-manifest.json`. This excludes databases, credentials, environments and Git internals. Original test suite: 37 passed. Before screenshots: `before-desktop.png`, `before-phone.png` in the same scratch directory.

## Design contract and reused skills

Use the already installed shared Droid/Codex skills at `C:/Users/ayan1/.agents/skills/{taste,platform-web,security,workflow}/SKILL.md`, mirrored for Claude. Product-wide workflow/design contracts are in `C:/Users/ayan1/Downloads/ayan-skills/WORKFLOW.md` and `DESIGN.md`. Preserve the project's editorial Evidence Spine and bundled IBM Plex font in `.stitch/DESIGN.md`. Apply design principles to the existing plain-JavaScript stack, not an unnecessary React/shadcn migration. No new packages or agent subscriptions.

The shared skills attribute their principles to original upstream projects, including `pbakaus/impeccable`. No new GitHub scan or upstream installer was run for this pass; the already installed shared skills were used directly.

## Initial observed usability issues

- On 390px phones the warning, header and navigation consume most of the initial viewport before prose starts.
- Six horizontal navigation buttons hide sections offscreen without a clear discovery cue.
- The visual Evidence Spine resembles links but is not interactive.
- All revisions share episode-only labels, making repeated drafts hard to distinguish.
- Memory lists current, proposed, rejected and superseded facts together with no easy filtering.
- Rebuilding the whole workspace can lose keyboard focus and input state on refresh.
- Model copy says discovery is complete even when no model metadata is attached, and asserts advertised streaming instead of reading its value.
- CSS and JavaScript are densely packed; Python review code combines snapshots, provider metadata, graph adaptation and HTTP transport.

## Implementation ownership

Frontend builder owns `serial_story/assets/review.html`, `review.css`, `review.js`, new `assets/ui/{dom,reader,planning,evidence,review-details}.js`, and a new frontend contract test if needed. Existing graph export assets and domain code are not in this builder's scope.

Backend builder owns `serial_story/review_web.py`, new `serial_story/review/{__init__,snapshot,provider,server}.py`, `tests/test_review_web.py` and new narrowly scoped web-security tests. The stable public review_web imports remain compatible. Exactly the five named frontend modules are added as fixed asset routes; no generic file server.

A separate correctness/modularity audit reviews the immutable baseline. Parent integrates any justified domain fixes with regression tests, reviews all edits, performs browser QA and writes final architecture/verification documentation. Builders never edit each other's files.

## Acceptance criteria

- Six sections remain discoverable on desktop and phone, keyboard navigable and distinguish their current view. Navigation/back/reload behavior is explicit.
- Reader distinguishes revision, status and word count; source inspection highlights the exact accepted evidence. Status is never indicated by color alone.
- Memory can filter meaningful states; empty results offer an actionable way to clear filters.
- Loading, empty, error/retry and loaded states are understandable. No fabricated narrative-quality scores, invented rates or unsupported provider claims.
- Refresh avoids unnecessary rerendering, preserves relevant selection/focus and cannot overlap requests. Show last successful observation without claiming model streaming.
- Screen checks at 1440, 768 and 390px, plus keyboard, reduced motion, long labels and 200% zoom. No document overflow. Bundled font renders.
- All frontend data reaches safe text sinks. No eval, external scripts, external fonts or loosened CSP.
- HTTP stays loopback-only with exact host/origin checks, fixed routes, no CORS, no writes or model calls. Read-only snapshots leave the selected database unchanged.
- Existing tests pass; meaningful added regression tests prove new boundaries and security cases. No unnecessary runtime dependencies or framework setup.
- Entire codebase gets correctness/security/modularity scrutiny; retain already sensible domain/repository/provider/budget boundaries instead of mechanically splitting every file.
- Final independent diff review covers correctness, security, reuse/efficiency and complexity. Verified high-severity issues are fixed or explicitly block the release.

## Production gates not addressed by UI polish

The executable writing provider is still fake. Real provider integration, explicit spend approval, observed billing/cache behavior, real-episode evaluation, human-edit/approval browser flows, hosted authentication and deployment must be separately implemented and verified. The local Python HTTP server is not a production internet-facing service.
