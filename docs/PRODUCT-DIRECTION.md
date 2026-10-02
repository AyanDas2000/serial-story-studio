# Serial Story Studio: recommended product direction

**Decision document, not implementation approval.** Prepared 2026-10-01 after one independent Droid/Opus 5.5 product-idea review. This is the parent's revised synthesis; it has not been sent for a second review. It does not replace the employer assignment or claim independent security clearance.

## 1. The thesis

**A local writer's room for a long serial: the author directs each episode; the system makes accepted history, proposed changes and the next draft's context inspectable.**

Its signature experience:

> Accept the episode. See what changed, with the exact passages. Confirm the interpretation. Begin the next episode knowing what it will rely on.

This is more specific and useful than "an autonomous 200-episode writer" or "a graph of story facts." It preserves Ayan's enthusiasm for a beautiful, explainable graph without making graph maintenance the author's main job. Usefulness and positioning remain hypotheses until actual author sessions.

We should not promise a preview of every downstream consequence of an edit. The current prototype has no complete dependency coverage or historical repair. Until that exists, show known dependencies, unknown coverage and conservative invalidation, not simulated certainty.

## 2. What the independent reviewer changed

Droid was invoked through its native CLI using the exact model `claude-opus-5-5`, high reasoning, in a new one-turn session. Official JSON returned success; the matching session settings confirmed the model. The review used the prepared proposal packet. No fallback or further inference was invoked. Its main verdict was **coherent, but changes are needed**.

| Reviewer challenge | Decision in this version |
| --- | --- |
| A graph is not a writing workflow | Put episode review and the memory delta first; keep the graph as an evidence lens |
| A citation does not establish narrative truth | Distinguish established events, reports, beliefs and approved author-only setup |
| Full knowledge/chronology modeling is too much for the first useful slice | Limit the first extension to high-impact claims and explicit temporal/secret scope; no general ontology |
| Review fatigue can destroy usefulness | Measure review minutes and missed changes; prioritize changes without concealing the rest |
| Backend-first sequencing delays author feedback | Use an existing-editor file round-trip for the next slice; an editable server can wait |
| USD 1 does not support an assumed critic/alternative/extraction loop | Start with human briefs, manual memory and no paid critic; measure before adding calls |
| A per-database cap is not a project-wide cap | Treat a shared ledger as mandatory before any real-provider path |

We do **not** adopt every suggestion literally:
- Narrated prose can be unreliable too. A `narrated` label must not silently mean objective truth. Record the claim and the human-approved interpretation.
- A review target such as eight changes is a usability hypothesis, not a hard cap that drops the ninth important change. Show remaining items and require an explicit handling decision.
- An "nothing else changed" attestation records the author's decision; it does not prove extraction completeness.
- Human-written prose is valid for testing the product loop, not an undisclosed substitute for a required model-generated demonstration.
- Timing flags are a limited safeguard, not a solution to all flashback chronology. Either constrain the initial demonstration's chronology explicitly or stop when a case is unsupported.

## 3. The four product surfaces

### Write: the default workspace

The episode text gets the most space. Alongside it: approved purpose, active cast/places, last hook, relevant continuity, active feedback and due story promises. The interface has one state-appropriate primary action, not a generic "generate everything" button.

A human-written brief is the initial default. Short generated alternatives and a model critic are optional later budget choices. Review should distinguish line edits, episode-local requests and future-standing directions. The author sees what will be sent to a model before authorizing a call.

### Storyboard: history and intention, side by side

Two separate lanes: **what happened** and **where we intend to go**. Major arc turns, planned reveals and future directions are not established facts. A developed 200-episode plan needs coherent purposes, stakes, progression and payoff; 200 numbered fixture beats do not meet that standard. Scene detail can be expanded just in time without claiming the arc is complete when it is not.

Future edits are versioned intentions. Historical edits are explicit retcons with retained old versions and repair review. Do not put both behind the same casual drag gesture or chat command.

### Memory: focused evidence, not a giant hairball

Start from a question or selected character/situation, not every node in the story. A fact or claim leads to the related character, situation, accepted episode, exact passage and confirmation history. Superseded states remain inspectable. Future directions are unmistakably labeled and visually separate.

The graph's teaching sentence is:

> This is the annotation, this is who or what it concerns, this is the scene, and this is the accepted passage behind it.

Search, a list/table and keyboard source inspection are equally important. The graph must work without drag-only controls, motion or color-dependent meaning. A filtered view reports what is hidden. Thread and timeline views are valuable later, once those records actually exist.

### Receipts: visible control

Show the current checkpoint, saved candidate, approval basis, unresolved issues, included/omitted context and cost reservations. After a restart, resume the pending task rather than generate again. Trust is part of the product experience, not a debug panel buried in the CLI.

The immediate writing surface can be safe Markdown export/edit/import in the author's existing editor. This is not the final beautiful UI; it lets actual writing tasks shape that UI before a server adds attack surface.

## 4. What memory means in a story

Consider accepted prose: **"Mara told Ivo that the captain was dead."**

That establishes a report. It does not establish that the captain is dead, that Ivo believes Mara, or that every character knows the claim. A source link alone cannot answer those questions.

The full product must distinguish:

| Layer | Meaning | Example |
| --- | --- | --- |
| Approved author setup | Explicit story-bible background/rules, possibly hidden from the reader | The captain secretly survived |
| Established event/state | Human-reviewed interpretation of accepted prose | Mara meets Ivo at the harbor |
| Attributed report | Something a speaker/source claims | Mara says the captain died |
| Attributed belief/knowledge | What a particular character believes or knows, with evidence and uncertainty | Ivo doubts Mara's report |
| Reader presentation | What has actually been revealed, not everything the author knows | The reader hears the report but not the survival secret |
| Future intention | What the author wants next | Reveal the captain's survival later |
| Open story promise | A setup/question requiring development or payoff | Who forged the harbor map? |

For the next slice, avoid building a general belief engine. Add a small, validated claim-kind vocabulary, attribution where needed, reviewed interpretation and explicit unsupported/unknown states. Do not hide different claims behind synonyms or a single multi-purpose `knows` property.

Author-only background needs its own approved source type/registry, not fabricated episode evidence or a weakened accepted-source constraint. Until that extension is approved and implemented, the existing fact ledger remains accepted-prose-only.

Episode order is not in-world order. A past scene must not silently replace present state. The early demonstration can explicitly use linear chronology; unsupported flashbacks must be flagged rather than interpreted as safe.

Secret visibility also needs a deliberate policy. The planner/critic may need author-only information; a writer must not reveal it before the brief authorizes that reveal. Initially, do not place secret values in a drafting packet without authorization; use a limited constraint or stop if consistent drafting needs an unsupported secret-aware route. A source inspector may remain author-facing without implying the reader or characters know its contents.

## 5. The core loop and its authority

```text
Human brief + context review
          ↓
Approved brief and frozen basis
          ↓
Human prose or authorized, reserved model draft
          ↓
Edit / reject / request revision
          ↓
Final prose accepted exactly once
          ↓
ACCEPTED — MEMORY REVIEW PENDING
          ↓
Review delta OR explicitly record no change
          ↓
READY FOR NEXT EPISODE
```

A prose acceptance says "these are the final words." A memory confirmation says "this is how those words affect the story state." These may be adjacent on one screen, but they are separate decisions. Extraction must use the edited final prose, not the discarded draft.

If the author permits continuation with incomplete memory, that is a separately named degraded decision with visible risks. Do not display it as complete. A crash between prose acceptance and memory completion resumes memory review, not drafting.

Memory review shows additions, changes, resolved promises and removals/supersession, each with a passage. Prioritize high-impact changes, but make omitted/remaining review work visible. A no-change receipt binds to the exact accepted revision. Corrections produce durable audit history.

Feedback is also durable: target revision, scope, reason, applicability and status. "Change this sentence" must not become a permanent style rule. "Delay romance until trust develops" must appear in future context until retired. Neither is a historical fact.

Failures remain honest:
- Rejection does not advance canon.
- Partial output stays an incomplete candidate.
- A timeout retains uncertainty in the budget; no automatic paid retry.
- A changed basis makes the candidate stale; show the reason and offer an explicit re-review/regeneration path rather than hiding the refusal.
- Budget exhaustion pauses paid work and preserves manual review options. It never approves a flawed episode.

## 6. What is necessary now versus later

| Need | Next bounded slice | Full product / later |
| --- | --- | --- |
| Author control | Human brief, edit/reject/accept, scoped feedback | Conversation-generated patch previews |
| Memory | Manual reviewed delta, claim kinds, exact source, no-change receipt | Automated suggestions with measured recall/precision |
| Recovery | Accepted-but-memory-pending checkpoint and resume | Complex branching and historical repair |
| Continuity | Relevant context receipt, simple explicit chronology limits | Threads, selective knowledge, richer temporal validity |
| Writing surface | Markdown round-trip with revision/hash/basis checks | Inspected editable local workspace |
| Graph | Existing source inspector and focused view | Thread/timeline views once modeled |
| Real generation | Not required to test the next manual slice | Explicit provider approval, shared ledger and price/token preflight |
| Critic/alternatives | Human feedback, no paid automatic loop | Add only if measured quality and budget justify it |

The existing implementation is a fake-only foundation with manual memory and a read-only graph. The pending-memory continuation gate, typed narrative claims, general threads/knowledge/time, real adapter and editable workspace are not delivered features.

## 7. The recommended next milestone

**Run one complete useful author loop twice, with a restart between acceptance and memory completion.**

Concrete acceptance criteria:
1. The author supplies an episode brief and receives a readable context receipt.
2. Prose is drafted or supplied, edited and accepted; author/model provenance is labeled.
3. A reviewable manual delta distinguishes established state from a report/belief, or records an explicit no-change decision.
4. The next episode is not silently drafted from incomplete memory.
5. Scoped feedback appears in the next context or is explicitly retired.
6. A restart in the pending-memory state resumes exactly there; it does not duplicate acceptance.
7. The author can follow a memory annotation to character/situation and exact accepted passage without developer assistance.
8. A small hand-labeled adversarial corpus probes lies, unreliable narration, secrets, past-scene misuse, contradictory reports, death rumors, human edits, stale directions and no-change review. Expected interpretations are defined before automated assertions.
9. Record actual review minutes, missed changes and time to locate evidence. Product targets are hypotheses until observed.

Use the current fake path or human prose initially. Keep fixtures explicitly labeled. Do not spend the story budget to discover whether a review screen is usable. This milestone is a recommendation requiring Ayan's scoped implementation approval.

## 8. What makes the eventual demonstration convincing

The assignment-facing outputs still require a developed 200-episode arc, fifteen sequential accepted 400-700-word episodes, two visible human interventions and successful continuation after episode 12. The existing fixture is not that demonstration.

Demonstrate more than length:
- An episode change produces a reviewed memory change and affects later context.
- A future direction intervention changes later work without rewriting established history.
- The saved state resumes after episode 12.
- A claimed fact can be traced to its source, and a character's lie is not promoted into world truth.
- Receipts show actual spending, uncertain calls, rejected drafts and human/model authorship.

Evaluate separately:
- **Code correctness:** transactions, idempotence, stale basis, checkpoints, safe rendering and budget enforcement.
- **Memory quality:** missing/incorrect changes against hand-labeled expectations; attribution and secret handling.
- **Writing quality:** human assessment of continuity, causal logic, distinct voices, momentum and hook using a versioned rubric.
- **Usability:** review time, successful source retrieval and unaided continuation.

A model critic score is advisory. A passed test suite is not evidence that the prose is compelling or that all important memory was extracted.

## 9. Budget, dependencies and release gates

USD 1 is the whole real story-generation ceiling, not a per-episode allowance. Every real planning, draft, critic, rewrite, extraction, test and retry call counts. Current accounting is shared within one database; it cannot govern real calls across new databases. A project-wide stable ledger is a prerequisite to any real adapter, not a reason to block a fake/manual author test.

Real generation remains gated on explicit provider/access/model/pricing approval, tokenizer/output bounds, reservation behavior and a bounded preflight. No evidence yet establishes that fifteen episodes plus the desired workflow fit USD 1. Default to no paid alternatives or critic. If measured feasibility fails, disclose it and revisit permitted scope/budget; do not disguise assistant allowance as story-provider spending.

Keep SQLite as the authority and the graph as its view. Planner/writer/reviewer/curator are roles, not necessarily separate autonomous agents. No framework or graph-database switch just to draw boxes.

Keep standard-library code where adequate. Any dependency addition requires provenance, license, maintenance and security review plus reproducible pinning; being well known is not a guarantee. Story imports/model output are data, not permission to run tools or write canon. Real model requests contain necessary story material only.

An editable server needs separate loopback/origin/CSRF/path and persistence review. Current offline CSP/rendering checks do not clear that surface. Independent product-idea review is not independent code-security clearance. The separate initial offline code review found no security concern and one medium filtered-graph defect. Parent correction was followed by a separately authorized targeted independent re-review, which passed with 32 tests, 17-file in-memory compilation and 149 probe assertions across 31 child processes. This closes that correction, not the broader roadmap: no provider, hosted-release or vulnerability-certification claim is made.

## 10. Stop lines and the final recommendation

Avoid for now: multi-user accounts, billing, hosting, audio, parallel full episodes, general belief/temporal reasoning, selective automatic retcons, autonomous conversational editing, adaptive preference training, model debates and a new workflow framework.

Do not throw away the graph or postpone design indefinitely. Let real author tasks guide a focused episode-and-delta interface; give the graph a clear evidence job. The best version is the smallest one that makes the next episode feel under the author's control, then earns more automation through evidence.

**Recommendation:** approve the two-cycle author loop as the next slice, choose an actual premise with Ayan, and validate it before building the full roadmap. No application code, provider configuration, shared memory, commits or publication were changed by this product-direction work.
