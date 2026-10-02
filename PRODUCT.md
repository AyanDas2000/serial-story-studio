# Serial Story Studio

## 0. Status and authority
Local, fake-provider-only learning scaffold. The next approved slice adds a human-confirmed, source-linked memory ledger, durable directions, registry, queries and a read-only local graph. The broader writer/reviewer workflow is a design proposal, not permission to build every stage. Merge is the intended future gateway and USD 1 is the total project spending ceiling; access, exact model, current pricing and a real-call preflight remain unapproved/unverified. No credential search or paid calls in this slice. A later personal-website demo is a goal, not permission for website edits, publication, submission or deployment. The product skill is adapted to this non-commercial learning outcome.

## 1. User
A writer/editor who wants to direct a long serial without losing accepted history or decisions. First user: the builder learning and reviewing this local workflow. No payer or commercial demand is asserted.

## 2. Outcome and metric
Reliable human-directed serial generation: propose a plan, approve it, review a draft, accept final prose, exit, and recover the same approved state from disk.
Metric for this milestone: one complete offline cycle survives fresh processes, with exactly one acceptance event and no repeated advancement.

## 3. Alternatives and positioning
A document plus chat can write prose but leaves approval, memory, and recovery to manual bookkeeping. An all-history prompt has no explicit canonical ledger. This tool separates proposed intentions from accepted history and makes that boundary inspectable.
ASSUMPTION: a single-user local CLI is the right first surface; discuss before further implementation.

## 4. First interaction
Inspect a plan proposal before any drafting. Primary action: approve the plan. During episode review: accept final text or reject the draft. Signature interaction, not a visual design claim: accepted-history receipt showing the episode, final revision, and next eligible episode.
No graphical UI, visual tokens, motion, or premium-screen claim in this milestone. Future UI requires the separate design workflow.

## 5. Not built now
Real model adapters; semantic canon extraction; historical rewriting; graphical web UI; multi-user accounts; audio; billing; deployment; submission automation.

## 6. Cost and access
Fake mode is the only executable provider. It ignores environment credentials. Model cost is zero, not an estimate for real providers. Development uses an isolated environment and standard-library unittest, with no third-party runtime or dev dependencies. A future adapter needs explicit provider, access, and budget approval.

## 7. Milestone acceptance checklist
- [x] Plan approval gates drafting.
- [x] Pending review and accepted prose survive actual process restart.
- [x] Rejection stays outside accepted history.
- [x] Human-edited final text supplies the stored memory source.
- [x] Repeated acceptance does not duplicate memory, event, or cursor movement.
- [x] Durable accounting seam and bounded fake calls are exercised.
- [x] Narrow tests, CLI walkthrough, and local design proposal are available.
These are scaffold criteria, not a claim that the full serial-writing product is ready.

## 8. Launch
Not authorized. No remote repository, deployment, portfolio modification, or upload.

## 9. Decisions
2026-10-01: Start with an inspectable plain-Python/SQLite fake path. Recommend CLI-first, but leave the framework and historical-edit depth open for discussion. Preserve business logic outside the CLI. Do not translate commercial skill defaults into unrequested features.
