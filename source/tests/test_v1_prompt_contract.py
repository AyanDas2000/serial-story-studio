"""Assembled `sequential_draft` prompt contract (Desk._freeze_draft).

A live linked run returned episode 2 as a screenplay with invented characters:
the prompt had no output form, no length, and appended predecessor prose with no
framing or ranking. These tests assert on the exact prompt the provider receives.
"""
import unittest

from serial_story.v1.desk import WORD_BAND, WORD_HARD_MAX
from serial_story.v1.provider import GenerationResult, ScriptedProvider

from tests.test_v1_slice import V1Case

SPINE_HEADER = "AUTHOR'S GOVERNING SPINE (do not restate)"
ARC_HEADER = 'ARC PURPOSE'
JOB_HEADER = "THIS EPISODE'S JOB"
DATA_HEADER = 'ESTABLISHED STORY DATA (reference only; do not imitate its formatting)'
VOICE_HEADER = 'ADOPTED VOICE NOTES (lower priority than the spine and arc)'
RULES_HEADER = 'OUTPUT RULES'
# Cache-friendly order (docs/research/MEMORY-CONTEXT-REVIEW.md F2): what repeats across episodes first,
# this episode's job and the output rules last.
HEADERS = [SPINE_HEADER, ARC_HEADER, VOICE_HEADER, DATA_HEADER, JOB_HEADER, RULES_HEADER]


def section(prompt: str, header: str) -> str:
    """Text between `header` and the next known section header."""
    start = prompt.index(header) + len(header)
    later = [prompt.find(h, start) for h in HEADERS if prompt.find(h, start) > 0]
    return prompt[start:min(later) if later else len(prompt)]


class LengthProvider(ScriptedProvider):
    """Scripted provider whose draft for one slot has an exact word count."""

    def __init__(self, ordinal: int, words: int):
        super().__init__()
        self.ordinal, self.words = ordinal, words

    def generate(self, request):
        result = super().generate(request)
        if request.recipe == 'sequential_draft' and request.params.get('ordinal') == self.ordinal:
            sentence = 'Darin read the ledger twice before he spoke.'
            words = (sentence + ' ') * (self.words // 8 + 1)
            text = ' '.join(words.split()[:self.words])
            return GenerationResult(text.rstrip('.') + '.')
        return result


class PromptContractCase(V1Case):
    def draft_prompts(self) -> list[str]:
        self.drafted()
        return [c['prompt'] for c in self.provider.calls if c['recipe'] == 'sequential_draft']

    def prompt_with_voice_note(self) -> tuple[str, str, str]:
        """Episode 2 redraft prompt with one adopted voice note; returns (prompt, note, predecessor text)."""
        e1 = self.drafted()[0]
        base = self.desk.revision(e1['revision_id'])
        blocks = [(b['block_id'], b['text']) for b in base['blocks']]
        blocks[1] = (blocks[1][0], 'She left. She did not look back.')
        saved = self.desk.save_revision(1, base_revision_id=base['revision_id'], blocks=blocks, expected_cas=e1['cas'])
        note = 'Leena POV: clipped sentences.'
        self.desk.adopt_style(self.desk.propose_style(note, evidence=[{'kind': 'human_edit', 'event_id': saved['event_id']}]))
        self.desk.revalidate(2)
        self.desk.redraft(2)
        predecessor = self.desk.revision(self.desk.selection(1)['revision_id'])['text']
        return self.provider.calls[-1]['prompt'], note, predecessor


class OutputFormTest(PromptContractCase):
    def test_prompt_requires_prose_and_forbids_script_markdown_and_heading_forms(self):
        for prompt in self.draft_prompts():
            rules = section(prompt, RULES_HEADER).lower()
            self.assertIn('narrative prose', rules)
            for forbidden in ('no headings', 'no markdown', 'no screenplay', 'no stage directions',
                              'no speaker labels', 'no preamble'):
                self.assertIn(forbidden, rules, forbidden)
            self.assertIn('- title: begin your reply with exactly one line of the form `title: `', rules)
            self.assertIn('return the title line and the episode text, nothing else', rules)
            self.assertIn('end on a turn', rules)
            self.assertIn('not a summary', rules)

    def test_output_rules_come_after_all_story_data(self):
        # The last thing the model reads must be the contract, not predecessor prose.
        prompt = self.draft_prompts()[1]
        self.assertGreater(prompt.index(RULES_HEADER), prompt.index(DATA_HEADER))
        self.assertGreater(prompt.index(RULES_HEADER), prompt.index(VOICE_HEADER))


class LengthTest(PromptContractCase):
    def test_prompt_names_target_and_band_and_prefers_short_over_long(self):
        low, target, high = WORD_BAND
        self.assertEqual(WORD_BAND, (550, 700, 900))
        for prompt in self.draft_prompts():
            rules = section(prompt, RULES_HEADER)
            self.assertIn(f'{target} words', rules)
            self.assertIn(f'{low} to {high} words', rules)
            self.assertIn(f'Running past {high} words is worse than running short', rules)


class SectionLabelTest(PromptContractCase):
    def test_every_section_is_labelled_and_in_contract_order(self):
        prompt, _, _ = self.prompt_with_voice_note()
        positions = [prompt.index(h) for h in HEADERS]
        self.assertEqual(positions, sorted(positions))
        self.assertIn('Expose coercion; useful lies give way to accountable uncertainty.', section(prompt, SPINE_HEADER))
        self.assertIn('make Darin suspect a manufactured witness', section(prompt, ARC_HEADER))
        self.assertIn('A witness says courier Oren died in a lockhouse fire; Darin hears it.', section(prompt, JOB_HEADER))

    def test_predecessor_canon_is_reference_only_and_subordinate_to_spine_and_arc(self):
        prompt, _, predecessor = self.prompt_with_voice_note()
        data = section(prompt, DATA_HEADER)
        self.assertIn(predecessor, data)
        self.assertEqual(prompt.count(predecessor), 1, 'predecessor prose appears only inside its labelled section')
        self.assertIn('[Episode 1 begins]', data)
        self.assertIn('[Episode 1 ends]', data)
        self.assertIn('canon to stay consistent with, not a template to copy form from', data)
        self.assertIn('ranks below the spine and arc', data)

    def test_first_episode_says_there_is_no_established_story_data(self):
        first = self.draft_prompts()[0]
        self.assertIn('None yet. This is the first episode.', section(first, DATA_HEADER))
        self.assertNotIn('[Episode', first)

    def test_adopted_voice_notes_are_labelled_lower_priority_than_spine_and_arc(self):
        prompt, note, _ = self.prompt_with_voice_note()
        voice = section(prompt, VOICE_HEADER)
        self.assertIn('- ' + note, voice)
        self.assertEqual(prompt.count(note), 1, 'voice note appears only inside its labelled section')
        self.assertIn('never override the spine, the arc or this episode\'s job', voice)

    def test_no_voice_notes_is_stated_rather_than_omitted(self):
        self.assertIn('None adopted.', section(self.draft_prompts()[0], VOICE_HEADER))


class PrecedenceTest(PromptContractCase):
    def test_precedence_of_spine_and_arc_over_predecessor_and_voice_is_explicit(self):
        prompt, _, _ = self.prompt_with_voice_note()
        head = prompt[:prompt.index(SPINE_HEADER)]
        self.assertIn('PRECEDENCE', head)
        self.assertIn('If sections conflict, follow this order: 1. the governing spine, 2. the arc purpose, '
                      "3. this episode's job, 4. the established story data, 5. the adopted voice notes.", head)
        self.assertIn('The spine and arc outrank the established story data and the voice notes.', head)


class NamedCharacterTest(PromptContractCase):
    def test_prompt_forbids_inventing_named_characters_and_requires_established_names(self):
        for prompt in self.draft_prompts():
            rules = section(prompt, RULES_HEADER)
            self.assertIn('Do not introduce a named character who does not already appear in the established story data '
                          'or the direction above.', rules)
            self.assertIn('When the established story data names a person, use that exact name.', rules)


class OverLengthTest(V1Case):
    """Decision: a draft over the band maximum is kept whole but REFUSED automatic selection.

    It is never truncated by the desk. The commission pauses with `over_length`.
    Short drafts stay advisory (owner decision), so only the maximum gates selection.
    """

    def run_with(self, words: int):
        self.provider = LengthProvider(2, words)
        self.desk.provider = self.provider
        self.adopt_direction()
        return self.desk.commission_arc(slots=(1, 3), progression='provisional_chain')

    def test_draft_past_band_maximum_is_stored_whole_detached_and_pauses_the_commission(self):
        high = WORD_HARD_MAX
        commission = self.run_with(high + 50)
        self.assertEqual((commission['status'], commission['pause_reason']), ('paused', 'over_length'))
        self.assertIsNone(self.desk.selection(2))
        alternatives = next(e for e in self.desk.snapshot()['episodes'] if e['ordinal'] == 2)['alternatives']
        self.assertEqual([a['detached_reason'] for a in alternatives], ['over_length'])
        stored = self.desk.revision(alternatives[0]['revision_id'])['text']
        self.assertEqual(len(stored.split()), high + 50, 'kept whole, not cut')
        self.assertTrue(stored.endswith('.'))
        self.assertEqual([c['params']['ordinal'] for c in self.provider.calls if c['recipe'] == 'sequential_draft'], [1, 2],
                         'episode 3 is not drafted from an over-length predecessor')
        self.assertIn('result_detached', [e['action'] for e in self.desk.history()])

    def test_draft_at_band_maximum_is_still_selected(self):
        commission = self.run_with(WORD_BAND[2])
        self.assertEqual(commission['status'], 'complete')
        self.assertEqual(self.desk.selection(2)['selected_by'], 'commission')

    def test_draft_a_little_past_the_band_is_kept_selected_and_flagged(self):
        words = WORD_BAND[2] + 150
        self.assertLess(words, WORD_HARD_MAX)
        commission = self.run_with(words)
        self.assertEqual(commission['status'], 'complete')
        episode = next(e for e in self.desk.snapshot()['episodes'] if e['ordinal'] == 2)
        self.assertEqual(episode['words'], words)
        self.assertEqual(episode['length_warning']['words'], words)

    def test_draft_exactly_at_the_hard_limit_is_still_selected(self):
        self.assertEqual(self.run_with(WORD_HARD_MAX)['status'], 'complete')

    def test_the_system_prompt_states_the_length_the_writer_is_held_to(self):
        self.drafted()
        system = next(c for c in self.provider.calls if c['recipe'] == 'sequential_draft')['params']['messages'][0]
        self.assertEqual(system['role'], 'system')
        low, target, high = WORD_BAND
        self.assertIn(f'LENGTH\nEvery episode: aim for {target} words and stay within {low} to {high}.', system['content'])
        self.assertIn('kept and flagged for them', system['content'])
        self.assertIn('the author decides whether to use it or ask for a new one', system['content'])
        self.assertNotIn('has to be written again', system['content'])
        self.assertTrue(system['content'].index('LENGTH') < system['content'].index(SPINE_HEADER))


if __name__ == '__main__':
    unittest.main()
