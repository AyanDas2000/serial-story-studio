# Offline memory-slice security review

Reviewed October 1, 2026. Scope: this build's application code, standard-library dependencies, bundled assets, CLI persistence and read-only graph export. Parent-performed review, NOT an independent security certification. Original 14-test scaffold had a separate successful independent review; that verdict does not cover this new slice.

## Verdict
Local checks and independent reviews identified no security concern within the reviewed offline scope. The initial independent review found one medium graph correctness defect; after correction, its separately authorized targeted independent re-review **passed** with no security concerns or logic errors. This closes the reported correction, not a general security certification. Any public/provider release remains HOLD; the future hosted or model-connected system has not been cleared.

## Independent finding and parent correction
- Original independent receipt: `C:/Users/ayan1/AppData/Local/hermes/cache/scratch/memory-independent-review-20261001-8e6134/review.json`. The reviewer ran 31 tests, compiled 17 files and ran nine targeted probes; no independent browser/CVE audit or real billing validation was performed.
- Defect: a location filter removed an old fact node after its object changed, but graph construction still emitted a supersession edge to that node. The CLI refused export with a dangling-edge error.
- Red/green: a new fresh-process CLI regression reproduced exit 2; after the upstream fix it passed. The parent full suite then passed 32 tests in 36.433 seconds. Strict filtering now omits supersession edges to facts outside the selected view, with warning metadata; unfiltered/character views retain the recorded history.
- SHA-256 comparison against independently reviewed code/assets/tests found changes only in `serial_story/memory.py` and `tests/test_memory.py`. Renderer validation, JS/CSS/CSP, provider and accounting code are unchanged. Parent fix receipt: `local/filtered-graph-fix-receipt.json`.
- **Status: targeted independent correction review PASSED** on October 1, 2026. Ayan explicitly approved this additional read-only review through the assistant allowance, separate from USD 1 story-generation spending. The original failed review remains preserved.
- Independent post-fix evidence: `C:/Users/ayan1/AppData/Local/hermes/cache/scratch/filtered-supersession-rereview-20261001-165346-23c6f706/review.json`. **32 tests passed in 23.719 seconds**, 17 files compiled in memory, and 149 targeted assertions across 31 child processes passed. Independently built fixtures were closed in a terminated builder process before export. Two/three-event chains, empty/factless/invalid filters, exact HTML/JSON, no-overwrite publication, complete retained ledger and mutation of the endpoint guard were exercised.
- The parent checked actual suite/compilation/probe receipts and matched all 50 reviewed protected-file hashes against the current project before these status-document updates. No application/assets/tests were changed after this re-review. Corroboration: `local/filtered-graph-rereview-confirmation.json`.
- Two non-blocking follow-ups remain: close the parent fixture repository before its regression subprocess for stronger coverage within that test; optionally show the filtered warning visibly using safe text rendering. Independent probes already demonstrated post-builder-termination exports. These suggestions were recorded, not silently implemented; the approved fix only promises warning metadata.

## Actual evidence (prior parent run)
- Full suite: **31 tests passed in 22.426 seconds**; compileall passed. Earlier baseline was 14 tests.
- Fresh-process integration: ledger commands, accepted evidence, confirmed facts, directions, storyboard, bounded context and graph export survived separate CLI processes.
- Scoped AST inspection of **10 application Python files**: only standard-library imports; no detected eval/exec, os.system, shell=True, pickle loading, environment-key lookup calls or formatted SQL calls. A sensitive-name literal check returned no findings and did not print values. This is a narrow static check, not a complete secret scanner.
- `pyproject.toml` runtime and development dependency lists are empty; offline locked synchronization passed. No package, CDN, graph library or external project runtime was added.
- Bundled IBM Plex Sans font and SIL license hashes/sizes matched `serial_story/assets/provenance.json`. This measures bundle integrity, not an exhaustive font-parser or upstream supply-chain security audit.
- Runtime inventory: Python **3.14.7**, SQLite **3.53.1**, on the verified Windows workstation. No exhaustive Python/SQLite/browser/OS CVE audit or clean-machine portability claim.
- Graph fixture snapshot: 13 nodes, 17 edges, five confirmed facts and two future intentions. Its initial protagonist filter displayed ten nodes; this is illustrative fixture data, not narrative coverage evidence.
- Browser: desktop 1440px and actual emulated 390px layout, font loading, Enter-key source inspection, empty/no-match/corrupt-export states, untrusted script-shaped labels, reduced-motion duration and no uncaught runtime exceptions on checked pages.
- Egress probe: a harmless request to example.com was blocked AND recorded a `connect-src` security-policy violation. Full receipt: ignored `local/memory-preview-76cf1f82e6fc/browser-verification.json`.
- Local scan receipt: ignored `local/security-scan.json`. Screenshots: `docs/design/`.

## Threat checks
| Boundary | Implemented and exercised protection | Remaining limitation |
| --- | --- | --- |
| SQL-shaped user input | Bound query values; literal-input regression did not alter episodes | This is not an untrusted SQL or arbitrary database import service |
| Proposed or rejected story prose | Facts require an accepted revision and exact, unambiguous canonical quote | Provenance does not prove the interpretation logically follows |
| Pending fact proposals | Visible in storyboard but absent from writing context until confirmed | Extraction/coverage is manual |
| Fact development | Explicit current-slot replacement, later evidence ordering, retained history | Predicate aliases, flashbacks and semantic contradictions are not resolved automatically |
| Atomicity / retries | Acceptance and fact confirmation rollback on injected failures; idempotent approvals | Direct database edits bypass application rules; no tamper-evident ledger |
| Mixed storyboard reads | Transactional snapshot; a second writer could not enter the middle of its read | Single-user local store, not a multi-tenant database service |
| HTML / script injection | Escaped JSON delimiters, single-pass template substitution, textContent, fixed attributes | Do not add raw HTML rendering for story prose |
| Browser capabilities | Hashed trusted script, no remote scripts/fonts, connect-src none, object/base/form restrictions | Inline styles remain permitted; this is not a complete hosted CSP |
| Existing human files | Same-directory staged/fsynced export, exclusive publication, different content refused | Explicit CLI paths are owner-controlled, not an HTTP path sandbox; unsupported filesystems refuse |
| Money / retries | Integer micro-USD accounting; aggregate cap, pending/uncertain reservations and attempt limits persist | Aggregate is per database; all amounts are artificial/fake until a shared real-provider ledger exists |
| Context / stale work | Essential overflow stops before another attempt; version checks refuse stale acceptance | Character bounds, not tokenizer bounds; omitted-fact coverage and location/thread retrieval are incomplete |
| Cast | Maximum 30 registry characters, ten major including protagonist, selected cast at most ten | No semantic character counting in actual prose |
| Private material | No credential files inspected, no key search, no real gateway calls, no recruiter/shared-memory data copied into artifacts | Story DB/exports are unencrypted; exported HTML contains full accepted source prose |

CSP adds defense in depth and does not replace safe handling of untrusted content. A hosted version should deliver its policy through response headers; meta policies do not support every CSP feature.[1] SQLite separately documents precautions for untrusted SQL and database files; this local trusted-store review does not establish an arbitrary-database-import security boundary.[2]

## Known product/QA issues and limits
1. Fixed: faded nonselected text and faint edges. Selection now uses border emphasis, preserving readability. Palette tokens and screenshots were updated.
2. Fixed: narrow grid track expanded the page. The real 390px check now reports page width 390 and a deliberately scrollable 960px graph within a 340px canvas.
3. Fixed: separate storyboard queries could produce a mixed view and did not expose pending fact proposals. A transactional snapshot now supplies both, with a second-writer regression.
4. Fixed: fixture helper initially calculated its root one directory too high. Its owned generated fixture was moved into the build; subsequent generation printed a project-local path. No existing story/work was overwritten. An empty `Downloads/local` directory may remain; no unrelated cleanup was performed.
5. Remaining usability issue: desktop-first exploration. On a phone, graph exploration needs horizontal scrolling and the evidence inspector is below the graph. Do not label the mobile product polished or ready to ship.
6. Remaining scale limit: viewer displays at most 250 items and asks to narrow filters. No full 200-episode graph performance/virtualization benchmark.
7. Harness caveat: browser-helper screenshots/timers timed out. Isolated native headless Edge plus local DevTools produced the final screenshots and browser receipts. Browser diagnostic stderr is not an app JavaScript exception report.

## Release gates
- Independent review chain completed: original broad offline review found one graph logic defect and no security concerns; parent reproduced/fixed it; the separately approved **targeted post-fix review passed** with empty security/logic findings. This is clearance of the reported correction within the offline scope, not provider, CVE, hosted UI or whole-product certification. No remaining blocking finding from these reviews is recorded.
- Real-provider path: approved access/model, current rates, actual tokenizer and worst-case reservation, one shared project ledger across ALL demo databases, timeout/billing reconciliation and no unapproved fallback. The current service's provider seam settles fake usage at zero; it is NOT ready for a real paid implementation.
- Future agent path: treat retrieved prose as data, isolate writer/reviewer from secrets and filesystem/network tools, validate proposed patches and require human approval. No autonomous editing agent is implemented now.
- Hosted website: separate authorization, authentication/authorization, per-owner storage isolation, CSRF/upload/path defenses, HTTP CSP, privacy/export review, explicit schema migrations, dependency/runtime advisory checks and production browser/accessibility/scale testing.
- No commits, remote creation, push, upload, deploy, portfolio edit, public release or assignment submission performed.

## Sources

[1] https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CSP — MDN: Content Security Policy
    > "However, this option does not support all CSP features."
[2] https://sqlite.org/security.html — SQLite: Defense Against The Dark Arts
    > "Applications that read or write SQLite database files of uncertain provenance should take precautions enumerated below."
