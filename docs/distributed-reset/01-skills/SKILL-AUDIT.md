# Skills/design foundations audit

2026-10-02. First-pass source review only, awaiting Ayan. No app edits, execution, provider calls, installation, screenshots, recordings or tests performed.

## Finding

The supplied skills contain useful safeguards, but loading them is not evidence they governed prior implementation. The source supports a workflow-enforcement gap, not a proven reconstruction of earlier agents' behavior. Ayan's report that the UI is worse than basic Notion is the user-quality verdict; I have not independently judged rendered pixels.

The gap is upstream of ornament: the token contract targets an evidence inspector, while the actual studio needs a complete writing/approval loop. Generic anti-slop scans and self-scored gates cannot select that loop or prove writing quality. More animation or a new palette would not repair authority and flow.

## Exact source evidence

Paths below are relative to the isolated `project` root unless prefixed `portfolio-source`. Line numbers refer to the snapshot read in this pass.

| Evidence | Observation and consequence |
| --- | --- |
| `docs/PRODUCT-DIRECTION.md:38–66,94–127` | Proposal correctly separates Write/Storyboard/Memory/Receipts and acceptance from memory confirmation. This is intended behavior, not proof of implementation. |
| `docs/PRODUCT-DIRECTION.md:139–159,163–184` and `PRODUCT.md:3–4,19–25` | Historical fake/manual milestone and 200/15-episode assignment do not supersede today's actual-model, 30–40 episode thriller, backend-first priorities. Keep USD 1 and access gates. Do not edit these historical docs in this lane. |
| `.stitch/DESIGN.md:3–11,31–36` | Tokens/signature were selected for an offline inspector and read-only live review. “Inspect a source” / “Refresh review” are not authoring primary actions. Tokens do not settle the writing surface choice. |
| `serial_story/assets/studio.html:24–50,61–72,79–123` | Manuscript, draft actions, plan, settings, paid preflight, feedback and property/value memory forms coexist. Memory review is a collapsed details element; plan and settings each have their own primary style. Task-driven hierarchy is not enforced by markup alone. Actual prominence/overload needs pixels. |
| `serial_story/assets/studio.js:50–64,69–97` | Save/accept emphasis is partly state-aware, a useful existing seam. But acceptance is not disabled for pending memory; header instructs plan approval/paste/synthetic generation when no candidate exists. Receipts say memory has not been reviewed while normal draft actions remain structurally available. |
| `serial_story/studio/store.py:376–401` | Acceptance stores final hash, edit lineage and `memory_review: not-reviewed`, with a next-episode receipt. It does not complete or gate a separate memory-review checkpoint in this method. |
| `serial_story/service.py:44–72` | Context checks approved plan, story and memory revisions, but this inspected function has no accepted-memory-pending continuation check. Evidence indicates a gap; no runtime bypass test performed. |
| `serial_story/studio/server.py:55–59` and `serial_story/assets/studio.html:64` | Earlier plan intentions are called “established” based on episode position. The UI's “Established intentions” phrasing risks conflating plans with events; proposals should instead remain prior approved intentions. |
| `serial_story/assets/studio.html:116–122`; `serial_story/assets/studio.js:95–103` | Memory UI collects generic property/value and exact passage, then confirms/rejects facts. This inspected surface has no typed report/belief/knowledge choice or episode-level no-change/completion control. Source links alone cannot classify a thriller's lie or rumor. |
| `serial_story/studio/store.py:283–308,343–357` | Synthetic generation prepends a clear label and appends notes; this is workflow material, not semantic revision evidence. Pasted/manual prose also has `synthetic: false`, so non-synthetic is not equivalent to model-generated. |
| `serial_story/studio/authoring.py:27–42,95–109,146–164,166–218,235–246`; `serial_story/studio/merge.py:283–319,321–370` | Guarded model runtime and consent/reservation/persistence code exist, unlike a blanket “no real adapter” doc claim. Enablement and independent billing qualification block the path by default; live compatibility, pricing, actual dispatch and output are unverified. No provider or credential was accessed by this review. |
| `serial_story/assets/studio.js:88–92,107–114` | Frozen request/provenance and cost recovery details are available, often as raw JSON. Inspector detail is useful, but routine origin/checkpoint should not require reading JSON. |
| `serial_story/assets/studio.css:38–47,71–81` | Press/background transitions and reduced-motion suppression exist. It would be false to call this source zero-motion. This file does not choreograph the writer-loop transitions. Timing and feel remain unverified. |
| `serial_story/assets/studio.css:8–9,32,47,49` versus `serial_story/assets/review.css:10–57` | Studio imports review CSS but references `--color-bg-raised`, `--color-fg-muted` and `--color-success`, absent from the inspected review root. These are a static token-integration risk, not a measured contrast failure. The separate graph `tokens.css:2` defines them, but studio HTML links studio CSS, which imports review CSS. |
| `serial_story/assets/review.css:157–162,191–195`; `serial_story/assets/review.html:24–29,64` | Existing review honestly labels read-only scope and has a delayed opacity loading shape/reduced-motion rule. Good seams to retain. Static Evidence Spine text alone is not proof of an effective interactive evidence path. |

## Supplied skill contents read

All eight requested files were read in full from the supplied `skill-context`: `DESIGN.md`, `workflow.md`, `taste.md`, `motion.md`, `design-system.md`, `platform-web.md`, `animate.md`, `review-animations.md`.

- **DESIGN / taste:** good contrast, focus, states, source privacy, hierarchy and token discipline. Gaps: signature/font/palette prohibitions can be satisfied without task coherence; screenshot scores overclaim when movement is included.
- **Workflow:** good source review and fresh-verification intent. Gaps: numeric role ratings and premium thresholds can become self-certification; personal review/authority is not a substitute score. The new evidence packet separates backend, pixels, movement, writing and Ayan approval.
- **Design-system:** starts with extraction/tokens and supply. Missing surface selection and writer-loop storyboard must precede it.
- **Platform-web:** installation defaults are optional accelerators, not a mandate to replace adequate native controls or this plain browser/Python stack.
- **Motion versus animate/review-animations:** mandatory list/route animation conflicts with purpose/frequency gating; 400ms route timing and curve prescriptions conflict with sub-300ms guidance. Review also flags pure fades while reduced motion needs non-spatial treatment. The local reference makes these proposed exceptions explicit and reuses existing tokens.

These are source-level weaknesses in enforcement and sequencing. There is no session history here proving which skill was ignored, when, or by whom.

## Portfolio comparison, only the authorized components

Read `portfolio-source/src/index.css`, `Hero.tsx`, `Ambient.tsx` and `Craft.tsx` in this isolated lane. No portfolio changes.

- `Hero.tsx:71–107`: headline/subhead/supporting achievements have differentiated structure. Borrow intentional hierarchy, not marketing layout.
- `Hero.tsx:59–68,110–114`: main entrance consults reduced motion, but `ScrollCue` at `7–24,119` repeats movement without its own reduced-motion handling. CSS transition suppression does not by itself prove this JS loop stops.
- `Ambient.tsx:12–37`: broad color washes and cursor-position radial glow exist; no reduced-motion handling in this component. Parent handling was not inspected. Do not import the effect into a concentration tool.
- `Craft.tsx:14–19`: 0.85s horizontal entrance, 0.2s stagger and `once: false` replay are defined without a reduced-motion hook in this component. This is not suitable writer-loop motion evidence.
- `index.css:107–132`: infinite CSS rotations have explicit reduced-motion cancellation, a positive static seam. It does not prove the separate Motion component animations comply.

No claim that the portfolio is premium, that its animations feel good, or that copying them would improve the studio. No font-rendering or performance verification.

## Deliverable and honest limits

New project-local skill and three references specify enforcement of surface choice, complete loop/authority, provenance, purposeful motion and evidence gates. They do not fix product behavior merely by existing. Later workers must read and apply them. After read-back, the harness explicitly reported `story-studio-design` discovered and available; invocation and later-worker compliance were not tested.

Validation performed: read source and supplied skills; checked claims against the cited lines; created only new files in the two authorized paths and read them back. No execution was permitted. No app/tests/credentials/databases/environment/browser profiles/global skills/shared memory/original project were changed or accessed as runtime data. No screenshot/video files matched the targeted snapshot search, and none were created. No numeric design score assigned.

No upstream installation is necessary for this pass. Optional component behavior, Impeccable and Stitch extraction are ranked in the evidence reference; upstream contents/availability remain unverified. Already-supplied animation skills are not missing.

## Exact next decision

**Ayan: approve or amend these five workflow requirements and the separation of prose acceptance from memory completion, then authorize a bounded backend plan for actual model-backed writing and the 30–40 episode thriller evaluation.** Decide the later authoring surface after backend prerequisites and writer-loop requirements are clear, before changing tokens. Provider/access/model/pricing and any live-call permission remain separate decisions. This is first-pass review, not approval to implement or spend.

Native session identity must come from the returned Droid/harness session metadata. No session ID was exposed to these file tools; this audit does not invent one. Parent must verify the actual successful returned session ID independently.
