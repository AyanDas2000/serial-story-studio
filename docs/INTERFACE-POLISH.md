# Serial Story Studio interface polish

## Outcome and boundary

Implemented the product-facing Operate interface: visible Plan, Write, Continuity and Models; honest blank prerequisites; restored editor-first entry; approved intention; saved/unsaved manuscript; scoped feedback and explicit acceptance; accepted-source memory. Writing instructions come before optional model/catalog inspection. Raw JSON stays in collapsed details.

Root: `C:\Users\ayan1\AppData\Local\hermes\cache\scratch\story-interface-staging-fde6df22a1`.

The later interface request supersedes PRODUCT.md's historical CLI milestone. No original project, DB, server or browser session was read or changed. No paid/catalog traffic, credential reads, packages, remote fonts, global settings, shared memory writes, Git changes or deployment. All test/server Python imports were asserted under staging. The original virtual environment was not needed.

## Exact modified source paths

- `C:\Users\ayan1\AppData\Local\hermes\cache\scratch\story-interface-staging-fde6df22a1\serial_story\assets\studio.html`
- `C:\Users\ayan1\AppData\Local\hermes\cache\scratch\story-interface-staging-fde6df22a1\serial_story\assets\studio.css`
- `C:\Users\ayan1\AppData\Local\hermes\cache\scratch\story-interface-staging-fde6df22a1\serial_story\assets\studio-layout.js`
- `C:\Users\ayan1\AppData\Local\hermes\cache\scratch\story-interface-staging-fde6df22a1\serial_story\studio\server.py`

The server delta is ONE fixed ROUTES entry: `'/studio-layout.js': ('studio-layout.js', 'text/javascript; charset=utf-8'),`.

Integrate that entry, NOT the entire server file, into the original worker's version. Preserve their financial/consent changes. Existing studio.js, authoring, merge, budget, repository, service, store and APIs were not modified.

The layout observes core-owned saved-copy output and visibility. It never fetches, changes form values, replaces private state, dispatches authoring actions, accepts prose or confirms memory. Stable form/action IDs are preserved and unique. Dirty/CAS/approval semantics remain owned by the core.

CSS preserves shared paper/graphite/deep-blue tokens, the existing IBM Plex Sans font route, tabular numerals, visible focus, a 72ch manuscript maximum, responsive navigation and token-based motion with reduced-motion override. Light only.

## Added test/fixture paths

- `C:\Users\ayan1\AppData\Local\hermes\cache\scratch\story-interface-staging-fde6df22a1\tests\test_studio_layout.py`
- `C:\Users\ayan1\AppData\Local\hermes\cache\scratch\story-interface-staging-fde6df22a1\tests\studio_layout_test.js`
- `C:\Users\ayan1\AppData\Local\hermes\cache\scratch\story-interface-staging-fde6df22a1\tests\studio_browser_qa.js`
- `C:\Users\ayan1\AppData\Local\hermes\cache\scratch\story-interface-staging-fde6df22a1\tests\studio_demo_bootstrap.py`
- `C:\Users\ayan1\AppData\Local\hermes\cache\scratch\story-interface-staging-fde6df22a1\docs\INTERFACE-POLISH.md`

Vertical RED/GREEN presentation slices: navigation/ID contract, saved intention/prerequisites, restored editor-first entry, action discoverability and contextual focus. Each was observed failing before its implementation.

Final studio suite: **35/35 passed**, including original dirty conflicts, acknowledged-version races, HTTP boundaries, approval, scoped feedback, acceptance idempotency, memory confirmation and paid-off manual workflow. Node syntax check passed.

Full suite: **123/128 passed, 2 failures and 3 errors**, all five remaining failures font-dependent graph/export/review tests caused by the missing staged font. The first run also exposed 11 missing-directory errors in existing Merge tests; creating the staging-only synthetic test directory resolved those. The fake financial authoring suite then passed **14/14**. No real Merge startup was enabled.

Logs under `C:\Users\ayan1\AppData\Local\hermes\cache\scratch\story-interface-staging-fde6df22a1\docs\interface-qa`: studio-suite-results.txt, full-suite-results.txt and browser-qa-results.json.

## Two actual SQLite states

Blank: `C:\Users\ayan1\AppData\Local\hermes\cache\scratch\story-interface-staging-fde6df22a1\local\interface-qa\blank-synthetic.db`.

Final demo: `C:\Users\ayan1\AppData\Local\hermes\cache\scratch\story-interface-staging-fde6df22a1\local\interface-qa\fictional-demo-v3.db`.

The final fixture uses genuine existing manual/fake workflows: approved intentions, one accepted manual episode, one unconfirmed source-linked memory proposal, an offline fake draft followed by a saved fictional edit, and revision-scoped feedback. Pending manuscript: 433 words, text version 2; provider fake, next episode 2, accepted count 1. All story content is labeled FICTIONAL SYNTHETIC DEMO, not real model output or model-quality evaluation. The manual receipt honestly records manual provenance.

The explicit bootstrap accepts the first fictional episode only to provide an accepted source. The interface automates neither acceptance nor confirmation. Earlier fictional-demo.db and fictional-demo-v2.db are retained agent-created synthetic intermediate artifacts, not the recommended fixture. No private/existing DB was used.

Bootstrap a NEW filename from staging:

```powershell
Set-Location 'C:\Users\ayan1\AppData\Local\hermes\cache\scratch\story-interface-staging-fde6df22a1'
& python.exe 'C:\Users\ayan1\AppData\Local\hermes\cache\scratch\story-interface-staging-fde6df22a1\tests\studio_demo_bootstrap.py' --db 'C:\Users\ayan1\AppData\Local\hermes\cache\scratch\story-interface-staging-fde6df22a1\local\interface-qa\fictional-demo-new.db'
& python.exe -c "import serial_story; from pathlib import Path; assert Path(serial_story.__file__).resolve().is_relative_to(Path.cwd()); from serial_story.studio.server import create_server; s=create_server(Path('local/interface-qa/fictional-demo-new.db'),port=18768,writes=True,merge_catalog=False,merge_generation=False); s.serve_forever()"
```

Bootstrap refuses existing DBs or paths outside staging local/interface-qa. Never enable real Merge generation here: its module-relative ledger must not become another real spending allowance.

## Browser and screenshots

Installed headless Edge used fresh staging-only QA profiles, never a user profile. Actual checks passed: all four areas, restored writing entry, arrow-key focus, saved intention, saved/unsaved indication, acceptance disabled while dirty, unsaved text retained through navigation and refresh, paid-source explanation OFF, and no horizontal overflow at 1440/768/390. Browser QA made no authoring POST, catalog or provider request. Browser.close ended QA Edge.

Screenshot directory: `C:\Users\ayan1\AppData\Local\hermes\cache\scratch\story-interface-staging-fde6df22a1\docs\interface-qa`.

Final captures read and inspected:
- blank-after-1440.png, blank-after-768.png, blank-after-390.png
- fictional-write-after-1440.png, fictional-write-after-768.png, fictional-write-after-390.png
- fictional-continuity-after-1440.png, fictional-models-after-1440.png

Before: supplied `C:\Users\ayan1\AppData\Local\hermes\cache\scratch\current-studio-preview-e6536a73fa\current-desktop.png`, blank-before-1440.png and *-review-before-*.png in the capture directory.

One bounded inspection/fix pass brought author actions above the editor, bounded editor height, moved catalog inspection after instructions, and exposed the actual 400-700-word acceptance requirement. Final captures were inspected again.

## Design audit and integration gates

Signature: intention-to-accepted-evidence spine across the approved intention, author review desk and memory ledger. No gradients, ornamental icons, nested cards, invented credits or quality scores. Slop diagnostic: **0/10**.

Premium Test writing desk before: **16/20**, fails #5 (primary action below viewport), #6 (font), #9 (four type sizes), #18 (complete loading/error coverage). After: **17/20**, #5 fixed; #6/#9/#18 remain. This is a documented hold, NOT a premium or release pass. No open-ended extra loop.

Token contrast: graphite/white 15.95:1, steel/white 6.36:1, steel/paper 5.92:1, white/deep-blue 9.10:1. Reduced motion and screen readers were not independently browser-certified. Extreme-name browser testing was not run; wrapping is authored.

Design lint reported 45 B6 hits across assets, mostly JavaScript identifiers null/payload rather than visible text, including one local variable in the new layout. The lint command did not pass; identifier hits are not presented as visible-copy defects.

Parent integration gates:
1. Integrate only the three frontend assets and one server route into the original worker's financial/consent fixes. Tests/docs may accompany them. Do not integrate staging DBs or browser profiles.
2. Staging lacks `serial_story/assets/IBMPlexSans[wdth,wght].ttf` and its license. Existing font family/route are preserved. Browser font status is error, so captures use fallback. Preserve/restore the already bundled licensed font at integration, then rerun font tests and captures. No font was downloaded or read from original.
3. Independently run merged author journeys: saved feedback -> explicit revision -> explicit acceptance -> separate memory review, plus dirty/CAS refusals. Browser QA intentionally did not mutate or accept the pending episode.
4. Existing core question-mark separators in titles/feedback/receipts/memory predate this change. studio.js was deliberately not modified.
5. Complete loading/error, reduced-motion, assistive-technology and extreme-content checks; resolve the Premium Test failures before a premium/release claim.

QA servers are stopped after verification. No production, paid Merge, publication or deployment clearance is claimed.
