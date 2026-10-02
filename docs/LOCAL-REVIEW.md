# Local story review

This is a working read-only browser view, not the finished writing product. The initial selection is the existing offline harbor workflow fixture, not a real generated serial or developed 200-episode narrative.

## Open it

On this workstation, open `http://127.0.0.1:8765` while the local review process is running. It is also opened in the Hermes desktop preview as **Story review · local live view**.

Sections:
- **Read episodes:** exact accepted final prose and pending/rejected revisions, word counts and adjacent source-linked interpretations.
- **Review storyboard:** browse all 200 placeholder intentions in episode ranges; distinguish intentions from accepted prose and active author directions.
- **Inspect memory:** current, proposed, rejected and superseded interpretations, exact evidence, source navigation and the existing graph rendered from a read-only database connection. The embedded graph remains a snapshot; this page rebuilds it on opening or refresh.
- **Review quality:** the actual 400–700 whitespace word-count check and unsaved author-review questions. No narrative-quality score or automated critic has run.
- **Read receipts:** recorded human decisions, calls, selected material and per-database accounting limitations.
- **Review writing model:** sanitized read-only Merge discovery metadata. No browser credentials or generation action.

The page checks the selected database every three seconds while visible. Unchanged content preserves author selection. A changed database refreshes the selected section. This is live database observation, **not live model-output streaming**. Accepting, rejecting, editing or confirming memory remains in the existing CLI workflow.

## Restart

From PowerShell:

```powershell
Set-Location 'C:\Users\ayan1\Downloads\serial-story-studio'
.\.venv\Scripts\python.exe -m serial_story.review_web --db local/memory-preview-76cf1f82e6fc/fixture.db --fixture --port 8765 --provider-receipt local/merge-review-metadata.json
```

From Git Bash:

```bash
cd 'C:/Users/ayan1/Downloads/serial-story-studio'
.venv/Scripts/python.exe -m serial_story.review_web --db local/memory-preview-76cf1f82e6fc/fixture.db --fixture --port 8765 --provider-receipt local/merge-review-metadata.json
```

Use another free port if 8765 is occupied. Press Ctrl+C in the owning terminal to stop it. The current agent-managed process is a local development server, not an installed service or a guaranteed persistent deployment.

For a different **known, trusted project database**, explicitly change `--db`; omit `--fixture` only when its material is not a fixture. Missing databases are not created by the viewer. Do not use it to open arbitrary untrusted database files. No browser-supplied paths or file uploads are accepted.

## Merge discovery and its limits

The user authorized the existing connection for read-only model/pricing/cache discovery only, explicitly excluding inference, credential-file searches and spending. Discovery used the already exported `MERGE_GATEWAY_API_KEY` privately and made only GET requests to `/v1/models`. No credential files were read, no key changed and no story material sent.

The model-list response returned Opus 5.5, with `has_more=false`; a larger-limit list returned the same one record. A separate exact-model GET returned **`anthropic/claude-sonnet-5-5`**, displayed as **Claude Sonnet 5.5**, advertised available with text output and streaming. This is not proof of a complete global model catalog or a successful inference call with this key.

The Anthropic vendor's discovered USD-per-million-token rates:

| Rate | USD |
| --- | ---: |
| Input | 2.00 |
| Output | 10.00 |
| Cache read | 0.20 |
| Cache write | 2.50 |

These are catalog metadata, **not observed charges or verified cache hits**. The same catalog advertises reasoning enabled by default with disabling unsupported; a tiny output allowance cannot be assumed to bypass reasoning or guarantee useful prose. Its Anthropic route does not advertise zero-data-retention. Any real-call approval should resolve routing, necessary story content, privacy and billing bounds explicitly.

Raw discovery receipts remain ignored/local: `local/merge-catalog-readonly.json`, `local/merge-model-check-readonly.json`. Browser metadata is allowlisted in `local/merge-review-metadata.json`; the server additionally drops non-public fields and hard-codes generation off.

Merge's public prompt-caching documentation describes route-specific caching, explicit `cache_control` markers for Anthropic/Bedrock and silently dropped markers on unsupported routes. Its source was retrieved through primary-domain search; direct Markdown fetch returned HTTP 403. Source: https://docs.merge.dev/merge-gateway/capabilities/prompt-caching

Before claiming proper caching, the future adapter must pin a supported model/vendor route, put stable story instructions/material before variable episode requests, apply that route's documented controls, and observe actual cache-write/read usage and cost over bounded requests. **None of this inference testing was authorized or performed here.**

## Safety and remaining gates

- Python standard library only; no installed packages, global changes or external frontend scripts/fonts.
- Listener fixed to `127.0.0.1`, never `0.0.0.0`. Exact host/origin checks; cross-site requests refused; no CORS access.
- Fixed asset/read routes. No directory listing, generic file route, write route, generation route, secrets endpoint or publication.
- Read-only SQLite URI, query-only mode, disabled trusted schema and consistent read transaction. No schema initialization/migration in the viewer.
- Story labels are inserted as text, not HTML. Local CSP blocks off-origin connections; graph retains its hashed-script/no-network policy.
- Full prose is still unencrypted in the local database and visible to trusted local processes. This is not remote authentication or a hosted security release.
- USD 1 remains the **entire story-generation project ceiling**. Existing accounting is per database; a new database must not reset a real spending allowance. Shared project accounting and an approved provider-side bound are unresolved real-call release gates.
- Real provider adapter, streaming generation, measured cache reuse, saved web review decisions, developed arc, real demo episodes and public deployment remain unimplemented.
- The earlier independent review covered the offline memory/graph slice, **not this new server/UI**. No additional model reviewer was launched.
