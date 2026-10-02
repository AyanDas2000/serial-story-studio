# Serial Story Studio: product direction proposal

Status: proposed direction for discussion, not implementation permission or release approval.
Prepared 2026-10-01. Independent Droid/Opus review pending when first written.
Scope: local single-author serial-writing product; no provider calls, credentials, publication or new dependencies are authorized by this proposal.

## 1. The product we should actually build

**A writer's room for long serials: direct the next episode, understand what the story has established, and see the consequences of a change before approving it.**

The promise is not "AI writes 200 episodes automatically." It is "You stay the author; the system carries the continuity, evidence and workflow."

The graph is an evidence lens, not the main writing surface. A beautiful graph alone does not solve drafting, feedback, suspense or recovery. The next-episode workspace should be the default screen; graph and storyboard answer questions raised there.

Positioning is a design hypothesis, not a verified market claim. The initial user is Ayan, learning and directing a local demonstration. We must validate usefulness with actual writing sessions before claiming product demand.

## 2. Three possible products, and the recommendation

| Direction | Benefit | Failure mode | Decision |
| --- | --- | --- | --- |
| Autonomous serial factory | Impressive volume | Human control becomes an afterthought; errors compound; call count grows | Do not make this v1 |
| Graph-first story encyclopedia | Beautiful, explorable memory | The author spends more time tending a database than writing | Use as a supporting view |
| Human-directed episode studio | One complete useful loop with visible authority | Requires good review UX and disciplined memory | Recommended core |

Keep one story, one active narrative history and sequential episodes. Do not start with agents debating in parallel, collaborative permissions, billing or a second graph database.

## 3. The four surfaces

### A. Write: the next-episode workspace

Show the current episode, approved objective, selected cast/places, last hook, due story promises and relevant continuity. One primary action appropriate to the current state: propose a direction, approve a brief, draft, review, accept final prose, or review memory.

For direction selection, display a recommended path and one genuinely different alternative as short briefs, not two full generated episodes. Each brief explains narrative purpose, expected change, continuity risks and which existing thread it develops. The author may write a brief directly instead of paying for alternatives.

The draft dominates the screen. The inspector shows evidence-backed issues and what the model was told. Editing and redraft requests are separate actions. Rejection preserves the candidate and feedback without advancing the episode.

### B. Storyboard: the unfolding story

Two visibly separate lanes: **established history** and **planned future**. A developed 200-episode arc contains coherent episode purposes, major turning points, character transformations, reveal windows, promises/payoffs and an ending, not 200 numbered placeholders. Detailed prose is generated sequentially; scene detail can be elaborated just before drafting.

Changing a future direction is easy and versioned. Changing accepted history is a different operation with a warning and downstream invalidation. No drag gesture or conversational message should silently retcon accepted prose.

### C. Memory: the evidence graph

Default to a useful local neighborhood: selected character or situation, relevant facts, and their accepted sources. Never begin with every node in a 200-episode story.

Signature question: **"Why does the system believe this?"** Select a fact to see its exact passage, episode, accepted revision, human confirmation and supersession history. Follow another connection to see the character, scene or related entity.

Useful views:
- Character: current situation, relationships, knowledge and linked evidence.
- Situation: who is present, where/when it occurs and the facts established there.
- Thread: setup, developments, open question, planned payoff and source passages.
- Episode: what changed and what was intentionally left unresolved.

Search/list/table are equal first-class alternatives to the graph. All filters and source inspection must work without dragging or depending on color alone. Future plans use a separate lane/style and explicit labels; they must not look like historical facts. A filtered display says what is hidden.

### D. Receipts: control, recovery and cost

Show approvals, revisions, saved state, context basis, unresolved checks, reserved/settled/uncertain usage and restart status. These are the trust layer, not a developer-only debug screen. A restart should offer "resume review" rather than regenerate by default.

## 4. The memory distinction that matters most

A passage provides provenance. It does not automatically prove literal truth.

Example: episode 4 says "Mara told Ivo that the captain was dead." The system must not infer that the captain is dead, that every character knows it, or that the reader has seen proof. Dialogue, deception and unreliable narration make those different claims.

The full product needs distinct concepts, introduced incrementally:

| Concept | Example | Authority |
| --- | --- | --- |
| Author-approved story bible | World rule or background secret | Explicit setup approval; labeled author-only until revealed |
| Established story event/state | Ivo arrives at the harbor | Final accepted prose plus reviewed interpretation |
| Character belief/knowledge | Mara believes the captain died | Attributed character, proposition, source and certainty |
| Reader-visible information | The reader hears Mara's claim | Narrative presentation, not global truth |
| Future intention | Reveal the captain's survival later | Approved direction, never automatically canon |
| Open promise/thread | Who forged the harbor map? | Source-linked setup, development and resolution |

Author secrets must exist before their first reveal without pretending they were already established in accepted episodes. This requires a new labeled setup-source type and visibility rules; the current fact ledger only admits accepted prose and must not be casually weakened. Registry identity/roles do not prove narrative events. An imported story bible is not canon until the author approves it.

Use a small typed vocabulary for high-impact claims rather than synonyms such as alive/status/life-state silently competing. Relationships and knowledge are multi-valued, not a single generic "knows" property. Distinguish episode order, in-world time, and the time at which a fact is valid so a flashback cannot resurrect a dead character in the present.

These richer semantics are proposed. The current manual ledger does not implement reliable knowledge boundaries, reader visibility, thread tracking or in-world chronology.

## 5. The complete episode loop

1. Read the approved arc band, current facts, active directions, due threads, selected cast and relevant evidence.
2. Propose short direction options, or accept a human-written brief.
3. Human approves an episode brief. Persist its exact memory/history/direction basis.
4. Construct a bounded context packet and save its inclusion/omission receipt. Essential context overflow pauses before a call.
5. Reserve a conservative worst-case charge in one shared project ledger, then draft.
6. Run deterministic checks first; a model critic, when budget allows, reports supported/contradicted/unknown findings with source IDs and a versioned quality rubric.
7. Allow at most one automatic rewrite initially. Repeated criticism without improvement returns to the human. Human review can continue without a paid call.
8. Human accepts, edits or rejects. Persist final accepted prose atomically and idempotently. Cost exhaustion never causes automatic acceptance.
9. Propose a memory delta from **final** prose, not the pre-edit draft. Prioritize changed high-impact facts, knowledge, relationships and open threads. Show evidence beside each proposed change.
10. Human confirms/corrects the delta. A no-change decision is an explicit receipt, not missing data.
11. Mark the episode ready for continuation only after a memory-review receipt, or an explicit degraded/manual continuation decision recorded as such. Never silently call incomplete memory complete.

A checkpoint should distinguish accepted prose with memory review pending from accepted-and-ready. A crash during digestion resumes that review; it does not rewrite the episode or silently advance with old memory.

Review fatigue is a product risk. Aim for a short change-focused panel, batch review of low-risk evidence-backed changes, and mandatory individual review for identity, death, location/time, secrets, beliefs, relationships and retcons. Do not equate a bulk approve button with proven extraction coverage. Measure review time and missed changes in actual sessions before choosing defaults.

## 6. Feedback is a durable artifact

Persist feedback with target revision, scope, reason and applicability. Distinguish "fix this sentence" from "for future episodes, delay the romance." Episode-local edits must not become global rules by accident. Global preferences should not become historical facts.

A future conversational command becomes a previewed patch: target, proposed change, reason, affected future material and cost estimate. The author confirms it. The model has no direct authority to execute arbitrary SQL, mutate canon or broaden file/network access.

Historical edits should conservatively invalidate later dependent material, retain the old history and require repair review. Selective automatic repair is later scope and needs measured extraction coverage.

## 7. Bounded architecture

Keep domain services in Python and canonical records in SQLite. The graph is a view of those records, not independent state. A workflow framework can be reconsidered if actual durable branching becomes difficult; adopting one is not a product milestone by itself.

Planner, writer, reviewer and memory curator are role contracts with explicit inputs/outputs. They may be sequential calls to one chosen model; four agent names do not require four autonomous workers. Deterministic validation and the human author retain authority.

A minimal full-product data spine comprises:
- Story setup and approved/versioned arc/episode briefs.
- Cast/place registry and source records with explicit source type.
- Drafts, final accepted revisions and scoped feedback/approvals.
- Typed claims, knowledge/beliefs, situations, chronology and threads.
- Memory-delta/checkpoint receipts and context provenance.
- Project-wide reservations, settlements and uncertainty.

The current implementation covers a narrower manual slice. Introducing these entities requires explicit migrations and tests, not renaming existing fields and claiming completion.

## 8. Security and dependency principles

Treat story prose, imports and model output as untrusted data, including malicious instructions embedded in a story. The model proposes; the application validates; the human authorizes.

Keep fake mode default. Real calls need explicit provider/access/model/pricing approval; send necessary story context only. All planning, review, rewrite, extraction and retry calls share the USD 1 project ceiling across databases, not one fresh budget per database. Character limits are not token limits. A real adapter needs model token accounting and conservative output/price bounds; provider billing still cannot be guaranteed solely by a local ledger.

No unknown project imports, remote font/script dependencies, hosted accounts or browser-executable model HTML. Use standard library where adequate; any dependency addition gets a provenance/license/maintenance/security review and pinned reproducible install. Reputation alone is not a security guarantee.

Maintain safe no-overwrite exports, inert text rendering, CSP, trusted-local SQLite handling, bounded file size/path rules, backups/restore checks and least-privilege tools. Once there is an editable local server, separately review loopback binding, origin/CSRF protection, path traversal and authentication decisions. A saved offline read-only page does not cover that attack surface.

Security release language stays scoped: local checks, independent code review, product-idea review and hosted release are different gates. Opus reviewing this idea is not a penetration test or clearance of the app.

## 9. What "best version" means: evidence, not feature count

### Required demonstration

- A real developed 200-episode arc consistent with the chosen premise, not fixture beats.
- Fifteen sequential accepted 400-700-word episodes.
- Two observable human interventions whose consequences appear in later work.
- Exit and resume after episode 12 with correct history and pending state.
- Source-linked memory with a demonstrable character/situation/evidence path.
- Recorded full-project spending and clearly separated assistant-development allowance.

These are outstanding, not delivered by the present fake fixture. Whether real generation fits USD 1 must be measured after pricing/access approval. If it does not, reduce paid calls, supply human material or openly revisit scope/budget; do not assume subscription assistance can be relabeled as USD 1 story generation.

### Acceptance tests for the product, not just the code

- **Truth:** a character's lie does not become global canon; a plan does not become an event; a secret is not leaked before approval.
- **Continuity:** long-distance callbacks and due threads can be retrieved with sources even when old prose is absent from the prompt.
- **Control:** two interventions produce visible scoped changes; stale drafts are blocked.
- **Recovery:** crashes during generation, acceptance and memory review resume the correct checkpoint without duplicate advancement or charges.
- **Time:** flashbacks do not overwrite present state; supersession preserves valid-time and source history.
- **Budget:** creating another database cannot reset the real project allowance; timeout uncertainty remains reserved.
- **Safety:** story prompt injection cannot invoke tools or canon writes; graph labels remain inert; untrusted database/import provenance is handled explicitly.
- **Usability:** the author can locate a fact's source, explain what changed, reject a proposal and resume without developer help.

Build a small adversarial story corpus first: lie, mistaken belief, secret, flashback, contradictory report, death, resurrection rumor, edited final draft, future direction change and no-change memory review. Define expected outcomes by hand. Measure errors separately from source-link completeness; a source link alone does not prove a correct interpretation.

## 10. Sequence and stop lines

### Milestone A: prove the human loop

Complete the current local security review before new risky code. Keep fake fixtures as tests. Select an actual premise with Ayan; create a coherent approved arc and story bible. Add brief/feedback and accepted-but-memory-pending checkpoints. Prove a short manual episode loop, including one intervention and restart.

### Milestone B: prove continuity and affordable generation

Implement typed high-impact memory/threads and context receipts needed by the adversarial corpus. Add a shared project ledger. Only after explicit approval, integrate the exact real gateway/model, validate pricing/output limits and perform a bounded generation preflight. Run the required demonstration with transparent evidence. Do not promise the full call graph fits USD 1 before measuring it.

### Milestone C: make the working loop beautiful

Build the editable next-episode workspace around the proven domain services, with storyboard and focused graph as supporting views. Inspect desktop/mobile/keyboard states, empty/error/loading/pending states, contrast and motion. Conduct observed author tasks. No production UI completion claim without real inspection.

### Later, not v1

Multi-user collaboration, billing, hosting, audio generation, parallel competing episodes, adaptive preference learning, selective retcon repair and an unrestricted conversational operator. A website demo remains a separately approved publication task.

## 11. Decisions still requiring Ayan

Premise/genre/tone; language and audience; the initial cast/locations; acceptable review workload; how much of the arc should be authored by hand; real provider approval; and whether author-only setup canon belongs in the first extension. These are creative/product decisions, not missing credentials to be searched for.

Recommendation: approve a bounded next slice, not this whole roadmap. The core should succeed with one author, one story and one complete episode before the architecture expands.
