"""V1 vertical slice (docs/v1/01 §3, J1-J9) against the deterministic scripted provider."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from serial_story.records import StoryError
from serial_story.v1.desk import Desk, Refused
from serial_story.v1.provider import ScriptedProvider

REPO = Path(__file__).resolve().parents[1]
RUNS = REPO / 'local' / 'test-runs'

SKELETON = {'premise': 'Leena Vale borrows voices; each use costs a memory.',
            'spine': 'Expose coercion; useful lies give way to accountable uncertainty.'}
INTENTIONS = ['Leena stages a witness interview; the reader sees her memory cost.',
              'A witness says courier Oren died in a lockhouse fire; Darin hears it.',
              'Darin obtains the dispatch ledger that predates the alleged death.']


class V1Case(unittest.TestCase):
    def setUp(self):
        RUNS.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=RUNS)
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'story.db'
        self.provider = ScriptedProvider()
        self.desk = Desk.create(self.path, provider=self.provider)
        self.addCleanup(lambda: self.desk.close())

    def reopen(self):
        self.desk.close()
        self.desk = Desk.open(self.path, provider=self.provider)

    def adopt_direction(self):
        s1 = self.desk.save_direction('skeleton', SKELETON)
        self.desk.adopt(s1, expected_governing=None)
        a1 = self.desk.save_direction('arc', {'purpose': 'make Darin suspect a manufactured witness',
                                               'end_state': 'an ordinary record the recorder cannot alter',
                                               'intentions': INTENTIONS})
        self.desk.adopt(a1, expected_governing=None)
        return s1, a1

    def drafted(self):
        self.adopt_direction()
        self.desk.commission_arc(slots=(1, 3), progression='provisional_chain')
        return [self.desk.selection(n) for n in (1, 2, 3)]


class DirectionBackboneTest(V1Case):
    def test_chat_suggestions_and_working_proposals_never_replace_adopted_direction(self):
        s1, _ = self.adopt_direction()
        self.desk.converse(target=s1, text='What if Leena were the villain all along?')
        s2 = self.desk.propose('skeleton')
        self.assertNotEqual(s2, s1)
        self.reopen()
        self.assertEqual(self.desk.governing('skeleton')['revision_id'], s1)
        with self.assertRaises(Refused) as stale:
            self.desk.adopt(s2, expected_governing=None)
        self.assertEqual(stale.exception.code, 'stale_pointer')
        self.assertEqual(self.desk.governing('skeleton')['revision_id'], s1)
        self.assertEqual(self.desk.canon(), [])

    def test_bulk_drafting_requires_adopted_skeleton_and_arc(self):
        self.desk.save_direction('skeleton', SKELETON)
        with self.assertRaises(Refused) as missing:
            self.desk.commission_arc(slots=(1, 3), progression='provisional_chain')
        self.assertEqual(missing.exception.code, 'direction_missing')
        self.assertEqual(self.provider.calls, [])


class LinkedDraftsTest(V1Case):
    def test_linked_drafts_are_sequential_from_exact_selected_predecessors(self):
        selections = self.drafted()
        self.assertEqual(len(self.desk.artifacts('episode')), 3)
        for n, sel in enumerate(selections, 1):
            self.assertEqual(sel['selected_by'], 'commission')
            job = self.desk.job_for(sel['revision_id'])
            expected = [(s['revision_id'], s['sha256']) for s in selections[:n - 1]]
            self.assertEqual(job['predecessors'], expected)
        texts = [self.desk.revision(s['revision_id'])['text'] for s in selections]
        self.assertEqual(len(set(texts)), 3)
        # The governing skeleton reached every draft request; chat did not.
        self.assertTrue(all(SKELETON['spine'] in c['prompt'] for c in self.provider.calls if c['recipe'] == 'sequential_draft'))
        self.assertEqual(self.desk.canon(), [])

    def test_provider_is_deterministic_and_alternatives_are_distinct(self):
        a = ScriptedProvider().draft_text('seed', 1, variant=0)
        self.assertEqual(a, ScriptedProvider().draft_text('seed', 1, variant=0))
        self.assertNotEqual(a, ScriptedProvider().draft_text('seed', 1, variant=1))
        words = len(a.split())
        self.assertTrue(120 <= words <= 700, words)


if __name__ == '__main__':
    unittest.main()
