# Serial Story Studio, beta: start here

A writers' room for a long serial. You direct. A writer drafts. Nothing becomes part of your story until you press a button that says so. Everything runs on your own computer.

You can use it two ways:

| | Practice mode | Live writers |
|---|---|---|
| Writer | A scripted writer that produces plain filler | Real models (Claude Sonnet 5.5 drafts, Claude Opus 5.5 plans, GPT-6 Luna reads) |
| Key needed | No | Yes, a Merge Gateway key |
| Cost | Nothing | Real money, with a limit you set per series (about $0.04 to $0.07 per episode in our runs) |
| Good for | Learning the desk, judging the screens | Judging the writing |

Start with practice mode. It takes five minutes.

## What you need

- Python 3.14 (https://www.python.org/downloads/). No other packages.
- A modern browser.

## Practice mode

1. Unzip the folder anywhere.
2. **Windows:** double-click `try-it.bat`. **Mac or Linux:** run `sh try-it.sh` in a terminal opened in the folder.
3. Your browser opens at http://127.0.0.1:8766/. A short walkthrough opens the first time. Press Ctrl+C in the terminal window to stop.

Press **Start here** on the home page any time to see the walkthrough again. Inside any series, Studio, **How it works** shows the whole logic with diagrams.

## Live writers

If you received an evaluation key with the handoff email, skip account creation below and start at step 4. Full supplied-key instructions are in `../LIVE-EVALUATION.md`. This repository contains no credential.

1. Sign up at https://gateway.merge.dev/signup. Signup needs no card.
2. Add a card in your Merge account. Merge's Free plan only covers a short list of small models. This program uses Claude and GPT models that are on the paid Pro plan. We have not tested the Free plan with this program. Merge's published Pro plan adds a 5% fee on top of the model cost. Your invoice is the final word on what you owe.
3. Create a key at https://gateway.merge.dev/api-keys.
4. In the program folder, copy `.env.example` to a new file named `.env`. Open it and paste your key after `MERGE_GATEWAY_API_KEY=` on the same line. Do not add quotes or spaces. Never send this file to anyone.
5. **Windows:** double-click `live-it.bat`. **Mac or Linux:** run `sh live-it.sh`. Your browser opens at http://127.0.0.1:8770/.
6. Press **New series**, choose the live writer and set a spend limit. The default is $1. The most you can set is $5.

If you were given a key by the person who sent you this download, put it in `.env` exactly the same way.

### How your money is kept safe

- Every live series has its own limit and its own spend log. One series can never spend another series' money. Restarting does not reset what was spent.
- Before each call the desk checks there is room under the limit, and holds that amount while the call runs. A call with no clear answer is marked unconfirmed and is never retried by itself.
- The key stays in `.env`. It is not stored in any series folder, not shown on any page and not sent anywhere except to Merge.
- Secrets you add to a series have trigger words. If a trigger word would be in a request, the run stops before anything is sent. This finds words, not ideas, so keep the secret itself out of your plan.
- The desk's limit is a local safety. For a second layer, also set a spend limit inside your Merge account.

### What is sent to Merge

The writer receives your direction, your plan line, your voice notes and every earlier episode in full. It does not receive Memory facts, your private notes, secrets or chat messages. In the series, Studio, Support, **What the writer was shown** displays the exact request for any draft.

## What to try (about 20 minutes)

1. First minute: do you know what this is and what to click?
2. Open the sample series. Read an episode and open Memory.
3. Start your own series. Write a direction, adopt it, plan a few episodes, draft one.
4. Read the draft and edit a paragraph. Check the "New names in this draft" note under it.
5. Approve it, then look at Memory. Every fact is shown with the sentence it came from.
6. Open Studio, Length. Set your own shortest, aim and longest.
7. Press Ctrl+K and ask for something in your own words.
8. Resize the window to a phone width. Try dark mode.

## What to send back

- A screenshot of anything that looks wrong, with the window width if you can.
- Anything that confused you, in your own words.
- Anything you expected to find and could not.
- What felt good.
- With live writers: any place where the story contradicted itself or invented something. Say which episode.

## Known gaps

- Live writers can still contradict an earlier episode or invent a new place or office. The desk lists new names after each draft and you decide what to keep, but it cannot find a wrong fact.
- Memory is a long list of facts with their quotes. A compact view is not built yet.
- A long plan is one flat list. Named arcs are not built yet.
- No export, and no rename or delete for a series on the shelf. To remove a series, stop the program and delete its folder inside `stories`.
- Chat history lives in this browser only.
- Not tested live yet: running out of money mid-run, a restart in the middle of a paid run, and the secret check on a real draft.
