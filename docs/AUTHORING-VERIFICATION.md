# Authoring pilot verification

## Result and scope

The working local authoring pilot is available on the Windows PC at `http://127.0.0.1:8766`. It uses a NEW clean database, `local/authoring-workspace/story.db`; no synthetic QA story was copied into it. Explicit writable startup and metadata-only Merge catalog access are enabled. Default writing source is the labeled deterministic synthetic writer. Paid Merge generation is OFF, with no paid enablement flag in this slice.

Independent native Sol 6.1 source review returned **LOCAL_PILOT_CLEAR** for the frozen loopback-only, single-author pilot. This is a static source review, not a hosted production certification or an independent runtime test. The parent separately executed the real tests and browser checks below. Production remains **HOLD** for the shared USD1 ledger/reservation/settlement, exact model/vendor pricing and token preflight, authorized live writing evaluation and deployment evaluation.

## Executed evidence

- Final independent offline suite: `uv run --offline --locked python -m unittest discover -s tests -q`: **97 tests in 80.965 seconds, OK, exit 0**. Node syntax and successful-response race/selection DOM tests passed.
- Actual isolated installed Edge author journey passed: setup, future-plan save/approval, saved writer instructions, explicitly synthetic generation, scoped saved feedback consumed by revision, typing during a successful save retained and saved again with acknowledged CAS, acceptance blocked by unsaved feedback, edited final prose accepted, unrelated memory input retained, reload, exact accepted-source memory proposal and separate confirmation, current-CAS rejection, live Merge model/vendor/price selection with generation OFF.
- Edge at 1440/768/390 widths: no horizontal overflow, bundled font loaded. Mobile setup action is now visible in the first viewport. No application JavaScript exceptions recorded in the full journey; reduced-motion emulation checked. This is bounded functional/layout QA, not full accessibility certification.
- Final Edge delta checks passed: instruction reset retains other unsaved settings and only applies through explicit Save settings; live catalog reload retains an unsaved vendor; saved model/vendor restoration and disappearing choices retain exact values. The latter two-model/removal cases used explicitly SYNTHETIC injected catalog fixtures, not fabricated live Merge access.
- Existing protected review fixture SHA256 remained `0d4c6b1b15eaca79b909fc7f0e48b38792374e185c3beb86786d45b16bf2718a`.
- Current source/test files exactly match the final independent-review source manifest. Server state readback confirmed clean workspace, writable true, default source fake, generation_enabled false. QA port 8767 was stopped.

## Review and QA handles

- Final independent verdict: `C:/Users/ayan1/AppData/Local/hermes/data/droid-bridge/story-authoring/independent-review-42ae511d8f/result.md`.
- Exact reviewed source hashes: same directory, `source-manifest.json`. Owned session: `c1d62391-e4c9-420b-8fb1-d9e95e526fe8`, verified `gpt-6.1-sol`, medium reasoning. Source snapshot unchanged.
- Full Edge journey receipt/screenshots: `C:/Users/ayan1/AppData/Local/hermes/cache/scratch/authoring-browser-qa-6421579ae9/results.json` and adjacent PNGs.
- Final settings/catalog Edge receipt: `C:/Users/ayan1/AppData/Local/hermes/cache/scratch/authoring-delta-0f896291df/results.json`.
- Main correction evidence: `docs/AUTHORING-AUDIT-FIXES.md` and `local/test-runs/audit-fixes-20261002-02`.

## Corrections since the first review

Acceptance no longer discards unrelated dirty forms. Successful saves acknowledge only submitted edits and preserve typing made while the response is pending. Rejection and plan feedback use explicit caller-loaded CAS/source identifiers. Ambiguous catalog JSON keys are rejected. Windows refused POST responses flush before a tightly bounded cleanup drain, without weakening authorization checks. Prompt reset is a local dirty edit with explicit save guidance. Model/vendor choices are restored coherently, and missing selections remain labeled unavailable rather than silently erased. Browser-like select membership in the DOM tests caught the previous weak-mock gap.

## Run and operating boundary

From the project directory:

```bash
.venv/Scripts/python.exe -m serial_story.studio_web --db local/authoring-workspace/story.db --enable-writes --enable-merge-catalog --port 8766
```

The already configured Merge environment key is resolved privately by the application for authorized catalog GETs. No credential files, management-key recovery, purchases, global model switches, paid writing or fallback were used. Native Droid coding/review consumed subscription allowance; that is separate from application Merge spending. Catalog access does not prove writing quality or paid inference readiness.

At handoff there are no coding/review workers pending. Only the new local studio server and the pre-existing read-only review server remain running. QA servers and isolated browser processes were stopped. This is not public hosting or an unattended writer. Shared memory was not edited.
