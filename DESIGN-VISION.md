# Design vision and implementation boundary

## Authorship and development approach

This project was built largely using LLM-powered coding tools. Ayan did not manually implement every component. Ayan's main contribution was defining the core logic and author workflow, making design and tradeoff decisions, and directing iterations and workarounds. The implementation and supporting code were produced substantially with LLM coding assistance.

## Why this flow

As a serial grows, both the model and the human writer have more characters, events, plans and revisions to track. The design makes those states visible and gives the author explicit control over what governs the story and what becomes accepted text. It is an assisted writing environment rather than an autonomous writer that silently makes irreversible narrative decisions.

Adopted direction and plan guide generation. Drafts remain editable proposals. Author approval fixes the exact accepted prose. Facts extracted from that prose remain proposals until the author confirms them, with source quotes available for inspection. Upstream edits flag dependent later work so the author can repair or redirect it. Chat and rewrite suggestions assist without acquiring the author's authority.

## Backend now

- A standard-library Python server exposes explicit author commands to the browser and author CLI. SQLite stores each series' revisions, selections, approvals, jobs and claims.
- Each draft freezes the governing direction, episode intention, adopted style and exact revisions of earlier prose. Accepted earlier prose takes precedence; otherwise current selected drafts may support a provisional chain. Dependency hashes and version checks prevent stale results from silently replacing current work.
- Author edits create revisions. Approved prose is immutable. Separate extraction and confirmation create source-linked facts, rather than immediately accepting model claims.
- Provider calls run outside the database transaction. Known-not-sent failures, unknown outcomes and completed-but-unusable answers have different recovery paths. Unknown outcomes pause for human resolution rather than automatic retries.
- Merge calls reserve estimated cost before sending and settle afterward. Each series has its own local spending ledger; the supplied key's provider-side limit is separate.
- Episode length is an intentional per-series setting: shortest, target and longest. It guides future prompts and warnings. Existing prose is not automatically rewritten when the range changes.

## Long-story vision versus current implementation

The explicit state and source trail make it easier for the author to manage context, corrections and direction as the work grows. They do not yet solve model context growth. Current draft requests still include all preceding prose. The Memory ledger is for author inspection and does not feed the writer. Bounded retrieval, summaries and semantic consistency checking remain unfinished, and episode-150 or 200 consistency has not been demonstrated.
