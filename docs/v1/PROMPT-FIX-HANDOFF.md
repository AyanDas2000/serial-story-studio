# Prompt-contract fix: handoff

Scope: `Desk._freeze_draft` prompt assembly and the length gate it requires. Owned files: `project/serial_story/v1/desk.py`, `project/tests/test_v1_prompt_contract.py` (new). No live model call was made.

Source of wording: `specs/OWNER-DECISIONS.md` **does not exist** in this workspace. I used the owner band recorded in `desk.py` (`WORD_BAND = (550, 700, 900)`, advisory at acceptance), docs/v1/01 J7 ("Length is advisory"), docs/v1/04 §192 (style notes are secondary `sequential_draft` inputs; predecessors untruncated), and docs/v1/03 (plain words, no internal terms). If that file exists elsewhere, check the wording against it.

## Final prompt template (`desk.draft_prompt`)

Rendered for episode 2 with placeholders. Fixed overhead is about 1,400 characters.

```
You are writing episode 2 of a serial story. Write that one episode as narrative prose and nothing else.

PRECEDENCE
The spine and arc outrank the established story data and the voice notes. If sections conflict, follow this order: 1. the governing spine, 2. the arc purpose, 3. this episode's job, 4. the established story data, 5. the adopted voice notes.

AUTHOR'S GOVERNING SPINE (do not restate)
{skeleton.spine}

ARC PURPOSE
{arc.purpose}

THIS EPISODE'S JOB (episode 2)
{arc.intentions[1]}

ESTABLISHED STORY DATA (reference only; do not imitate its formatting)
Earlier episodes, in story order. This is canon to stay consistent with, not a template to copy form from, and it ranks below the spine and arc. Keep its facts, names and events; ignore its layout.

[Episode 1 begins]
{exact text of episode 1: canon if accepted, else current selection}
[Episode 1 ends]

ADOPTED VOICE NOTES (lower priority than the spine and arc)
Apply these only where they do not conflict with anything above; they never override the spine, the arc or this episode's job.
- {adopted note}

OUTPUT RULES
- Form: continuous narrative prose for episode 2 only. No headings, no markdown, no screenplay or script format, no stage directions, no speaker labels, no sound cues, no episode title or preamble, no notes or commentary. Dialogue sits inside the prose in quotation marks.
- Length: aim for 700 words; stay within 550 to 900 words. Running past 900 words is worse than running short.
- Characters: Do not introduce a named character who does not already appear in the established story data or the direction above. When the established story data names a person, use that exact name. Unnamed minor figures are allowed.
- Ending: end on a turn (a decision, a discovery, a reversal), not a summary or a moral.
- Return the episode text only.
```

Episode 1 gets `None yet. This is the first episode.` under the data header. With no adopted notes the voice section reads `None adopted.`. The output rules come last on purpose: in the failing run, the last thing the model read was thousands of characters of predecessor prose.

## Length decision: refused, not truncated

A commission draft over 900 words (the band maximum, not the 700 target) is **stored whole** as a revision, recorded as `detached` with `detached_reason='over_length'`, and **not selected automatically**. The commission pauses with `pause_reason='over_length'`, so the next episode is never drafted from it. The desk never cuts text. Short drafts stay advisory (owner decision), and acceptance stays advisory too. Exactly 900 words is still selected.

## Tests (`tests/test_v1_prompt_contract.py`): RED then GREEN

| Test | RED (before) | GREEN (after) |
|---|---|---|
| OutputFormTest.test_prompt_requires_prose_and_forbids_script_markdown_and_heading_forms | ERROR, ValueError: substring not found | ok |
| OutputFormTest.test_output_rules_come_after_all_story_data | ERROR, ValueError | ok |
| LengthTest.test_prompt_names_target_and_band_and_prefers_short_over_long | ERROR, ValueError | ok |
| SectionLabelTest.test_every_section_is_labelled_and_in_contract_order | ERROR, ValueError | ok |
| SectionLabelTest.test_predecessor_canon_is_reference_only_and_subordinate_to_spine_and_arc | ERROR, ValueError | ok |
| SectionLabelTest.test_first_episode_says_there_is_no_established_story_data | ERROR, ValueError | ok |
| SectionLabelTest.test_adopted_voice_notes_are_labelled_lower_priority_than_spine_and_arc | ERROR, ValueError | ok |
| SectionLabelTest.test_no_voice_notes_is_stated_rather_than_omitted | ERROR, ValueError | ok |
| PrecedenceTest.test_precedence_of_spine_and_arc_over_predecessor_and_voice_is_explicit | ERROR, ValueError | ok |
| NamedCharacterTest.test_prompt_forbids_inventing_named_characters_and_requires_established_names | ERROR, ValueError | ok |
| OverLengthTest.test_draft_past_band_maximum_is_stored_whole_detached_and_pauses_the_commission | FAIL: `('complete', None) != ('paused', 'over_length')` | ok |
| OverLengthTest.test_draft_at_band_maximum_is_still_selected | ok (boundary guard, green by design) | ok |

Suite counts (real):
- New file: Ran 12, OK.
- v1 suites (http, slice, journey, prompt_contract): Ran 32, OK (the 20 baseline tests still pass).
- Full `python -m unittest discover -s tests`: Ran 162, errors=11, failures=0. All 11 are `FileNotFoundError` in the unchanged `test_merge_authoring.py`, matching the stated pre-existing 11. Details are in `PROGRESS.md`.

## Deliberately not changed

- `serial_story/studio/*`, `repository.py`, `budget.py`, `authoring.py`, `merge.py`, `provider.py`, all `live_*` scripts. Every baseline-hashed file except `desk.py` is byte-identical.
- M12 (partial or malformed output retention): the desk still ignores `GenerationResult.completeness`. A provider-side cut at a token cap is still stored as-is. This fix does not detect a mid-sentence ending.
- No `max_tokens` cap or band hint is passed to the provider. The live provider scripts own their caps, and I may not edit them.
- `redraft()`: its results were already always detached (`author_request`), never auto-selected. It does not get an `over_length` label.
- No manual "select this alternative" action was added. One does not exist today for any detached alternative.
- The skeleton `premise` is still not sent. Only `spine` is sent, as before.
- No context-size budget was added for the growing predecessor text (docs/v1/02 blocking is a separate item).

## Risks in the assembled prompt

1. **Untested against a model.** The tests prove the contract text is present and ordered. They do not prove Opus will produce prose. The next live linked run is the real check.
2. **Name rule versus thin direction.** The rule allows names from "the established story data or the direction above". The premise is not sent, so in episode 1 the only names are those in the spine, arc or intention. The model may then leave the protagonist unnamed or invent one despite the rule. Adding the premise would fix this, but it is outside this change.
3. **Prompt growth.** Predecessors are sent untruncated, per the spec, so episode N carries all N−1 texts. By around episode 10 the data section dwarfs the rules. Putting the rules last helps, but it is not a budget.
4. **Delimiter collision.** If an episode's own text contained `[Episode 1 ends]` or a section header in capitals, the framing could blur. This is unlikely, and nothing escapes it.
5. **Token cap below the band.** If a live provider caps output under about 1,300 tokens, 900 words can still be cut mid-sentence, and the result will be stored and possibly selected (M12). The over-length gate only catches drafts that are too long, not ones that are cut off.
6. **Resume costs a new draft.** After an `over_length` pause, `resume_commission` drafts the slot again: a new provider call, with no automatic retry. The author has no way to select the long draft instead.
7. **Hash churn.** Every `sequential_draft` request hash changes because the prompt changed. Jobs frozen before this change keep their old prompt text, as they should.
