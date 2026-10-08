"""V1 rewrite/undo/impact (J5-J6) and accept/memory/continue (J7-J9), plus style side journey."""
import sqlite3
import unittest

from serial_story.v1.desk import Refused
from serial_story.v1.provider import ScriptedProvider
from tests.test_v1_slice import V1Case


class RewriteUndoTest(V1Case):
    def setUp(self):
        super().setUp()
        self.e1 = self.drafted()[0]
        self.base = self.desk.revision(self.e1['revision_id'])

    def rewrite_first(self):
        target = self.base['blocks'][0]
        return self.desk.request_rewrite(1, block_id=target['block_id'], expected_sha256=target['sha256'],
                                         intent='polish', reason='tighten the rhythm')

    def test_rewrite_is_a_candidate_and_apply_changes_only_the_target_block(self):
        candidate = self.rewrite_first()
        self.assertEqual(self.desk.selection(1)['revision_id'], self.base['revision_id'])
        applied = self.desk.apply_candidate(candidate, expected_cas=self.e1['cas'])
        after = self.desk.revision(self.desk.selection(1)['revision_id'])
        self.assertEqual(after['revision_id'], applied['revision_id'])
        self.assertNotEqual(after['blocks'][0]['text'], self.base['blocks'][0]['text'])
        self.assertEqual([(b['block_id'], b['text']) for b in after['blocks'][1:]],
                         [(b['block_id'], b['text']) for b in self.base['blocks'][1:]])
        self.assertEqual(self.desk.revision(self.base['revision_id'])['text'], self.base['text'])

    def test_rewrite_targeting_stale_text_is_rejected_not_applied_to_new_version(self):
        with self.assertRaises(Refused) as wrong:
            self.desk.request_rewrite(1, block_id=self.base['blocks'][0]['block_id'], expected_sha256='0' * 64,
                                      intent='polish', reason='tighten')
        self.assertEqual(wrong.exception.code, 'invalid_range')
        candidate = self.rewrite_first()
        blocks = [(b['block_id'], b['text']) for b in self.base['blocks']]
        blocks[0] = (blocks[0][0], 'Leena wrote this opening herself.')
        self.desk.save_revision(1, base_revision_id=self.base['revision_id'], blocks=blocks, expected_cas=self.e1['cas'])
        now = self.desk.selection(1)
        with self.assertRaises(Refused) as stale:
            self.desk.apply_candidate(candidate, expected_cas=now['cas'])
        self.assertEqual(stale.exception.code, 'overlap')
        self.assertEqual(set(stale.exception.detail), {'before', 'ai', 'now'})
        self.assertEqual(self.desk.selection(1)['revision_id'], now['revision_id'])
        with self.assertRaises(Refused) as cas:
            self.desk.save_revision(1, base_revision_id=self.base['revision_id'], blocks=blocks, expected_cas=self.e1['cas'])
        self.assertEqual(cas.exception.code, 'stale_pointer')

    def test_undo_restores_a_real_prior_block_keeps_hand_edit_and_redo_reuses_prose(self):
        applied = self.desk.apply_candidate(self.rewrite_first(), expected_cas=self.e1['cas'])
        mid = self.desk.revision(applied['revision_id'])
        blocks = [(b['block_id'], b['text']) for b in mid['blocks']]
        blocks[-1] = (blocks[-1][0], 'A last paragraph written by hand.')
        self.desk.save_revision(1, base_revision_id=mid['revision_id'], blocks=blocks, expected_cas=self.desk.selection(1)['cas'])
        calls = len(self.provider.calls)
        self.desk.revert_event(applied['event_id'])
        self.reopen()
        undone = self.desk.revision(self.desk.selection(1)['revision_id'])
        self.assertEqual(undone['blocks'][0]['text'], self.base['blocks'][0]['text'])
        self.assertEqual(undone['blocks'][-1]['text'], 'A last paragraph written by hand.')
        redo = self.desk.redo_event(applied['event_id'])
        again = self.desk.revision(redo['revision_id'])
        self.assertEqual(again['blocks'][0]['text'], mid['blocks'][0]['text'])
        self.assertEqual(len(self.provider.calls), calls)

    def test_undo_refuses_when_the_target_block_changed_since(self):
        applied = self.desk.apply_candidate(self.rewrite_first(), expected_cas=self.e1['cas'])
        mid = self.desk.revision(applied['revision_id'])
        blocks = [(b['block_id'], b['text']) for b in mid['blocks']]
        blocks[0] = (blocks[0][0], 'Edited after the rewrite.')
        self.desk.save_revision(1, base_revision_id=mid['revision_id'], blocks=blocks, expected_cas=self.desk.selection(1)['cas'])
        with self.assertRaises(Refused) as overlap:
            self.desk.revert_event(applied['event_id'])
        self.assertEqual(overlap.exception.code, 'overlap')

    def test_upstream_edit_flags_downstream_before_it_is_applied_and_blocks_acceptance(self):
        self.assertEqual(self.desk.impact_preview(1), [2, 3])
        blocks = [(b['block_id'], b['text']) for b in self.base['blocks']]
        blocks[0] = (blocks[0][0], 'Leena loses her mother\'s face instead of a street name.')
        saved = self.desk.save_revision(1, base_revision_id=self.base['revision_id'], blocks=blocks, expected_cas=self.e1['cas'])
        self.assertEqual(saved['flagged'], [2, 3])
        episodes = [self.desk.selection(n) for n in (1, 2, 3)]
        with self.assertRaises(Refused) as conflict:
            self.desk.accept_prefix([(n, s['revision_id'], s['sha256']) for n, s in enumerate(episodes, 1)], expected_canon_seq=0)
        self.assertEqual(conflict.exception.code, 'open_conflict')
        self.assertEqual(self.desk.canon(), [])
        self.desk.revalidate(2)
        self.desk.revalidate(3)
        self.desk.accept_prefix([(n, s['revision_id'], s['sha256']) for n, s in enumerate(episodes, 1)], expected_canon_seq=0)
        self.assertEqual(len(self.desk.canon()), 3)


class AcceptMemoryContinueTest(V1Case):
    def group(self):
        return [(n, s['revision_id'], s['sha256']) for n, s in enumerate((self.desk.selection(n) for n in (1, 2, 3)), 1)]

    def test_accept_prefix_stores_exact_text_and_refuses_holes_stale_hashes_and_raw_edits(self):
        self.drafted()
        group = self.group()
        with self.assertRaises(Refused) as hole:
            self.desk.accept_prefix(group[1:], expected_canon_seq=0)
        self.assertEqual(hole.exception.code, 'prefix_invalid')
        with self.assertRaises(Refused) as stale:
            self.desk.accept_prefix([group[0], (2, group[1][1], '0' * 64)], expected_canon_seq=0)
        self.assertEqual(stale.exception.code, 'prefix_invalid')
        self.assertEqual(self.desk.canon(), [])
        receipt = self.desk.accept_prefix(group, expected_canon_seq=0)
        self.assertIn('warnings', receipt)
        for row, (n, revision_id, digest) in zip(self.desk.canon(), group):
            self.assertEqual(row['text'], self.desk.revision(revision_id)['text'])
            self.assertEqual(row['sha256'], digest)
        with self.assertRaises(sqlite3.IntegrityError):
            self.desk.connection.execute("UPDATE v1_canon SET text='tampered' WHERE ordinal=1")
        with self.assertRaises(Refused):
            self.desk.accept_prefix(group, expected_canon_seq=0)

    def test_awaiting_previews_stay_visible_between_approve_and_save(self):
        self.drafted()
        self.desk.read_provisional(1)
        proposed = [c['claim_id'] for c in self.desk.memory()['provisional']]
        self.assertTrue(proposed)
        self.assertEqual(self.desk.memory()['awaiting'], [])
        self.desk.accept_prefix(self.group(), expected_canon_seq=0)
        memory = self.desk.memory()
        self.assertEqual(memory['provisional'], [])
        self.assertEqual([c['claim_id'] for c in memory['awaiting']], proposed)
        self.desk.update_memory()
        self.assertEqual(self.desk.memory()['awaiting'], [], 'saved facts are no longer awaiting')

    def test_provisional_and_accepted_memory_are_separate_and_corrections_supersede(self):
        self.drafted()
        self.desk.read_provisional(1)
        memory = self.desk.memory()
        self.assertTrue(memory['provisional'])
        self.assertEqual(memory['accepted'], [])
        self.desk.accept_prefix(self.group(), expected_canon_seq=0)
        self.assertEqual(self.desk.memory()['accepted'], [], 'memory waits for explicit authority')
        self.desk.update_memory()
        accepted = self.desk.memory()['accepted']
        self.assertTrue(accepted)
        for claim in accepted:
            block = next(b for b in self.desk.revision(claim['revision_id'])['blocks'] if b['block_id'] == claim['block_id'])
            self.assertEqual(block['text'][claim['start']:claim['end']], claim['quote'])
        self.assertEqual(self.desk.memory()['provisional'], [], 'accepted episodes are no longer previews')
        old = accepted[0]
        corrected = self.desk.interpret(old['claim_id'], kind='testimony', speaker='witness', world_validity='unknown',
                                        note='attributed testimony; survival unknown')
        self.assertNotIn(old['claim_id'], [c['claim_id'] for c in self.desk.memory()['accepted']])
        history = self.desk.claim_history(corrected)
        self.assertEqual([c['claim_id'] for c in history], [corrected, old['claim_id']])
        self.assertEqual(history[1]['standing'], 'superseded')
        with self.assertRaises(Refused):
            self.desk.interpret(old['claim_id'], kind='testimony', speaker=None, world_validity='unknown', note='')
        self.assertTrue(all(c['narrative_ordinal'] <= 2 for c in self.desk.memory(boundary=2)['accepted']))
        self.assertEqual(self.desk.canon()[0]['text'], self.desk.revision(self.desk.canon()[0]['revision_id'])['text'])

    def test_continue_uses_exact_text_fallback_until_memory_is_complete(self):
        self.drafted()
        self.desk.accept_prefix(self.group(), expected_canon_seq=0)
        receipt = self.desk.prepare_context(boundary=3)
        self.assertEqual(receipt['mode'], 'exact_text')
        self.assertEqual([i['ordinal'] for i in receipt['items']], [1, 2, 3])
        self.assertEqual(receipt['items'][0]['text'], self.desk.canon()[0]['text'])
        self.desk.update_memory()
        self.assertEqual(self.desk.prepare_context(boundary=3)['mode'], 'indexed')


class UnresolvedAndStyleTest(V1Case):
    def test_unresolved_request_blocks_continuation_until_resolved(self):
        self.provider.fail_recipes.add('sequential_draft')
        self.adopt_direction()
        commission = self.desk.commission_arc(slots=(1, 3))
        self.assertEqual((commission['status'], commission['pause_reason']), ('paused', 'accounting_uncertain'))
        self.assertIsNone(self.desk.selection(1))
        for attempt in (lambda: self.desk.commission_arc(slots=(1, 3)),
                        lambda: self.desk.resume_commission(commission['commission_id']),
                        lambda: self.desk.prepare_context(boundary=1)):
            with self.assertRaises(Refused) as blocked:
                attempt()
            self.assertEqual(blocked.exception.code, 'accounting_uncertain')
        sent = len(self.provider.calls)
        self.assertEqual(sent, 1, 'never retried automatically')
        self.provider.fail_recipes.clear()
        self.desk.resolve_uncertain(self.desk.uncertain_jobs()[0], 'provider receipt unavailable')
        self.assertEqual(self.desk.resume_commission(commission['commission_id'])['status'], 'complete')

    def test_style_is_learned_only_from_chosen_evidence_and_used_only_after_adoption(self):
        e1 = self.drafted()[0]
        base = self.desk.revision(e1['revision_id'])
        with self.assertRaises(Refused) as generated:
            self.desk.propose_style('Short declaratives.', evidence=[{'kind': 'generated_acceptance', 'revision_id': base['revision_id']}])
        self.assertEqual(generated.exception.code, 'invalid_evidence')
        blocks = [(b['block_id'], b['text']) for b in base['blocks']]
        blocks[1] = (blocks[1][0], 'She left. She did not look back.')
        saved = self.desk.save_revision(1, base_revision_id=base['revision_id'], blocks=blocks, expected_cas=e1['cas'])
        style = self.desk.propose_style('Leena POV: short declaratives.', evidence=[{'kind': 'human_edit', 'event_id': saved['event_id']}])
        shown = self.desk.style(style)
        self.assertEqual(shown['status'], 'proposed')
        self.assertEqual(shown['evidence'][0]['after_text'], 'She left. She did not look back.')
        self.assertNotEqual(shown['evidence'][0]['before_text'], shown['evidence'][0]['after_text'])
        self.desk.revalidate(2)
        self.desk.revalidate(3)
        self.desk.redraft(3)
        self.assertNotIn('short declaratives', self.provider.calls[-1]['prompt'])
        self.desk.adopt_style(style)
        self.desk.redraft(3)
        self.assertIn('Leena POV: short declaratives.', self.provider.calls[-1]['prompt'])


class FullJourneyTest(V1Case):
    def test_adopt_draft_rewrite_undo_accept_inspect_memory_continue(self):
        e1 = self.drafted()[0]
        base = self.desk.revision(e1['revision_id'])
        target = base['blocks'][0]
        applied = self.desk.apply_candidate(
            self.desk.request_rewrite(1, block_id=target['block_id'], expected_sha256=target['sha256'], intent='polish', reason='rhythm'),
            expected_cas=e1['cas'])
        self.desk.revert_event(applied['event_id'])
        self.assertEqual(self.desk.revision(self.desk.selection(1)['revision_id'])['text'], base['text'])
        for n in (2, 3):
            self.desk.revalidate(n)
        group = [(n, self.desk.selection(n)['revision_id'], self.desk.selection(n)['sha256']) for n in (1, 2, 3)]
        self.desk.accept_prefix(group, expected_canon_seq=0)
        self.desk.update_memory()
        self.assertTrue(self.desk.memory()['accepted'])
        receipt = self.desk.prepare_context(boundary=3)
        self.assertEqual(receipt['mode'], 'indexed')
        self.assertEqual(receipt['governing']['skeleton'], self.desk.governing('skeleton')['revision_id'])


if __name__ == '__main__':
    unittest.main()
