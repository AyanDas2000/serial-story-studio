# Memory graph design tokens

name: Serial Story Studio, source-linked memory explorer
platform: offline browser explanation prototype
status: local review artifact, not a deployed or shippable web app

## Atmosphere and reference
A story editor's evidence desk: printed manuscript margins, a library index and ink connecting annotations. White paper, graphite text and a deep blue editorial mark. No gradients, glows, card grids or ornamental icons.

## Signature and primary action
Signature: Evidence Spine, visible links from a character through a fact and situation to accepted prose. Primary action: Inspect a source. Entity filters and history toggle are secondary. Density: compact data tool.

## Typography
Bundled IBM Plex Sans, variable font, body and display; the deliberate sober editorial/technical voice lets character names and evidence passages share the same readable family. Numerals are tabular. The font is distributed through Google's official fonts repository under SIL OFL 1.1. Asset source URLs, byte counts and SHA-256 hashes are in serial_story/assets/provenance.json. No runtime font fetch. Body 16/14, display 40, labels 14. Each string wraps. Unselected graph nodes retain fully readable text; selection uses border emphasis, not faded text.

## Palette roles
Canvas white (#ffffff), surface cool paper (#f5f7f9), raised white; foreground graphite (#17232e), secondary/muted steel (#526170); editorial accent deep blue (#144b78); border subtle (#d5dde3), strong (#758693). Planned intentions use dashed borders and explicit words, not color alone. Contrast must be checked against actual rendered colors.

## Layout tokens
Spacing 4,8,12,16,20,24,32,40,48,64; radii 4/8/12; one border strategy, no shadows. One container level. Explorer combines a canvas and an adjacent evidence panel, not nested cards. Desktop and narrow-screen layouts are explicit; diagram canvas may scroll rather than squeeze labels.

## Motion tokens
instant 80ms, fast 160ms, base 240ms, slow 400ms; standard cubic-bezier(0.2,0,0,1), exit cubic-bezier(0.3,0,1,1). Use focus/selection state transitions, no autoplay. prefers-reduced-motion removes translation and collapses durations.

## States
Empty explains how accepted evidence will appear and gives Inspect a source as an unavailable action with a next-step hint. Loaded shows saved revision and graph. No search matches provides Clear filters. Failed load says the graph could not be read and to recreate the export; source action is disabled. Loading is brief local initialization, no network. Success updates selected node and evidence panel. It is a saved snapshot: changes in the database require a fresh export.

## Bounds and security
Handwritten SVG/DOM rendering only. Untrusted labels go to textContent, never HTML. The embedded JSON escapes script-delimiter characters. No CDN, remote code, account or server. Full story prose may be present in this local export; do not publish it automatically. Filtering and keyboard access are required. A future production graph needs a viewport/virtualization for large stories.

## Local live review extension
Primary surface: Inspect, with Monitor as a secondary behavior. Signature: the Evidence Spine above the reader and the adjacent exact-passage interpretations. Primary action: Refresh review. Six secondary sections show episode prose, storyboard intentions, memory evidence, quality-review prompts, receipts and read-only model discovery. No edit, approval or generation action is provided.

The reader uses the same palette, font, motion and spacing tokens. Named review dimensions are index 200px, evidence 300px, prose measure 76ch, maximum surface width 1680px, graph height 760px and minimum touch target 44px. One local font route; no CDN. Light appearance only, explicitly supported. Database observations refresh every three seconds while visible, preserving unchanged content and author selection. This is live database inspection, not model-output streaming.

The initial view is explicitly labeled offline workflow-test material. Quality shows the real whitespace word-count check plus unsaved human-review questions, never invented scores. Model rates are read-only discovery metadata, not a connected generation provider or verified reuse savings. Empty, initial loading, read failure and refreshed states have specific copy; reduced motion suppresses reveal animations. Binding is local loopback only with fixed asset routes, origin/host checks and read-only SQLite connections. Full accepted prose remains private to this local review. No hosted release or public deployment is claimed.

