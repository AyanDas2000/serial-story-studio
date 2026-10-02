# Authorized offline milestone

Outcome: one human-controlled fake writing cycle survives disk reopen without duplicate acceptance.
Surfaces: development CLI commands only, no graphical UI or release surface. Primary actions are propose plan, approve plan, draft, accept/reject, and read. No visual tokens or Premium Test claim; apply the full graphical-design workflow before any UI phase.

Files: PRODUCT.md, DESIGN-PROPOSAL.md, this plan, README.md, VERIFICATION.md, pyproject.toml, uv.lock, .python-version, .gitignore, config.example.toml; serial_story/{__init__,__main__,records,repository,provider,budget,service,cli}.py; tests/test_workflow.py and tests/fixtures/edited.txt.

Sequence: outcome brief before code; isolated environment and Git init without commits/remotes; vertical test-first service tracer; CLI tracer; edit/reject/idempotency tests; durable budget/recovery tests; fresh verification and read-only independent review.
States: no story (actionable initialize error), proposed plan (approval needed), pending review (resume same draft), rejected (explicit new attempt), accepted (read/next episode), exhausted/uncertain budget (stop), invalid text/ID (refuse without state changes).
Data: one story per DB, typed immutable records, parameterized SQLite repository, provider protocol and fake-only implementation, durable call-accounting protocol, thin CLI.
Risk: local storage atomicity and premature canonical history. Mitigate with short explicit transactions, immutable draft versions, acceptance IDs, restart tests and no provider calls inside write transactions. No external side effects.

## CEO review
Metric: yes, restart-safe human acceptance is directly exercised. User: yes, can inspect the receipt and stored text. Verdict: keep; defer monetization and website work.

## EM plan review
Scope 9/10, reversibility 8/10 (new isolated folder, no existing work), tests 9/10, blast radius 9/10. Storage warrants security review. No commits because the user forbids them in this phase. Build authorized for the bounded scaffold; future architecture still requires discussion.

## Designer plan review
Visual dimensions, screenshots, font/token work and motion are not applicable to this no-GUI development milestone. Do not score an unseen UI. Command flow and error/success states will be exercised as text. This is not a product release or a substitute for later screenshot inspection.

## Security plan
No secrets discovery, dotenv loading, SDK, HTTP, external subprocess from user input, public surface, remote or uploads. Private generated DB and story exports are ignored. Local data is not encrypted; this is a single-user local development boundary, not secure hosted storage.

## Out of scope
Real episodes, semantic canon extraction, directions, retroactive repair, graphical interface, deployment, publication, provider spending and submission.
