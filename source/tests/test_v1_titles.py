"""Episode titles and retryable drafting failures.

The writer names each draft with one `Title: …` line; the desk stores the title apart from the
prose. An answer that was billed but cannot be used (cut off, empty, an echo of the original)
pauses the run with a reason the author can act on directly, instead of the settle-a-charge flow.
"""
import unittest

from serial_story.v1.desk import Refused, split_title
from serial_story.v1.provider import AnswerUnusable, ScriptedProvider
from tests.test_v1_slice import V1Case


class SplitTitleTest(unittest.TestCase):
    def test_a_title_line_is_separated_from_the_prose(self):
        title, text = split_title('Title: The Brass Compass\n\nRon opened the drawer.')
        self.assertEqual(title, 'The Brass Compass')
        self.assertEqual(text, 'Ron opened the drawer.')

    def test_missing_or_malformed_titles_leave_the_text_alone(self):
        self.assertEqual(split_title('Ron opened the drawer.'), (None, 'Ron opened the drawer.'))
        long = 'Title: ' + 'x ' * 50 + '\n\nBody.'
        self.assertEqual(split_title(long), (None, long))
        self.assertEqual(split_title('Title: "The Lockhouse"\n\nBody.'), ('The Lockhouse', 'Body.'))


class TitleFlowTest(V1Case):
    def test_drafted_episodes_carry_a_title_and_clean_prose(self):
        self.drafted()
        episodes = self.desk.snapshot()['episodes']
        self.assertEqual(episodes[0]['title'], 'The 1th turning')
        self.assertNotIn('Title:', episodes[0]['text'])
        self.assertTrue(episodes[0]['text'].startswith('[E1.1]'))

    def test_a_draft_without_a_title_line_still_imports(self):
        class Bare(ScriptedProvider):
            def draft_text(self, key, ordinal, variant=0):
                return super().draft_text(key, ordinal, variant).split('\n\n', 1)[1]
        self.desk.provider = Bare()
        self.adopt_direction()
        self.desk.commission_arc(slots=(1, 1))
        episode = self.desk.snapshot()['episodes'][0]
        self.assertIsNone(episode['title'])
        self.assertTrue(episode['text'].startswith('[E1.1]'))

    def test_a_title_survives_approval_and_reopen(self):
        self.drafted()
        sel = self.desk.selection(1)
        self.desk.accept_prefix([(1, sel['revision_id'], sel['sha256'])], expected_canon_seq=0)
        self.reopen()
        episode = next(e for e in self.desk.snapshot()['episodes'] if e['ordinal'] == 1)
        self.assertEqual(episode['title'], 'The 1th turning')

    def test_an_unusable_answer_pauses_with_a_retryable_reason_and_resume_continues(self):
        self.adopt_direction()
        state = {'fail': True}

        def cut_off(request):
            if request.recipe == 'sequential_draft' and state['fail']:
                raise AnswerUnusable('scripted cut-off')
        self.provider.during_exchange = cut_off
        run = self.desk.commission_arc(slots=(1, 3))
        self.assertEqual((run['status'], run['pause_reason']), ('paused', 'unusable_answer'))
        job = self.desk.connection.execute('SELECT state FROM v1_job').fetchone()
        self.assertEqual(job[0], 'resolved')  # billed and discarded: nothing left to settle
        self.assertEqual(self.desk.uncertain_jobs(), [])
        state['fail'] = False
        self.provider.during_exchange = None
        run = self.desk.resume_commission(run['commission_id'])
        self.assertEqual(run['status'], 'complete')
        episodes = self.desk.snapshot()['episodes']
        self.assertEqual([e['ordinal'] for e in episodes], [1, 2, 3])
        self.assertTrue(all(e['title'] for e in episodes))

    def test_a_redraft_with_an_unusable_answer_changes_nothing(self):
        self.drafted()
        before = self.desk.selection(1)['revision_id']

        def cut_off(request):
            if request.recipe == 'sequential_draft':
                raise AnswerUnusable('scripted cut-off')
        self.provider.during_exchange = cut_off
        with self.assertRaises(Refused) as refused:
            self.desk.redraft(1)
        self.assertEqual(refused.exception.code, 'unusable_answer')
        job = self.desk.connection.execute('SELECT state FROM v1_job ORDER BY rowid DESC').fetchone()
        self.assertEqual(job[0], 'resolved')
        self.assertEqual(self.desk.selection(1)['revision_id'], before)


if __name__ == '__main__':
    unittest.main()
