"""Regression tests for approval, stale results and provider recovery boundaries."""
import threading
import unittest
from pathlib import Path

from serial_story.v1.api import claim_database
from serial_story.v1.desk import Desk, Refused
from serial_story.v1.provider import GenerationResult, NotSent, ScriptedProvider
from tests.test_v1_slice import INTENTIONS, SKELETON, V1Case

SKELETON_PREMISE = SKELETON['premise']


def group(desk, ordinals):
    return [(n, desk.selection(n)['revision_id'], desk.selection(n)['sha256']) for n in ordinals]


def edit_first_paragraph(desk, ordinal, text):
    sel = desk.selection(ordinal)
    blocks = [(b['block_id'], b['text']) for b in desk.revision(sel['revision_id'])['blocks']]
    blocks[0] = (blocks[0][0], text)
    return desk.save_revision(ordinal, base_revision_id=sel['revision_id'], blocks=blocks, expected_cas=sel['cas'])


class ApprovalRaceTest(V1Case):
    def test_a_replacement_that_arrives_after_approval_is_set_aside_and_the_reader_shows_approved_words(self):
        self.drafted()
        edit_first_paragraph(self.desk, 1, 'Leena changed this opening line herself.')
        self.desk.accept_prefix(group(self.desk, (1,)), expected_canon_seq=0)
        self.desk.revalidate(2)
        approved = {}

        def approve_while_writing(request):
            if request.recipe == 'sequential_draft' and request.params.get('ordinal') == 2 and not approved:
                sel = self.desk.selection(2)
                approved['text'] = self.desk.revision(sel['revision_id'])['text']
                self.desk.accept_prefix(group(self.desk, (2,)), expected_canon_seq=1)

        self.provider.during_exchange = approve_while_writing
        run = self.desk.commission_arc(slots=(2, 2))
        self.assertEqual(run['status'], 'paused')
        self.assertEqual(run['pause_reason'], 'target_accepted')
        canon2 = next(r for r in self.desk.canon() if r['ordinal'] == 2)
        self.assertEqual(canon2['text'], approved['text'])
        episode = next(e for e in self.desk.snapshot()['episodes'] if e['ordinal'] == 2)
        self.assertTrue(episode['accepted'])
        self.assertEqual(episode['text'], approved['text'], 'an approved episode is shown from canon, never from a later draft')
        self.assertEqual(self.desk.selection(2)['revision_id'], canon2['revision_id'])
        self.assertEqual([a['detached_reason'] for a in episode['alternatives']][-1], 'target_accepted')

    def test_the_snapshot_reads_approved_text_from_canon_even_if_the_selection_pointer_moves(self):
        self.drafted()
        self.desk.accept_prefix(group(self.desk, (1,)), expected_canon_seq=0)
        canon1 = self.desk.canon()[0]
        other = self.desk.redraft(1)
        sel = self.desk.selection(1)
        self.desk.connection.execute('UPDATE v1_selection SET revision_id=? WHERE artifact_id=?', (other, sel['artifact_id']))
        episode = self.desk.snapshot()['episodes'][0]
        self.assertEqual(episode['text'], canon1['text'])


class FinishedRunTest(V1Case):
    def drafts_for(self, ordinal):
        return [c for c in self.provider.calls if c['recipe'] == 'sequential_draft' and c['params'].get('ordinal') == ordinal]

    def test_a_finished_run_cannot_be_resumed_after_the_author_edits(self):
        self.adopt_direction()
        run = self.desk.commission_arc(slots=(1, 3))
        self.assertEqual(run['status'], 'complete')
        edit_first_paragraph(self.desk, 2, 'Darin read the page twice.')
        kept = self.desk.selection(2)['revision_id']
        sent = len(self.provider.calls)
        with self.assertRaises(Refused) as closed:
            self.desk.resume_commission(run['commission_id'])
        self.assertEqual(closed.exception.code, 'commission_closed')
        self.assertEqual(len(self.provider.calls), sent)
        self.assertEqual(self.desk.selection(2)['revision_id'], kept)

    def test_a_new_run_never_overwrites_an_episode_the_author_has_taken_over(self):
        self.adopt_direction()
        self.desk.commission_arc(slots=(1, 3))
        edit_first_paragraph(self.desk, 2, 'Darin read the page twice.')
        kept = self.desk.selection(2)['revision_id']
        before = len(self.drafts_for(2))
        self.desk.revalidate(3)
        self.desk.commission_arc(slots=(1, 3))
        self.assertEqual(self.desk.selection(2)['revision_id'], kept)
        self.assertEqual(len(self.drafts_for(2)), before)


class HandEditDependencyTest(V1Case):
    def test_editing_episode_one_flags_a_hand_edited_episode_two_and_blocks_approval(self):
        self.drafted()
        edit_first_paragraph(self.desk, 2, 'Darin read the page twice.')
        edit_first_paragraph(self.desk, 1, 'Leena began again, differently.')
        flagged = {e['ordinal']: e['open_impacts'] for e in self.desk.snapshot()['episodes']}
        self.assertGreater(flagged[2], 0, 'episode 2 was drafted from episode 1 even though the author edited it')
        self.assertGreater(flagged[3], 0)
        with self.assertRaises(Refused) as blocked:
            self.desk.accept_prefix(group(self.desk, (1, 2)), expected_canon_seq=0)
        self.assertEqual(blocked.exception.code, 'open_conflict')


class OrderedUndoTest(V1Case):
    def test_undoing_a_deleted_paragraph_puts_it_back_in_place_with_its_own_identity(self):
        self.drafted()
        sel = self.desk.selection(1)
        original = [(b['block_id'], b['text']) for b in self.desk.revision(sel['revision_id'])['blocks']]
        self.assertGreater(len(original), 2)
        saved = self.desk.save_revision(1, base_revision_id=sel['revision_id'], blocks=original[1:], expected_cas=sel['cas'])
        self.desk.revert_event(saved['event_id'])
        restored = [(b['block_id'], b['text']) for b in self.desk.revision(self.desk.selection(1)['revision_id'])['blocks']]
        self.assertEqual(restored, original)
        self.desk.redo_event(saved['event_id'])
        again = [(b['block_id'], b['text']) for b in self.desk.revision(self.desk.selection(1)['revision_id'])['blocks']]
        self.assertEqual(again, original[1:])

    def test_undoing_a_deleted_middle_paragraph_restores_its_position(self):
        self.drafted()
        sel = self.desk.selection(1)
        original = [(b['block_id'], b['text']) for b in self.desk.revision(sel['revision_id'])['blocks']]
        without = original[:2] + original[3:]
        saved = self.desk.save_revision(1, base_revision_id=sel['revision_id'], blocks=without, expected_cas=sel['cas'])
        self.desk.revert_event(saved['event_id'])
        restored = [(b['block_id'], b['text']) for b in self.desk.revision(self.desk.selection(1)['revision_id'])['blocks']]
        self.assertEqual(restored, original)


class ShorterPlanTest(V1Case):
    def test_a_plan_cannot_drop_episodes_that_are_already_approved(self):
        _, arc = self.drafted() and self.desk.governing('skeleton')['revision_id'], self.desk.governing('arc')['revision_id']
        self.desk.accept_prefix(group(self.desk, (1, 2)), expected_canon_seq=0)
        short = self.desk.save_direction('arc', {'purpose': 'shorter', 'end_state': 'none', 'intentions': INTENTIONS[:1]})
        with self.assertRaises(Refused) as refused:
            self.desk.adopt(short, expected_governing=arc)
        self.assertEqual(refused.exception.code, 'plan_below_approved')
        self.assertEqual(self.desk.governing('arc')['revision_id'], arc)

    def test_drafting_a_slot_outside_the_plan_is_a_named_refusal(self):
        self.adopt_direction()
        with self.assertRaises(Refused) as refused:
            self.desk.commission_arc(slots=(1, 5))
        self.assertEqual(refused.exception.code, 'invalid_slots')
        self.assertEqual(self.provider.calls, [])


class ConcurrentSaveTest(V1Case):
    def test_two_saves_at_once_import_each_episode_once(self):
        self.drafted()
        self.desk.accept_prefix(group(self.desk, (1,)), expected_canon_seq=0)
        barrier = threading.Barrier(2, timeout=15)

        def meet(request):
            if request.recipe == 'promotion':
                barrier.wait()

        provider = ScriptedProvider(during_exchange=meet)
        failures = []

        def save():
            desk = Desk.open(self.path, provider=provider)
            try:
                desk.update_memory()
            except Exception as problem:  # surfaced below so a thread error cannot pass silently
                failures.append(repr(problem))
            finally:
                desk.close()

        threads = [threading.Thread(target=save) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(30)
        self.assertEqual(failures, [])
        db = self.desk.connection
        self.assertEqual(db.execute('SELECT count(DISTINCT extraction_id) FROM v1_claim').fetchone()[0], 1)
        first = db.execute('SELECT extraction_id FROM v1_claim LIMIT 1').fetchone()[0]
        self.assertEqual(db.execute('SELECT count(*) FROM v1_claim').fetchone()[0],
                         db.execute('SELECT count(*) FROM v1_claim WHERE extraction_id=?', (first,)).fetchone()[0])


class ProviderOutcomeTest(V1Case):
    def sent(self):
        return [c for c in self.provider.calls if c['recipe'] == 'sequential_draft']

    def test_the_draft_request_carries_the_public_premise(self):
        self.drafted()
        system = self.sent()[0]['params']['messages'][0]['content']
        self.assertIn(SKELETON_PREMISE, system)

    def test_a_request_that_was_never_sent_pauses_the_run_without_an_unknown_charge(self):
        self.adopt_direction()

        def refuse(request):
            if request.recipe == 'sequential_draft':
                raise NotSent('limit reached')

        self.provider.during_exchange = refuse
        run = self.desk.commission_arc(slots=(1, 2))
        self.assertEqual((run['status'], run['pause_reason']), ('paused', 'not_sent'))
        self.assertEqual(self.desk.uncertain_jobs(), [])
        with self.assertRaises(NotSent):
            self.desk.redraft(1)
        self.assertEqual(self.desk.uncertain_jobs(), [])

    def test_a_partial_draft_is_set_aside_and_never_selected(self):
        self.adopt_direction()
        real = self.provider.generate

        def partial(request):
            result = real(request)
            return GenerationResult(result.text, completeness='partial') if request.recipe == 'sequential_draft' else result

        self.desk.provider = type('Partial', (), {'generate': staticmethod(partial)})()
        run = self.desk.commission_arc(slots=(1, 2))
        self.assertEqual((run['status'], run['pause_reason']), ('paused', 'incomplete'))
        self.assertIsNone(self.desk.selection(1))
        episode = self.desk.snapshot()['episodes'][0]
        self.assertEqual(episode['alternatives'][0]['detached_reason'], 'incomplete')


class CorrectionVocabularyTest(V1Case):
    def first_claim(self):
        self.drafted()
        self.desk.accept_prefix(group(self.desk, (1,)), expected_canon_seq=0)
        self.desk.update_memory()
        return self.desk.connection.execute("SELECT claim_id FROM v1_claim ORDER BY rowid LIMIT 1").fetchone()[0]

    def test_a_correction_must_use_the_same_vocabulary_as_extraction(self):
        claim = self.first_claim()
        bad = [dict(kind='gossip', speaker=None, world_validity='unknown'),
               dict(kind='event', speaker=None, world_validity='maybe'),
               dict(kind='event', speaker=7, world_validity='unknown'),
               dict(kind='belief', speaker=None, world_validity='unknown', holder=None),
               dict(kind='testimony', speaker='', world_validity='unknown')]
        for fields in bad:
            with self.subTest(fields):
                with self.assertRaises(Refused) as refused:
                    self.desk.interpret(claim, note='fix', **fields)
                self.assertEqual(refused.exception.code, 'invalid_claim')
        self.assertEqual(self.desk.connection.execute("SELECT count(*) FROM v1_claim WHERE prior_claim_id IS NOT NULL").fetchone()[0], 0)

    def test_a_valid_correction_still_supersedes_the_original(self):
        claim = self.first_claim()
        new = self.desk.interpret(claim, kind='belief', speaker='Leena', holder='Leena', world_validity='false_in_story', note='fix')
        self.assertEqual(self.desk.claim_history(new)[1]['standing'], 'superseded')


class DraftInspectionTest(V1Case):
    def test_it_shows_what_the_writer_was_sent_and_nothing_private(self):
        s1 = self.desk.save_direction('skeleton', {**SKELETON, 'private': 'THE-HIDDEN-TRUTH'})
        self.desk.adopt(s1, expected_governing=None)
        a1 = self.desk.save_direction('arc', {'purpose': 'make Darin suspect a manufactured witness', 'end_state': 'x',
                                              'intentions': INTENTIONS, 'private_intentions': ['', 'KEEP-THIS-BACK', '']})
        self.desk.adopt(a1, expected_governing=None)
        self.desk.commission_arc(slots=(1, 3))
        shown = self.desk.draft_inspection(3)
        kinds = [p['kind'] for p in shown['parts']]
        self.assertEqual(kinds, ['direction', 'episode', 'episode', 'job'])
        direction = shown['parts'][0]['text']
        self.assertIn(SKELETON_PREMISE, direction)
        self.assertIn(SKELETON['spine'], direction)
        everything = ' '.join(p.get('text', '') for p in shown['parts'])
        self.assertNotIn('THE-HIDDEN-TRUTH', everything)
        self.assertNotIn('KEEP-THIS-BACK', everything)
        self.assertTrue(all(p['words'] > 0 for p in shown['parts'] if p['kind'] == 'episode'))
        self.assertEqual(shown['fingerprint'], self.desk.connection.execute(
            'SELECT request_sha256 FROM v1_job ORDER BY rowid DESC LIMIT 1').fetchone()[0])

    def test_an_episode_never_drafted_has_nothing_to_show(self):
        self.adopt_direction()
        self.assertIsNone(self.desk.draft_inspection(1)['job'])


class ChatScopeTest(V1Case):
    def sent(self, target, text='Is this working?'):
        out = self.desk.converse(target=target, text=text)
        call = [c for c in self.provider.calls if c['recipe'] == 'converse'][-1]
        return out, call['params']['messages']

    def setUp(self):
        super().setUp()
        s1 = self.desk.save_direction('skeleton', {**SKELETON, 'private': 'THE-HIDDEN-TRUTH'})
        self.desk.adopt(s1, expected_governing=None)
        a1 = self.desk.save_direction('arc', {'purpose': 'make Darin suspect a manufactured witness', 'end_state': 'x',
                                              'intentions': INTENTIONS, 'private_intentions': ['', 'KEEP-THIS-BACK', '']})
        self.desk.adopt(a1, expected_governing=None)
        self.desk.commission_arc(slots=(1, 2))

    def test_a_later_message_carries_the_earlier_conversation(self):
        first, _ = self.sent('story', 'Give me one idea for the second arc.')
        _, msgs = self.sent('story', 'What was that?')
        turns = [(m['role'], m['content']) for m in msgs if m['role'] != 'system'][-3:]
        self.assertEqual([r for r, _ in turns], ['user', 'assistant', 'user'])
        self.assertEqual(turns[0][1], 'Give me one idea for the second arc.')
        self.assertEqual(turns[1][1], first['text'])
        self.assertEqual(turns[2][1], 'What was that?')

    def test_only_the_last_few_turns_are_carried(self):
        for n in range(8):
            self.desk.converse(target='story', text=f'question number {n}')
        _, msgs = self.sent('story', 'the newest one')
        body = ' '.join(m['content'] for m in msgs)
        self.assertNotIn('question number 0', body)
        self.assertIn('question number 7', body)
        roles = [m['role'] for m in msgs[2:]]  # after the system rules and the story context
        self.assertTrue(all(a != b for a, b in zip(roles, roles[1:])), 'roles alternate')
        self.assertEqual(roles[-1], 'user')

    def test_the_editor_is_asked_to_think_with_the_author_not_to_stop_at_four_sentences(self):
        _, msgs = self.sent('story')
        system = msgs[0]['content']
        self.assertNotIn('four plain sentences', system)
        self.assertIn('the author decides', system)
        self.assertIn('say when you are guessing', system)
        self.assertIn('no markdown', system)
    def test_each_scope_sends_what_it_says_and_nothing_private(self):
        out, msgs = self.sent('skeleton')
        body = ' '.join(m['content'] for m in msgs)
        self.assertIn(SKELETON['spine'], body)
        self.assertNotIn(INTENTIONS[0], body)
        self.assertEqual(out['read'], ['premise and spine'])

        out, msgs = self.sent('arc')
        body = ' '.join(m['content'] for m in msgs)
        self.assertIn(INTENTIONS[2], body)
        self.assertEqual(out['read'], ['premise and spine', 'the plan, one line per episode'])

        out, msgs = self.sent('story')
        self.assertNotIn('APPROVED EPISODES', ' '.join(m['content'] for m in msgs), 'nothing is approved yet')
        self.assertEqual(out['read'], ['premise and spine', 'the plan, one line per episode'])

        out, msgs = self.sent('episode:2')
        body = ' '.join(m['content'] for m in msgs)
        draft = self.desk.revision(self.desk.selection(2)['revision_id'])['text']
        self.assertIn(draft[:60], body)
        self.assertIn(INTENTIONS[1], body)
        self.assertTrue(out['read'][-1].startswith('episode 2, current draft ('))
        for _, sent in [(0, body)]:
            self.assertNotIn('THE-HIDDEN-TRUTH', sent)
            self.assertNotIn('KEEP-THIS-BACK', sent)

    def test_an_approved_episode_is_sent_from_canon(self):
        self.desk.accept_prefix(group(self.desk, (1,)), expected_canon_seq=0)
        out, msgs = self.sent('episode:1')
        self.assertTrue(out['read'][-1].startswith('episode 1, approved ('))

    def test_the_whole_story_scope_adds_approved_episodes_and_no_drafts(self):
        self.desk.accept_prefix(group(self.desk, (1,)), expected_canon_seq=0)
        out, msgs = self.sent('story')
        body = ' '.join(m['content'] for m in msgs)
        approved = self.desk.canon()[0]['text']
        self.assertIn(approved[:60], body)
        draft2 = self.desk.revision(self.desk.selection(2)['revision_id'])['text']
        self.assertNotIn(draft2[:60], body)
        self.assertTrue(out['read'][-1].startswith('approved episode 1 ('))

    def test_the_author_message_comes_last_and_an_unknown_scope_sends_only_the_storyline(self):
        out, msgs = self.sent('nonsense:7', 'hello')
        self.assertEqual(msgs[-1], {'role': 'user', 'content': 'hello'})
        self.assertEqual(out['read'], ['premise and spine'])
        self.assertNotIn(INTENTIONS[0], ' '.join(m['content'] for m in msgs))

    def fresh_desk(self):
        desk = Desk.create(Path(self.tmp.name) / 'fresh.db', provider=self.provider)
        self.addCleanup(desk.close)
        return desk

    def test_every_scope_carries_the_storyline_even_before_it_is_adopted(self):
        for target in ('story', 'skeleton', 'arc', 'episode:1', 'anything'):
            out, msgs = self.sent(target)
            self.assertIn(SKELETON['spine'], ' '.join(m['content'] for m in msgs), target)
            self.assertIn('premise and spine', out['read'], target)

    def test_a_saved_but_not_adopted_storyline_is_used_and_labelled(self):
        fresh = self.fresh_desk()
        fresh.save_direction('skeleton', {**SKELETON, 'spine': 'A newer spine the author has only saved.'})
        messages, labels, _ = fresh.chat_context('story')
        self.assertIn('A newer spine the author has only saved.', ' '.join(m['content'] for m in messages))
        self.assertEqual(labels, ['premise and spine (saved, not adopted yet)'])
        self.assertEqual(fresh.chat_context('story')[0][0]['role'], 'system')

    def test_the_latest_saved_storyline_is_never_the_private_note(self):
        fresh = self.fresh_desk()
        fresh.save_direction('skeleton', {**SKELETON, 'private': 'ONLY-FOR-ME'})
        messages, _, _ = fresh.chat_context('story')
        self.assertNotIn('ONLY-FOR-ME', ' '.join(m['content'] for m in messages))


class SecretRoutesTest(V1Case):
    def setUp(self):
        super().setUp()
        self.drafted()
        self.desk.add_secret(label='Orchid', body='The orchid key opens the vault.', canaries=['OrchidKey'], reveal_ordinal=5)

    def asks(self):
        return [c for c in self.provider.calls if c['recipe'] in ('converse', 'polish_rewrite', 'story_rewrite')]

    def test_chat_naming_a_protected_word_is_refused_before_anything_is_sent(self):
        with self.assertRaises(Refused) as refused:
            self.desk.converse(target='story', text='What if the OrchidKey were hidden in the ledger?')
        self.assertEqual(refused.exception.code, 'secret_in_message')
        self.assertEqual(self.asks(), [])
        self.assertEqual(self.desk.connection.execute('SELECT count(*) FROM v1_message').fetchone()[0], 0)

    def test_a_rewrite_reason_naming_a_protected_word_is_refused(self):
        sel = self.desk.selection(1)
        block = self.desk.revision(sel['revision_id'])['blocks'][0]
        with self.assertRaises(Refused) as refused:
            self.desk.request_rewrite(1, block_id=block['block_id'], expected_sha256=block['sha256'], intent='polish', reason='mention the orchidkey')
        self.assertEqual(refused.exception.code, 'secret_in_message')
        self.assertEqual(self.asks(), [])

    def test_spelling_tricks_do_not_get_past_the_gate(self):
        tricks = ['Orchid\u200bKey', 'Orchid<b></b>Key', '\uff2f\uff52\uff43\uff48\uff49\uff44\uff2b\uff45\uff59', 'ORCHIDKEY', 'Orchid\u2060Key']
        for text in tricks:
            with self.subTest(text):
                with self.assertRaises(Refused) as refused:
                    self.desk.converse(target='story', text=text)
                self.assertEqual(refused.exception.code, 'secret_in_message')

    def test_ordinary_chat_still_works_and_the_secret_is_free_once_revealed(self):
        self.assertTrue(self.desk.converse(target='story', text='What makes a good ending?')['text'])
        self.desk.reveal_secret(self.desk.connection.execute('SELECT secret_id FROM v1_secret').fetchone()[0], 1)
        self.assertTrue(self.desk.converse(target='story', text='Mention the OrchidKey now.')['text'])


class OrphanRecoveryTest(V1Case):
    def interrupted_run(self):
        self.adopt_direction()

        def die(request):
            if request.recipe == 'sequential_draft':
                raise KeyboardInterrupt  # stands in for the process being killed mid-exchange

        self.provider.during_exchange = die
        with self.assertRaises(KeyboardInterrupt):
            self.desk.commission_arc(slots=(1, 2))
        self.provider.during_exchange = None
        return self.desk.connection.execute("SELECT commission_id FROM v1_commission").fetchone()[0]

    def claim(self):
        lease = claim_database(self.path, ScriptedProvider())
        if lease is not None:
            self.addCleanup(lease.close)
        return lease

    def test_a_restart_turns_the_orphaned_request_into_an_unverified_one_and_pauses_the_run(self):
        commission_id = self.interrupted_run()
        self.assertEqual(self.desk.connection.execute("SELECT state FROM v1_job").fetchone()[0], 'sent')
        self.assertIsNotNone(self.claim())
        self.assertEqual(len(self.desk.uncertain_jobs()), 1)
        run = self.desk.commission(commission_id)
        self.assertEqual((run['status'], run['pause_reason']), ('paused', 'accounting_uncertain'))
        calls = len([c for c in self.provider.calls if c['recipe'] == 'sequential_draft'])
        with self.assertRaises(Refused) as refused:
            self.desk.resume_commission(commission_id)
        self.assertEqual(refused.exception.code, 'accounting_uncertain')
        self.assertEqual(len([c for c in self.provider.calls if c['recipe'] == 'sequential_draft']), calls)

    def test_a_second_process_does_not_orphan_a_request_the_first_is_still_waiting_on(self):
        self.interrupted_run()
        first = self.claim()
        self.desk.connection.execute("UPDATE v1_job SET state='sent'")
        self.assertIsNone(self.claim())
        self.assertEqual(self.desk.connection.execute("SELECT state FROM v1_job").fetchone()[0], 'sent')
        self.assertIsNotNone(first)


if __name__ == '__main__':
    unittest.main()
