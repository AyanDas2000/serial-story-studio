"""The author sets how long each episode of a series should be. The writer is told, and the desk's limits follow."""
import sqlite3
import unittest

from serial_story.records import StoryError
from serial_story.v1.api import V1Api
from serial_story.v1.desk import WORD_BAND, WORD_HARD_MAX, Desk, Refused
from serial_story.v1.provider import GenerationResult, ScriptedProvider

from tests.test_v1_slice import V1Case


class ExactLength(ScriptedProvider):
    """Every draft has the same number of words."""

    def __init__(self, words: int):
        super().__init__()
        self.words = words

    def generate(self, request):
        result = super().generate(request)
        if request.recipe == 'sequential_draft':
            return GenerationResult(' '.join(['word'] * self.words) + '.')
        return result


class LengthCase(V1Case):
    def length(self):
        return self.desk.snapshot()['length']

    def drafts(self):
        return [c for c in self.provider.calls if c['recipe'] == 'sequential_draft']

    def with_words(self, words: int):
        self.provider = ExactLength(words)
        self.desk.provider = self.provider


class SettingTest(LengthCase):
    def test_a_new_series_uses_the_usual_length(self):
        low, target, high = WORD_BAND
        self.assertEqual(self.length(), {'low': low, 'target': target, 'high': high, 'limit': WORD_HARD_MAX, 'custom': False})

    def test_saving_a_length_changes_what_the_snapshot_reports(self):
        self.desk.set_length(low=250, target=350, high=450)
        shot = self.desk.snapshot()
        self.assertEqual(shot['length'], {'low': 250, 'target': 350, 'high': 450, 'limit': 540, 'custom': True})
        self.assertEqual((shot['word_band'], shot['word_limit']), ([250, 350, 450], 540))

    def test_the_latest_save_wins_and_survives_reopening(self):
        self.desk.set_length(low=250, target=350, high=450)
        self.desk.set_length(low=900, target=1200, high=1500)
        self.reopen()
        self.assertEqual(self.length()['target'], 1200)

    def test_each_save_is_recorded_in_the_history(self):
        self.desk.set_length(low=250, target=350, high=450)
        self.assertIn('length_save', [e['action'] for e in self.desk.history()])

    def test_bad_values_are_refused_and_change_nothing(self):
        bad = [(250, 350, 'x'), (250.5, 350, 450), (True, 350, 450), (None, 350, 450), (400, 350, 450), (250, 500, 450),
               (99, 200, 300), (250, 350, 3001), (-5, 350, 450), (350, 350, 349)]
        for low, target, high in bad:
            with self.assertRaises(Refused, msg=(low, target, high)) as why:
                self.desk.set_length(low=low, target=target, high=high)
            self.assertEqual(why.exception.code, 'invalid_length')
        self.assertFalse(self.length()['custom'])

    def test_equal_low_target_and_high_are_allowed(self):
        self.desk.set_length(low=300, target=300, high=300)
        self.assertEqual(self.length()['limit'], 360)

    def test_a_database_made_before_the_setting_still_opens(self):
        self.desk.connection.execute('DROP TABLE v1_length')
        self.desk.close()
        self.desk = Desk.open(self.path, provider=self.provider)
        self.assertFalse(self.length()['custom'])
        self.desk.set_length(low=250, target=350, high=450)
        self.assertEqual(self.length()['high'], 450)

    def test_the_command_checks_its_fields(self):
        api = V1Api(self.path, self.provider)
        self.desk.close()
        status, body = api.command('set_length', {'payload': {'low': 250, 'target': 350, 'high': 450}})
        self.assertEqual(status, 200, body)
        with self.assertRaises(StoryError):
            api.command('set_length', {'payload': {'low': 250, 'target': 350}})
        status, body = api.command('set_length', {'payload': {'low': 450, 'target': 350, 'high': 250}})
        self.assertEqual((status, body['code']), (400, 'invalid_length'))
        self.desk = Desk.open(self.path, provider=self.provider)


class WriterIsToldTest(LengthCase):
    def test_the_system_prompt_and_output_rules_use_the_authors_numbers(self):
        self.desk.set_length(low=250, target=350, high=450)
        self.adopt_direction()
        self.desk.commission_arc(slots=(1, 1))
        messages = self.drafts()[0]['params']['messages']
        self.assertIn('LENGTH\nEvery episode: aim for 350 words and stay within 250 to 450.', messages[0]['content'])
        self.assertIn('Length: aim for 350 words; stay within 250 to 450 words. Running past 450 words is worse than running short.',
                      messages[-1]['content'])
        self.assertNotIn('700', messages[0]['content'])

    def test_a_later_change_reaches_the_next_request_only(self):
        self.adopt_direction()
        self.desk.commission_arc(slots=(1, 1))
        self.desk.set_length(low=250, target=350, high=450)
        self.desk.redraft(1)
        first, second = [c['params']['messages'][0]['content'] for c in self.drafts()]
        self.assertIn('aim for 700 words', first)
        self.assertIn('aim for 350 words', second)
        shown = self.desk.draft_inspection(1)['parts'][0]['text']
        self.assertIn('aim for 350 words', shown)

    def test_changing_the_length_does_not_flag_or_replace_drafts_already_made(self):
        self.adopt_direction()
        self.desk.commission_arc(slots=(1, 2))
        before = [self.desk.selection(n)['revision_id'] for n in (1, 2)]
        self.desk.set_length(low=250, target=350, high=450)
        after = self.desk.snapshot()
        self.assertEqual([self.desk.selection(n)['revision_id'] for n in (1, 2)], before)
        self.assertEqual([e['open_impacts'] for e in after['episodes']][:2], [0, 0])


class LimitsFollowTest(LengthCase):
    def test_the_set_aside_limit_follows_the_authors_maximum(self):
        self.desk.set_length(low=200, target=300, high=400)
        self.with_words(470)
        self.adopt_direction()
        run = self.desk.commission_arc(slots=(1, 2))
        self.assertEqual(run['status'], 'complete', 'past the maximum but within a fifth: kept')
        shot = self.desk.snapshot()
        self.assertEqual(shot['episodes'][0]['length_warning']['band'], [200, 300, 400])

    def test_a_draft_past_a_fifth_over_the_authors_maximum_is_set_aside_with_the_numbers(self):
        self.desk.set_length(low=200, target=300, high=400)
        self.with_words(481)
        self.adopt_direction()
        run = self.desk.commission_arc(slots=(1, 2))
        self.assertEqual((run['status'], run['pause_reason']), ('paused', 'over_length'))
        detail = next(c for c in self.desk.snapshot()['commissions'] if c['commission_id'] == run['commission_id'])['pause_detail']
        self.assertEqual(detail, {'ordinal': 1, 'words': 481, 'limit': 480, 'within_limit': False})

    def test_short_drafts_stay_advisory(self):
        self.desk.set_length(low=600, target=800, high=1000)
        self.with_words(300)
        self.adopt_direction()
        self.assertEqual(self.desk.commission_arc(slots=(1, 1))['status'], 'complete')
        self.assertIsNotNone(self.desk.snapshot()['episodes'][0]['length_warning'])


if __name__ == '__main__':
    unittest.main()
