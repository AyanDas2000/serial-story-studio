"""Author-only secrets: protected terms never reach a drafter request before their reveal episode.

Maps to docs/research/MEMORY-CONTEXT-REVIEW.md answer 3 (one gate; canary terms; offline test).
"""
import json
import unittest

from serial_story.v1.desk import Refused
from tests.test_v1_slice import INTENTIONS, SKELETON, V1Case

SECRET_BODY = 'Oren is alive and hiding in the lockhouse cellar.'
CANARY = 'Zorvathian'


class SecretCase(V1Case):
    def adopt_with_canary_in_episode_two(self):
        self.desk.adopt(self.desk.save_direction('skeleton', SKELETON), expected_governing=None)
        intentions = list(INTENTIONS)
        intentions[1] = intentions[1] + f' The word {CANARY} is spoken once.'
        self.desk.adopt(self.desk.save_direction('arc', {'purpose': 'make Darin suspect a manufactured witness',
                                                          'end_state': 'an ordinary record the recorder cannot alter',
                                                          'intentions': intentions}), expected_governing=None)

    def sent(self, recipe='sequential_draft'):
        return [c for c in self.provider.calls if c['recipe'] == recipe]


class SecretRegistrationTest(SecretCase):
    def test_a_secret_needs_a_label_a_body_and_distinctive_canary_terms(self):
        for kwargs in ({'label': '', 'body': SECRET_BODY, 'canaries': [CANARY]},
                       {'label': 'Oren', 'body': '', 'canaries': [CANARY]},
                       {'label': 'Oren', 'body': SECRET_BODY, 'canaries': []},
                       {'label': 'Oren', 'body': SECRET_BODY, 'canaries': ['the']},
                       {'label': 'Oren', 'body': SECRET_BODY, 'canaries': [CANARY] * 2 + ['x' * 61]},
                       {'label': 'Oren', 'body': SECRET_BODY, 'canaries': [CANARY], 'reveal_ordinal': 0}):
            with self.assertRaises(Refused) as refused:
                self.desk.add_secret(**kwargs)
            self.assertEqual(refused.exception.code, 'invalid_secret', kwargs)

    def test_a_canary_already_visible_to_the_drafter_is_refused_at_registration(self):
        self.drafted()
        word = self.desk.revision(self.desk.selection(1)['revision_id'])['text'].split()[2].strip('.,;')
        self.assertGreaterEqual(len(word), 4)
        with self.assertRaises(Refused) as refused:
            self.desk.add_secret(label='Oren', body=SECRET_BODY, canaries=[word])
        self.assertEqual(refused.exception.code, 'canary_already_visible')
        self.assertEqual(self.desk.secrets(), [])

    def test_events_record_that_a_secret_changed_but_never_its_words(self):
        secret = self.desk.add_secret(label='Oren', body=SECRET_BODY, canaries=[CANARY])
        self.desk.reveal_secret(secret, 3)
        self.desk.retire_secret(secret)
        history = json.dumps(self.desk.history())
        self.assertIn('secret_add', history)
        self.assertNotIn(CANARY, history)
        self.assertNotIn('lockhouse cellar', history)
        listed = self.desk.secrets()[0]
        self.assertEqual((listed['label'], listed['canaries'], listed['reveal_ordinal'], listed['status']),
                         ('Oren', [CANARY], 3, 'retired'))


class SecretGateTest(SecretCase):
    def test_drafting_pauses_before_the_request_when_a_canary_would_be_sent(self):
        self.desk.add_secret(label='Oren', body=SECRET_BODY, canaries=[CANARY])
        self.adopt_with_canary_in_episode_two()
        result = self.desk.commission_arc(slots=(1, 3))
        self.assertEqual((result['status'], result['pause_reason']), ('paused', 'secret_in_input'))
        self.assertEqual(len(self.sent()), 1, 'episode 1 was drafted; episode 2 was never sent')
        self.assertIsNone(self.desk.selection(2))
        self.assertEqual(self.desk.connection.execute("SELECT count(*) FROM v1_job WHERE target_artifact_id=?",
                                                      (self.desk._episode_artifact(2),)).fetchone()[0], 0)

    def test_the_same_text_is_allowed_from_the_reveal_episode_onward(self):
        secret = self.desk.add_secret(label='Oren', body=SECRET_BODY, canaries=[CANARY])
        self.adopt_with_canary_in_episode_two()
        paused = self.desk.commission_arc(slots=(1, 3))
        self.desk.reveal_secret(secret, 2)
        done = self.desk.resume_commission(paused['commission_id'])
        self.assertEqual(done['status'], 'complete')
        self.assertTrue(all(self.desk.selection(n) for n in (1, 2, 3)))

    def test_a_retired_secret_stops_guarding(self):
        secret = self.desk.add_secret(label='Oren', body=SECRET_BODY, canaries=[CANARY])
        self.adopt_with_canary_in_episode_two()
        paused = self.desk.commission_arc(slots=(1, 3))
        self.desk.retire_secret(secret)
        self.assertEqual(self.desk.resume_commission(paused['commission_id'])['status'], 'complete')

    def test_a_requested_redraft_is_gated_too(self):
        self.drafted()
        self.desk.add_secret(label='Oren', body=SECRET_BODY, canaries=[CANARY])
        selection = self.desk.selection(1)
        revision = self.desk.revision(selection['revision_id'])
        blocks = [(b['block_id'], b['text']) for b in revision['blocks']]
        blocks[0] = (blocks[0][0], f'Leena whispered {CANARY.lower()} to nobody.')
        self.desk.save_revision(1, base_revision_id=revision['revision_id'], blocks=blocks, expected_cas=selection['cas'])
        before = len(self.sent())
        with self.assertRaises(Refused) as refused:
            self.desk.redraft(2)
        self.assertEqual(refused.exception.code, 'secret_in_input')
        self.assertEqual(len(self.sent()), before)

    def test_an_edit_that_leaks_a_canary_is_flagged_for_the_author(self):
        self.drafted()
        self.desk.add_secret(label='Oren', body=SECRET_BODY, canaries=[CANARY])
        selection = self.desk.selection(1)
        revision = self.desk.revision(selection['revision_id'])
        blocks = [(b['block_id'], b['text']) for b in revision['blocks']]
        blocks[0] = (blocks[0][0], f'Leena said {CANARY} aloud.')
        self.desk.save_revision(1, base_revision_id=revision['revision_id'], blocks=blocks, expected_cas=selection['cas'])
        episodes = {e['ordinal']: e for e in self.desk.snapshot()['episodes']}
        self.assertEqual(episodes[1]['secret_hits'], ['Oren'])
        self.assertEqual(episodes[2]['secret_hits'], [])


class SecretNeverLeavesTest(SecretCase):
    def test_no_request_job_or_snapshot_contains_the_secret_or_its_canary(self):
        secret = self.desk.add_secret(label='Hidden survivor', body=SECRET_BODY, canaries=[CANARY, 'cellar-door-key'])
        self.assertTrue(secret)
        self.drafted()
        self.desk.read_provisional(1)
        everything = json.dumps({
            'calls': self.provider.calls,
            'jobs': [dict(r) for r in self.desk.connection.execute('SELECT * FROM v1_job')],
            'snapshot': {k: v for k, v in self.desk.snapshot().items() if k != 'secrets'},
            'memory': self.desk.memory(),
        }, default=str).casefold()
        for forbidden in (CANARY, 'cellar-door-key', 'lockhouse cellar', 'hiding in'):
            self.assertNotIn(forbidden.casefold(), everything)


if __name__ == '__main__':
    unittest.main()
