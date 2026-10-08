# Live evaluation with the supplied Merge Gateway key

The evaluation key is shared separately with the handoff email. No real key is included in this repository. You do not need to create or fund your own Merge account to use the supplied key.

1. Install Python 3.14, then download or clone this repository.
2. Open the repository's `source` folder. Copy `.env.example` to a new file named `.env` in that same folder, beside `run_shelf_live.py`. Make sure Windows has not named it `.env.txt`.
3. Replace the placeholder value with the supplied key, on one line:

```text
MERGE_GATEWAY_API_KEY=PASTE_THE_SUPPLIED_KEY_HERE
```

4. Save the file. On Windows, double-click `live-it.bat`. Alternatively, open a terminal in `source` and run:

```text
python run_shelf_live.py --sample --default-cap 1 --open
```

5. Open http://127.0.0.1:8770/ if the browser does not open automatically. Choose New series, select the live writer and set a per-series spending limit. The command above starts with a $1 default. Practice mode remains available for free.
6. Adopt a direction and episode plan, then draft an episode. Edit or request a rewrite, save, and approve when ready. Preview and explicitly confirm extracted facts to populate Memory.
7. For a 400–700-word episode, open Studio → Length and set Shortest = 400, Aim = 550 and Longest = 700. These settings influence future requests and warnings; they do not shorten existing prose or guarantee every model response falls in range.
8. Stop the server with Ctrl+C. Stories and accounting remain saved locally. Do not upload `.env` or paste the key into story text or chat.

The supplied key is intended to have a $5 provider-side spending limit for the review period. This is shared across its calls, while the app's local limit is per series. The key settings and review period will be supplied with the email. Merge's standard limits reset periodically, spending is recorded after each request, and the request crossing a threshold can exceed it. Revoke the evaluation key before its reset to keep the trial one-time. No exact $5 maximum is guaranteed by the app.

Provider reference: https://docs.merge.dev/merge-gateway/cost/budgets
