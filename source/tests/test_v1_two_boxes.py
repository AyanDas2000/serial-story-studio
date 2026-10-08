"""Two boxes: what the reader can know (the drafter sees it) and private notes (the drafter never sees them)."""
import json
import unittest

from serial_story.v1.desk import Refused
from tests.test_v1_slice import INTENTIONS, SKELETON, V1Case

PRIVATE_SPINE = 'Brandt-Veil is Oren\'s real surname; he faked the lockhouse fire.'
PRIVATE_ARC = 'Episode three ends with the ledger proving the Brandt-Veil forgery.'
PRIVATE_INTENTIONS = ['Plant the recorder as a clue to Brandt-Veil.', 'Let Darin half-hear the name Brandt-Veil.', 'Show the forged ledger page.']


class TwoBoxCase(V1Case):
    def adopt_two_boxes(self):
        skeleton = dict(SKELETON, private=PRIVATE_SPINE)
        arc = {'purpose': 'make Darin suspect a manufactured witness', 'end_state': 'an ordinary record the recorder cannot alter',
               'intentions': INTENTIONS, 'private': PRIVATE_ARC, 'private_intentions': PRIVATE_INTENTIONS}
        self.desk.adopt(self.desk.save_direction('skeleton', skeleton), expected_governing=None)
        self.desk.adopt(self.desk.save_direction('arc', arc), expected_governing=None)


class PrivateBoxTest(TwoBoxCase):
    def test_the_drafter_never_receives_private_notes(self):
        self.adopt_two_boxes()
        self.desk.commission_arc(slots=(1, 3))
        self.desk.redraft(2)
        sent = json.dumps([c['prompt'] for c in self.provider.calls if c['recipe'] == 'sequential_draft'] +
                          [r['prompt'] for r in self.desk.connection.execute('SELECT prompt FROM v1_job')]).casefold()
        for private in ('brandt-veil', 'real surname', 'forgery', 'forged ledger', 'half-hear'):
            self.assertNotIn(private, sent)
        self.assertIn('expose coercion', sent, 'the reader-safe spine is still sent')
        self.assertIn('lockhouse fire', sent, 'the reader-safe plan is still sent')

    def test_the_author_sees_private_notes_in_the_snapshot_and_a_proposal_keeps_them(self):
        self.adopt_two_boxes()
        arc = self.desk.snapshot()['directions']['arc']['content']
        self.assertEqual((arc['private'], arc['private_intentions']), (PRIVATE_ARC, PRIVATE_INTENTIONS))
        revision = self.desk.propose('skeleton')
        kept = json.loads(self.desk.revision(revision)['text'])
        self.assertEqual(kept['private'], PRIVATE_SPINE)

    def test_a_guarded_word_may_live_in_private_notes_but_not_in_the_reader_safe_box(self):
        self.adopt_two_boxes()
        self.desk.add_secret(label='Oren', body='Oren faked his death.', canaries=['Brandt-Veil'])
        done = self.desk.commission_arc(slots=(1, 3))
        self.assertEqual(done['status'], 'complete')
        spine = self.desk.save_direction('skeleton', dict(SKELETON, spine='Expose Brandt-Veil.'))
        self.desk.adopt(spine, expected_governing=self.desk.governing('skeleton')['revision_id'])
        with self.assertRaises(Refused) as refused:
            self.desk.redraft(2)
        self.assertEqual(refused.exception.code, 'secret_in_input')
        with self.assertRaises(Refused) as again:
            self.desk.add_secret(label='Second', body='Another secret.', canaries=['Expose Brandt-Veil'])
        self.assertEqual(again.exception.code, 'canary_already_visible')

    def test_private_fields_must_be_text_and_match_the_episode_count(self):
        for layer, content in (
                ('skeleton', dict(SKELETON, private=5)),
                ('arc', {'purpose': 'p', 'intentions': INTENTIONS, 'private': ['not text']}),
                ('arc', {'purpose': 'p', 'intentions': INTENTIONS, 'private_intentions': 'one string'}),
                ('arc', {'purpose': 'p', 'intentions': INTENTIONS, 'private_intentions': ['only one']}),
                ('arc', {'purpose': 'p', 'intentions': INTENTIONS, 'private_intentions': ['a', 'b', 7]})):
            with self.assertRaises(Refused) as refused:
                self.desk.save_direction(layer, content)
            self.assertEqual(refused.exception.code, 'invalid_direction', content)


if __name__ == '__main__':
    unittest.main()
