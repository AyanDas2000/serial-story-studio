"""Reducing invented facts: standing instructions that ground the writer, and a plain check for new names.

A review of ten live episodes found no invented characters (the earlier rule works) but invented places and
organisations, evidence nobody in the scene supplied ("her neighbours say so"), and a character who knew something
nobody had told him. These tests hold the instructions and the check that answer those findings.
"""
import unittest

from serial_story.v1.desk import proper_names
from serial_story.v1.provider import GenerationResult, ScriptedProvider

from tests.test_v1_prompt_contract import SPINE_HEADER
from tests.test_v1_slice import V1Case


class SaysProvider(ScriptedProvider):
    """Returns fixed text for chosen episodes."""

    def __init__(self, texts: dict[int, str]):
        super().__init__()
        self.texts = texts

    def generate(self, request):
        result = super().generate(request)
        n = request.params.get('ordinal')
        if request.recipe == 'sequential_draft' and n in self.texts:
            return GenerationResult(self.texts[n])
        return result


class StandingInstructionsTest(V1Case):
    def system(self):
        self.drafted()
        call = next(c for c in self.provider.calls if c['recipe'] == 'sequential_draft')
        return call['params']['messages'][0]['content'], call['params']['messages'][-1]['content']

    def test_the_grounding_section_comes_before_the_story_direction(self):
        system, _ = self.system()
        self.assertIn('CONTINUITY AND GROUNDING', system)
        self.assertLess(system.index('CONTINUITY AND GROUNDING'), system.index(SPINE_HEADER))

    def test_each_finding_has_a_rule(self):
        system, _ = self.system()
        for phrase in (
            'Never contradict a name, age, number, date, place, object, relationship, injury or promise',
            'If the direction and an earlier episode disagree, follow the direction.',
            'A character may act only on what they have seen, been told, or could plainly infer in this story.',
            'show where it came from in the scene',
            'Do not claim support that no one in the story has given',
            'copy it exactly',
            'Do not settle any question the plan leaves open',
            'If you are not sure of a fact, leave it vague or leave it out.',
            'new place, office or company name is allowed only when this episode needs it',
        ):
            self.assertIn(phrase, system)

    def test_the_last_message_points_back_at_the_rules(self):
        _, last = self.system()
        self.assertIn('Grounding: follow CONTINUITY AND GROUNDING above', last)

    def test_the_rules_are_the_same_for_every_episode_so_they_stay_cached(self):
        self.drafted()
        systems = {c['params']['messages'][0]['content'].split('ESTABLISHED STORY DATA')[0] for c in self.provider.calls if c['recipe'] == 'sequential_draft'}
        self.assertEqual(len(systems), 1, 'everything before the story data is identical from episode to episode')


class NewNamesTest(V1Case):
    def start(self, texts):
        self.provider = SaysProvider(texts)
        self.desk.provider = self.provider
        self.adopt_direction()
        self.desk.commission_arc(slots=(1, 2))
        return {e['ordinal']: e for e in self.desk.snapshot()['episodes']}

    def test_names_not_in_the_direction_or_earlier_episodes_are_listed(self):
        eps = self.start({1: 'Leena met Haskett at the Customs Library. "Come here," said Darin. Oren waited.',
                          2: 'Haskett came back with Aldermoor. Darin read the ledger.'})
        self.assertEqual(eps[1]['new_names'], ['Customs', 'Haskett', 'Library'])
        self.assertEqual(eps[2]['new_names'], ['Aldermoor'])

    def test_sentence_openers_and_dialogue_openers_are_not_names(self):
        eps = self.start({1: 'Then Leena waited. "Where is he?" asked Darin. "Come in." Everything stopped. Oren left.',
                          2: 'Darin read.'})
        self.assertEqual(eps[1]['new_names'], [])

    def test_a_possessive_of_a_name_already_used_is_not_new(self):
        eps = self.start({1: '"Cooper\'s Stair is steep," said Leena. Darin read.', 2: 'Leena climbed Cooper\'s Stair. Darin read the Stair.'})
        self.assertEqual(eps[1]['new_names'], ['Stair'])
        self.assertEqual(eps[2]['new_names'], [])

    def test_approved_episodes_are_not_flagged(self):
        eps = self.start({1: 'Leena met Haskett.', 2: 'Darin read.'})
        sel = eps[1]['selection']
        self.desk.accept_prefix([(1, sel['revision_id'], sel['sha256'])], expected_canon_seq=0)
        again = {e['ordinal']: e for e in self.desk.snapshot()['episodes']}
        self.assertEqual(again[1]['new_names'], [])

    def test_proper_names_skips_weekdays_titles_and_short_words(self):
        self.assertEqual(proper_names('She came on Tuesday with Mrs Haskett and Sir Dunn, not Ed.'), {'Haskett', 'Dunn'})
        self.assertEqual(proper_names('Tomas\'s coat and Tomas.'), {'Tomas'})


if __name__ == '__main__':
    unittest.main()
