"""A live author run found two traps:

1. Resuming a paused drafting run asked for every earlier episode again, replacing drafts the author had already read.
2. A draft that ran past the length limit was paid for and set aside, but its words could not be read, trimmed or used.
"""
import unittest

from serial_story.v1.desk import WORD_BAND, WORD_HARD_MAX, Refused
from serial_story.v1.provider import GenerationResult, ScriptedProvider

from tests.test_v1_slice import V1Case


class LongOnceProvider(ScriptedProvider):
    """Over the limit the first time one episode is drafted, normal afterwards."""

    def __init__(self, ordinal: int, words: int):
        super().__init__()
        self.ordinal, self.words, self.long_sent = ordinal, words, False

    def generate(self, request):
        result = super().generate(request)
        if request.recipe == 'sequential_draft' and request.params.get('ordinal') == self.ordinal and not self.long_sent:
            self.long_sent = True
            text = ' '.join(['Darin read the ledger twice before he spoke.'.split()[i % 8] for i in range(self.words)])
            return GenerationResult(text + '.')
        return result


class Case(V1Case):
    def start(self, ordinal=3, words=WORD_HARD_MAX + 40):
        self.provider = LongOnceProvider(ordinal, words)
        self.desk.provider = self.provider
        self.adopt_direction()
        return self.desk.commission_arc(slots=(1, 3), progression='provisional_chain')

    def drafts_of(self, ordinal):
        return [c for c in self.provider.calls if c['recipe'] == 'sequential_draft' and c['params'].get('ordinal') == ordinal]

    def episode(self, ordinal):
        return next(e for e in self.desk.snapshot()['episodes'] if e['ordinal'] == ordinal)


class ResumeKeepsDraftedEpisodesTest(Case):
    def test_resume_asks_only_for_the_episode_that_stopped(self):
        paused = self.start()
        self.assertEqual(paused['pause_reason'], 'over_length')
        before = {n: self.desk.selection(n)['revision_id'] for n in (1, 2)}
        done = self.desk.resume_commission(paused['commission_id'])
        self.assertEqual(done['status'], 'complete')
        self.assertEqual([len(self.drafts_of(n)) for n in (1, 2, 3)], [1, 1, 2])
        self.assertEqual({n: self.desk.selection(n)['revision_id'] for n in (1, 2)}, before)

    def test_an_edit_to_an_earlier_episode_stops_the_resume_and_nothing_is_overwritten(self):
        paused = self.start()
        e1 = self.desk.selection(1)
        blocks = [(b['block_id'], b['text']) for b in self.desk.revision(e1['revision_id'])['blocks']]
        blocks[0] = (blocks[0][0], 'A new first paragraph that changes what follows.')
        self.desk.save_revision(1, base_revision_id=e1['revision_id'], blocks=blocks, expected_cas=e1['cas'])
        with self.assertRaises(Refused) as stopped:
            self.desk.resume_commission(paused['commission_id'])
        self.assertEqual(stopped.exception.code, 'open_conflict')
        self.assertEqual([len(self.drafts_of(n)) for n in (1, 2, 3)], [1, 1, 1])


class SetAsideDraftTest(Case):
    def test_the_set_aside_draft_can_be_read_with_its_length(self):
        self.start(words=WORD_HARD_MAX + 40)
        alt = self.episode(3)['alternatives'][0]
        self.assertEqual(alt['words'], WORD_HARD_MAX + 40)
        self.assertEqual(alt['text'].split()[:2], ['Darin', 'read'])
        self.assertEqual(alt['detached_reason'], 'over_length')

    def test_the_pause_says_which_episode_and_how_long(self):
        paused = self.start(words=WORD_HARD_MAX + 40)
        row = next(c for c in self.desk.snapshot()['commissions'] if c['commission_id'] == paused['commission_id'])
        self.assertEqual(row['pause_detail'], {'ordinal': 3, 'words': WORD_HARD_MAX + 40, 'limit': WORD_HARD_MAX, 'within_limit': False})

    def test_a_pause_made_under_a_stricter_limit_says_it_is_now_within_the_limit(self):
        paused = self.start(words=WORD_HARD_MAX + 40)
        self.desk.set_length(low=550, target=1200, high=1500)
        row = next(c for c in self.desk.snapshot()['commissions'] if c['commission_id'] == paused['commission_id'])
        self.assertEqual(row['pause_detail'], {'ordinal': 3, 'words': WORD_HARD_MAX + 40, 'limit': 1800, 'within_limit': True})

    def test_a_pause_still_over_the_limit_is_not_marked_within_it(self):
        paused = self.start(words=WORD_HARD_MAX + 40)
        row = next(c for c in self.desk.snapshot()['commissions'] if c['commission_id'] == paused['commission_id'])
        self.assertFalse(row['pause_detail']['within_limit'])

    def test_using_the_draft_selects_it_and_resume_carries_on_without_asking_again(self):
        paused = self.start()
        alt = self.episode(3)['alternatives'][0]
        self.assertIsNone(self.desk.selection(3))
        self.desk.use_draft(3, alt['revision_id'], expected_cas=0)
        chosen = self.desk.selection(3)
        self.assertEqual((chosen['revision_id'], chosen['selected_by']), (alt['revision_id'], 'author'))
        self.assertEqual(self.episode(3)['length_warning']['words'], WORD_HARD_MAX + 40)
        done = self.desk.resume_commission(paused['commission_id'])
        self.assertEqual(done['status'], 'complete')
        self.assertEqual(len(self.drafts_of(3)), 1)

    def test_the_chosen_draft_can_then_be_trimmed_by_hand(self):
        self.start()
        alt = self.episode(3)['alternatives'][0]
        self.desk.use_draft(3, alt['revision_id'], expected_cas=0)
        sel = self.desk.selection(3)
        blocks = [(b['block_id'], b['text']) for b in self.desk.revision(sel['revision_id'])['blocks']]
        saved = self.desk.save_revision(3, base_revision_id=sel['revision_id'], blocks=blocks[:1], expected_cas=sel['cas'])
        self.assertTrue(saved['revision_id'])

    def test_using_a_draft_is_refused_when_it_is_not_this_episodes_set_aside_draft(self):
        self.start()
        other = self.desk.selection(1)['revision_id']
        for ordinal, revision, cas in ((3, other, 0), (3, 'rv-missing', 0), (3, self.episode(3)['alternatives'][0]['revision_id'], 5)):
            with self.assertRaises(Refused, msg=(ordinal, revision, cas)):
                self.desk.use_draft(ordinal, revision, expected_cas=cas)
        self.assertIsNone(self.desk.selection(3))

    def test_using_a_draft_is_refused_once_the_episode_is_approved(self):
        self.start()
        alt = self.episode(3)['alternatives'][0]
        self.desk.use_draft(3, alt['revision_id'], expected_cas=0)
        picked = [{'ordinal': n, 'revision_id': self.desk.selection(n)['revision_id'], 'sha256': self.desk.selection(n)['sha256']} for n in (1, 2, 3)]
        self.desk.accept_prefix([(p['ordinal'], p['revision_id'], p['sha256']) for p in picked], expected_canon_seq=0)
        with self.assertRaises(Refused):
            self.desk.use_draft(3, alt['revision_id'], expected_cas=self.desk.selection(3)['cas'])


if __name__ == '__main__':
    unittest.main()
