# Fresh submission smoke test, 8 October 2026

## Scope and verdict

Main practice-mode author workflow passed in a fresh isolated local shelf. This is a surface smoke test, not an exhaustive audit or proof of live-model story quality. No paid calls, original author stories, credentials, application source, or existing reviews were changed. No submission was sent.

Current source HEAD at launch: `320f5f29076a522018df7226349c927d6710c9e0` (feature/ledger-first). Launched from the repository using `.venv/Scripts/python.exe try_it.py --port 8794 --stories local/submission-smoke-2026-10-08`. Browser: Playwright Chromium, 1280x720. Read CONTEXT-TRANSFER.md and FRAMEWORK.md first. Test window approximately 21:04–21:13 IST. Practice writer only.

## What works, observed on the rendered surface

| Flow | Result |
|---|---|
| First-run onboarding | Welcome modal, practice/no-charge notice, sample series visible; modal closes. |
| New series | Created Submission Smoke through New series and Create series. Separate shelf folder created. |
| Direction | Premise and spine wizard advances; explicit Adopt this direction leads to Plan. |
| Plan | A blank episode2 line prevented adoption with a clear message. Completing30lines allowed adoption. |
| Draft | Start drafting confirmation identifies practice/free; scripted episodes1–3 arrive and remain unapproved. |
| Edit/save | Paragraph1 edited and Save edit persisted it. Episode word count changed351→324 and origin label became Edited by you. |
| Downstream warning | Earlier paragraph edit marked episodes2–3 may no longer fit. |
| Approve | Two-step Finish flow locks exact saved text. Episode1 became approved; paragraph edit controls absent. |
| Memory gate | Preview showed7quoted claims; explicit Save7storychanges required separately from approval. |
| Memory provenance | Memory7 displays claims. Selecting the first scene opens Source with Ep1/paragraph1 and highlighted exact quote Leena is a court recorder from the author-edited paragraph. |
| Source navigation | Go to paragraph returns to Write episode1 and highlights the approved paragraph. |
| Refresh persistence | Reload retained adopted plan, drafts, edited/approved paragraph,7saved facts and stale warnings for episodes2–3. |
| Browser errors | Playwright console inspection after refresh returned0errors and0warnings. |

## What does not work or cannot be claimed

- The practice writer follows a fixed script. Despite the Mira/library direction, it produced Leena/Darin prose and names, correctly accompanied by a new-names warning. This mode demonstrates the workflow, not adherence to an arbitrary story premise or live AI quality.
- Practice episode1 is351words before editing,324after, below the selected550–900range. The UI warns outside range but allows human approval. Do not describe this smoke fixture as satisfying an assignment400–700word output requirement.
- Scripted titles read The1thturning,The2thturning,The3thturning (spaces present in UI). Awkward practice-only copy, not a workflow blocker.
- The desktop1280x720Memory source panel overlays the lower screen; the full paragraph is visible and source navigation works, but additional long-source scroll behavior was not tested.
- No fresh live-provider, paid-budget, provider-error/retry, concurrency, secret enforcement,100episode drafting, claim correction, mobile, keyboard-only, screen-reader, macOS/Linux or restart-mid-job proof. Browser reload is tested; server restart is not.
- No new app blocker was found in this bounded happy-path test. Assignment completeness must be judged separately from this UI smoke test.

## Evidence

Repository-relative artifacts (all fresh and isolated):

- `output/playwright/submission-smoke-2026-10-08/offline-author-flow.webm`:243.08seconds,4,444,438bytes; starts at direction adoption, shows plan validation/adoption, draft, author edit/save, approval and memory save, ends at refresh. Silent automated practice-mode demonstration, not a live model recording.
- `output/playwright/submission-smoke-2026-10-08/memory-source.webm`: short follow-up showing source quote and Go to paragraph after refresh.
- `output/playwright/submission-smoke-2026-10-08/01-plan.png`: plan surface.
- `output/playwright/submission-smoke-2026-10-08/02-memory-source.png`: highlighted quote from author edit, visually inspected.
- `output/playwright/submission-smoke-2026-10-08/03-approved-edit.png`: approved paragraph after source navigation.
- Playwright CLI timestamped snapshots under `.playwright-cli/`,2026-10-08T15:34–15:42UTC; these contain only the isolated fixture.

The main video is under five minutes but contains automation waiting/typing and the visibly scripted content limitations above. Use an accurate caption if shared. The separate source clip can be appended while remaining under five minutes if its combined duration is checked.

Combined reviewer video: `output/playwright/submission-smoke-2026-10-08/offline-hitl-demo.webm`,250.16seconds (4min10.16seconds),4,738,600bytes. Concatenated without re-encoding; duration verified by ffprobe. Includes source quote and return to approved edited paragraph.
