# Droid task routing for the authoring project

Decision: use native GPT-6.1 Sol (`gpt-6.1-sol`) as the default engineering/review model for this project, medium reasoning by default and high only for a concrete difficult correctness problem. This is an invocation policy, not a global model/settings change or a paid fallback. Ayan explicitly recommended Sol6.1 if available and asked for task-appropriate price/intelligence selection.

Evidence: an actual bounded response succeeded, and the new owned session settings echoed `gpt-6.1-sol`, medium reasoning. Receipt: C:/Users/ayan1/AppData/Local/hermes/data/droid-bridge/story-authoring/sol61-check-06799b3ca923/manifest.json. Packet review is an access check and engineering advice, not a benchmark or code/security clearance.

Official current Factory allowance multipliers: Sol6.1 0.8x, Sonnet5.5 0.8x, Grok4.7 0.8x, Qwen3.8Max 0.8x, GLM5.3 0.56x, GLM5.3Flash 0.06x, Gemini3.8Flash 0.3x, Opus5.5 1.6x. These are quota multipliers, NOT USD prices or Merge generation rates. Re-fetch before future routing decisions; actual usage also depends on input/output/reasoning/cache/rework.

Roles:
- Sol6.1: authoritative implementation decisions, state/transaction/concurrency design and independent source review.
- GLM5.3Flash: bounded implementation/helper tasks, test scaffolding and cheap checks, with strong-model/parent verification before acceptance. Existing already-running authoring worker keeps ownership until completion; no mid-write model replacement.
- Sonnet5.5: candidate for interaction/UX work at the same published multiplier, but its account inference access has not yet been tested.
- GLM5.3: candidate for medium complexity at a lower multiplier; access/quality are not yet measured.
- Qwen3.8Max/Grok4.7: alternatives, not a price-based preference over Sol because the published multiplier is the same; account access/quality remain untested.
- Gemini3.8Flash: candidate for fast supporting design/data work; not inference-tested yet. Earlier Gemini3.1Pro execution failed, not diagnosed or relabeled as access success.
- Space Bunny Alpha: authorized only for bounded low-risk suggestions after fresh Merge access/pricing checks; no authority over accepted story, spending or credentials.

Catalog discovery: CLI help omitted seven native IDs. Complete current validator list contains 58 native entries (including Auto and three deprecated entries) plus 12 configured custom BYOK entries. Official documentation also retains two deprecated entries not present in the validator; keep them separate. Complete-Droid-Models.md and complete-model-catalog.json under the project task journal retain the reconciliation. Catalog recognition is distinct from actual inference access.

Keep native Droid development usage separate from the USD1 Merge story allowance. No global billing/Core/Extra Usage changes, no custom paid routing, and no automatic retries/fallbacks on quota/auth failure. Only one implementation worker currently owns the project; parent independently tests and performs local browser verification.
