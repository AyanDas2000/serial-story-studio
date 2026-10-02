# Authoring upgrade: authorized working slice

Authority: Ayan requested actual browser approval, planning/storyline editing, model selection, prompt tuning and feedback-driven revision; authorized starting Merge connection, and asked to continue using native Droid models, including GLM-5.3-Flash or Gemini. This supersedes the earlier read-only-only scope for a NEW local studio boundary, not the existing review server. No deployment, publication, unlimited inference, credential-file reads, global settings or shared-memory writes.

## Author journey and proof

Operate mode: one author writes a serial. Default workspace shows the next useful action, not a graph or developer catalog. Start with a blank story and explicit setup. Plan future beats, save and approve a specific plan revision; then draft or paste prose. Edit the pending prose with save/unsaved feedback. Attach revision-local feedback and revise. Explicitly accept final prose or reject a candidate. Show saved receipt, current episode, next episode and memory review separately. Accepted history cannot be overwritten by an editor. Memory confirmation and prose approval remain distinct.

Supporting controls: an actually persisted model/provider selector (explicit Fake versus Merge), a versioned editable writer prompt with reset, output limit, language/tone instructions and feedback scope. Explain what will be sent before real generation. Model, prompt and feedback configuration must be included in generation receipts. Future plan edits are versioned, use compare-and-swap and cannot silently invalidate a pending candidate or change established history. Keep sequential 1..200 episode constraints, but no placeholder arc disguised as real planning.

## Minimal local delivery

- Separate studio entrypoint and write HTTP boundary on loopback, port 8766, explicit writable startup switch. Preserve original review server, routes, tests and fixture database unchanged.
- Reuse canonical repository acceptance, rejection, memory sources and memory ledger. Add narrowly needed planning/feedback/settings/draft-edit version records; no duplicate canonical prose database or graph store. Database creation/migrations only under an explicitly chosen new studio DB. Add schema/migration tests.
- Strict bounded JSON requests, fixed route/method/asset allowlists, same-origin/Host checks plus random server-session CSRF capability on every mutation. No request-selected filesystem path or arbitrary SQL; no CORS wildcard, external JS/font calls, HTML model rendering, command execution or log dumps.
- Thread-safe request connections and generation serialization/deduplication. Stale history/memory/plan/settings/draft revisions fail clearly. Validation/error recovery must preserve typed inputs and unsaved work. Server-rendered metadata must not include secrets.
- Real Merge adapter lives separately from fake zero-cost StoryService._operation. Hardcoded official HTTPS origin, environment-held existing key only, no credential files or redirects. Narrow injected transport for offline tests. Sanitized catalog GET is allowed only when explicit Merge-enabled startup is requested; real POST remains disabled without explicit enablement, exact chosen model/vendor, validated known pricing/output bounds and project-shared USD1 reservation ledger. No automatic retry or fallback on timeout/auth/quota. Provider usage/cost settlement and uncertain reservations cannot pretend to be zero or refundable. A local budget is not provider-side billing enforcement.
- Worker must implement offline adapter/contract tests; parent owns real catalog/network checks and any paid-call authorization. No worker network calls, provider calls or reading process keys.
- First implementation should expose working fake/manual journey and Merge connection/settings controls truthfully. If any risky real-call prerequisite is unresolved, block real generation with an actionable reason rather than use fake output while labeling it Merge.

## Design contract

Keep sober editorial palette, bundled IBM Plex Sans, one accent, existing evidence provenance. Replace the inspector composition for this NEW surface: compact context/navigation, dominant manuscript editor, a narrow planning/review panel, clear bottom or adjacent action row. Use standard controls, progressive settings, one primary action per state, meaningful empty/loading/error/saved states and visible keyboard focus. Keep 390/768/1440 widths usable. No decorative card grids, hero header, fake scores, unnamed users or disabled controls posing as features.

Read installed Claude skills directly: C:/Users/ayan1/.claude/skills/{taste,platform-web,design-system,emil-design-eng}/SKILL.md and taste/references/principles.md, plus C:/Users/ayan1/Downloads/ayan-skills/{DESIGN,WORKFLOW}.md. Applicable incumbent tokens: .stitch/DESIGN.md. Plain Python/native JavaScript, no framework or dependencies.

## Verification gates

Use strict vertical TDD (one behavioral RED then minimal GREEN, not a pile of imagined tests). Exercise save/reload, plan edit and approval CAS, pending edit preservation, scoped feedback/revision, exactly-once acceptance with edited final source, rejection, memory confirmation, stale requests and no provider call without consent. Offline fake/mock HTTP responses must be visibly test data, never claimed live generation. Run full existing suite without weakening assertions and syntax-check new JS. Parent must independently rerun and inspect actual browser interactions before claiming working UI. Independent security review remains a release gate, not satisfied by the GLM packet-only review.

No Git commits/reset/clean, package installs, restarting existing servers, editing shared skills/memory, touching existing local databases or browsing user accounts. Allowed edits: project source, tests and new scoped authoring docs; test data only in new local/test-runs or scratch directories. Preserve untracked work. Report exact touched files, RED/GREEN logs, remaining risks and runnable command. Development usage is native Droid and separate from Merge story budget.
