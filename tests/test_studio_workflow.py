"""End-to-end authoring workflow over the writable studio boundary."""
import json
import tempfile
import threading
import unittest
from pathlib import Path

from serial_story.studio.server import create_server

REPO = Path(__file__).resolve().parents[1]
RUNS = REPO / 'local' / 'test-runs'
PROSE = ('The lamp turned once each night. '
         + 'The keeper wrote the log in steady lines. ' * 50).strip()


class StudioWorkflowTests(unittest.TestCase):
    def setUp(self):
        RUNS.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=RUNS)
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'studio.db'
        self.server = create_server(self.path, port=0, writes=True)
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(lambda: (self.server.shutdown(), self.server.server_close(), thread.join(5)))
        self.token = json.loads(self.get('/api/session')[2])['token']

    def get(self, route):
        import http.client
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        try:
            connection.request('GET', route)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def post(self, route, payload, expect=200):
        import http.client
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        try:
            body = json.dumps(payload).encode()
            connection.request('POST', route, body, headers={
                'Content-Type': 'application/json', 'X-Studio-Token': self.token,
                'Origin': f'http://127.0.0.1:{self.server.server_port}'})
            response = connection.getresponse()
            content = response.read()
            self.assertEqual(response.status, expect, f'{route}: {content!r}')
            return json.loads(content) if content else {}
        finally:
            connection.close()

    def state(self):
        return json.loads(self.get('/api/state')[2])

    def plan_content(self, intentions=3):
        return {'beats': [{'intention': f'Episode {n}: the lamp keeps its promise.'}
                          for n in range(1, intentions + 1)]}

    def draft_to_accept(self, text=PROSE):
        self.post('/api/setup', {'premise': 'A lighthouse story.'})
        plan = self.post('/api/plan/save', {'content': self.plan_content()})
        self.post('/api/plan/approve', {'plan_id': plan['plan_id']})
        self.post('/api/draft/save', {'text': text, 'basis': self.basis()})
        pending = self.state()['pending']
        return pending['id']

    def basis(self):
        return self.state()['basis']

    def accept_payload(self, revision_id):
        state = self.state()
        return {'revision_id': revision_id, 'expected_text_version': state['pending']['text_version'], 'basis': state['basis']}

    def test_accept_refuses_unseen_edit_and_keeps_canon_empty(self):
        revision_id = self.draft_to_accept()
        payload = self.accept_payload(revision_id)
        self.post('/api/draft/edit', {'revision_id': revision_id, 'text': PROSE + ' Changed elsewhere.', 'expected_text_version': 1})
        self.post('/api/accept', payload, expect=409)
        self.assertEqual(self.state()['accepted'], [])
        self.assertEqual(self.state()['story']['next_episode'], 1)

    def test_offline_generation_consumes_saved_prompt_and_scoped_feedback(self):
        self.post('/api/setup', {'premise': 'A lighthouse story.'})
        plan = self.post('/api/plan/save', {'content': self.plan_content()})
        self.post('/api/plan/approve', {'plan_id': plan['plan_id']})
        self.post('/api/settings', {'expected_version': 1, 'prompt_template': 'Write in Bengali, with a quiet tone.'})
        request = {'basis': self.basis(), 'operation_id': 'first-generation'}
        first = self.post('/api/draft/generate', request)
        pending = self.state()['pending']
        self.assertTrue(pending['run']['synthetic'])
        self.assertIn('Write in Bengali', pending['run']['frozen_prompt'])
        self.assertIn('SYNTHETIC', pending['text'])
        self.post('/api/draft/feedback', {'revision_id': pending['id'], 'expected_text_version': 1,
                  'basis': self.basis(), 'scope': 'this-revision', 'note': 'Keep the storm offstage.'})
        revision_request = {'basis': self.basis(), 'revision_id': pending['id'],
                            'expected_text_version': 1, 'operation_id': 'revision-one'}
        second = self.post('/api/draft/revise', revision_request)
        revised = self.state()['pending']
        self.assertNotEqual(first['revision_id'], second['revision_id'])
        self.assertNotEqual(pending['text'], revised['text'])
        self.assertEqual(revised['run']['parent_revision_id'], pending['id'])
        self.assertIn('Keep the storm offstage.', revised['run']['frozen_prompt'])
        self.assertEqual(revised['run']['feedback'][0]['source_text_version'], 1)
        self.assertEqual(self.post('/api/draft/revise', revision_request), second)
        final = PROSE + ' Author closing words.'
        self.post('/api/draft/edit', {'revision_id': revised['id'], 'expected_text_version': 1, 'text': final})
        acceptance = self.accept_payload(revised['id'])
        result = self.post('/api/accept', acceptance)
        self.assertEqual(result['receipt']['provider'], 'fake')
        self.assertTrue(result['receipt']['author_edited'])
        self.assertEqual(self.post('/api/accept', acceptance), result)
        import sqlite3
        from contextlib import closing
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('SELECT final_text FROM memory_sources').fetchone()[0], final)
            self.assertEqual(db.execute('SELECT count(*) FROM studio_runs').fetchone()[0], 2)

    def test_saved_plan_separates_established_history_and_future(self):
        revision_id = self.draft_to_accept()
        original = self.state()['plan']
        self.assertEqual(len(original['content']['beats']), 200)
        self.post('/api/accept', self.accept_payload(revision_id))
        changed = self.plan_content()
        changed['beats'][0]['intention'] = 'Rewrite already accepted intention.'
        self.post('/api/plan/save', {'content': changed, 'expected_plan_id': original['id']}, expect=400)
        changed['beats'][0] = original['content']['beats'][0]
        changed['beats'][1]['intention'] = 'A new future intention.'
        self.post('/api/plan/save', {'content': changed, 'expected_plan_id': original['id']})
        restored = self.state()['plan']
        self.assertEqual(restored['established'][0]['intention'], original['content']['beats'][0]['intention'])
        self.assertEqual(restored['future'][0]['intention'], 'A new future intention.')
        self.post('/api/plan/save', {'content': self.plan_content(201), 'expected_plan_id': restored['id']}, expect=400)

    def test_paid_off_manual_source_and_prompt_reset_are_truthful(self):
        self.post('/api/setup', {'premise': 'A lighthouse story.'})
        plan = self.post('/api/plan/save', {'content': self.plan_content()})
        self.post('/api/plan/approve', {'plan_id': plan['plan_id']})
        self.post('/api/settings', {'expected_version': 1, 'provider': 'merge', 'model': 'anthropic/claude-opus-5-5',
                                  'vendor': 'anthropic', 'prompt_template': 'Quiet Bengali prose.'})
        self.assertEqual(self.state()['settings']['vendor'], 'anthropic')
        self.post('/api/draft/generate', {'basis': self.basis(), 'operation_id': 'paid-disabled'}, expect=400)
        self.assertIsNone(self.state()['pending'])
        self.post('/api/draft/save', {'text': PROSE, 'basis': self.basis()})
        pending = self.state()['pending']
        result = self.post('/api/accept', self.accept_payload(pending['id']))
        self.assertEqual(result['receipt']['provider'], 'manual')
        self.assertEqual(result['receipt']['model'], '')
        self.post('/api/settings', {'expected_version': 2, 'prompt_template': ''})
        self.assertNotEqual(self.state()['settings']['prompt_template'], 'Quiet Bengali prose.')
        self.assertGreater(self.state()['settings']['prompt_version'], 1)

    def test_receipt_insert_failure_rolls_back_canonical_acceptance(self):
        import sqlite3
        from contextlib import closing
        revision_id = self.draft_to_accept()
        payload = self.accept_payload(revision_id)
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("CREATE TRIGGER fail_receipt BEFORE INSERT ON studio_acceptances BEGIN SELECT RAISE(ABORT,'synthetic receipt failure'); END")
            db.commit()
        self.post('/api/accept', payload, expect=500)
        state = self.state()
        self.assertEqual(state['accepted'], [])
        self.assertEqual(state['receipts'], [])
        self.assertEqual(state['pending']['id'], revision_id)
        self.assertEqual(state['story']['next_episode'], 1)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM memory_sources').fetchone()[0], 0)
            db.execute('DROP TRIGGER fail_receipt')
            db.commit()
        self.post('/api/accept', payload)

    def test_plan_settings_and_feedback_versions_refuse_races(self):
        revision_id = self.draft_to_accept()
        original = self.accept_payload(revision_id)
        self.post('/api/draft/feedback', {**original, 'note': 'Earlier feedback', 'scope': 'series'})
        self.post('/api/accept', original, expect=409)
        fresh = self.accept_payload(revision_id)
        self.post('/api/settings', {'expected_version': 1, 'prompt_template': 'Changed instructions.'})
        self.post('/api/accept', fresh, expect=409)
        current = self.accept_payload(revision_id)
        self.post('/api/accept', current, expect=409)
        self.post('/api/draft/revise', {**current, 'operation_id': 'changed-settings'}, expect=409)
        self.assertEqual(self.state()['accepted'], [])

    # -- Plan ---------------------------------------------------------------
    def test_plan_feedback_binds_explicit_loaded_plan(self):
        import sqlite3
        from contextlib import closing
        self.post('/api/setup', {'premise': 'Synthetic premise'})
        self.post('/api/plan/save', {'content': self.plan_content()})
        self.post('/api/plan/feedback', {'plan_id': 1, 'note': 'About first plan'})
        self.post('/api/plan/save', {'content': self.plan_content(2), 'expected_plan_id': 1})
        before = self.state()
        self.post('/api/plan/feedback', {'plan_id': 1, 'note': 'Unseen second plan'}, expect=409)
        self.assertEqual(self.state(), before)
        for bad in (None, True, '2', 2.0):
            self.post('/api/plan/feedback', {'plan_id': bad, 'note': 'Invalid ID'}, expect=400)
        self.post('/api/plan/feedback', {'plan_id': 2, 'note': 'About second plan'})
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('SELECT plan_id,note FROM plan_feedback ORDER BY id').fetchall(),
                             [(1, 'About first plan'), (2, 'About second plan')])

    def test_plan_versions_use_compare_and_swap(self):
        self.post('/api/setup', {'premise': 'A lighthouse story.'})
        first = self.post('/api/plan/save', {'content': self.plan_content()})
        self.assertEqual(first['plan_id'], 1)
        stale = self.post('/api/plan/save', {'content': self.plan_content(2),
                                             'expected_plan_id': 99}, expect=409)
        self.assertIn('changed', stale['message'])
        second = self.post('/api/plan/save', {'content': self.plan_content(2),
                                              'expected_plan_id': first['plan_id']})
        self.assertEqual(second['plan_id'], 2)

    def test_short_plan_marks_remaining_beats_unplanned(self):
        self.post('/api/setup', {'premise': 'A lighthouse story.'})
        self.post('/api/plan/save', {'content': self.plan_content(3)})
        state = self.state()
        self.assertEqual(state['plan']['next_unplanned'], 4)

    def test_approval_requires_latest_plan(self):
        self.post('/api/setup', {'premise': 'A lighthouse story.'})
        self.post('/api/plan/save', {'content': self.plan_content()})
        self.post('/api/plan/save', {'content': self.plan_content(2), 'expected_plan_id': 1})
        self.post('/api/plan/approve', {'plan_id': 1}, expect=400)
        result = self.post('/api/plan/approve', {'plan_id': 2})
        self.assertEqual(result['status'], 'approved')

    # -- Draft and acceptance ----------------------------------------------
    def test_pending_edit_preserves_and_rejects_stale_save(self):
        revision_id = self.draft_to_accept()
        self.post('/api/draft/feedback', {'revision_id': revision_id, 'scope': 'this-revision',
                                          'note': 'Slow the opening, keep the lamp exact.', 'expected_text_version': 1, 'basis': self.basis()})
        edited = PROSE + ' Extra closing beat.'
        stale = self.post('/api/draft/edit', {'revision_id': revision_id, 'text': edited,
                                              'expected_text_version': 99}, expect=409)
        self.assertIn('changed', stale['message'])
        self.assertEqual(self.state()['pending']['text'], PROSE)
        self.post('/api/draft/edit', {'revision_id': revision_id, 'text': edited,
                                      'expected_text_version': 1})
        self.assertEqual(self.state()['pending']['text'], edited)

    def test_accept_is_exactly_once_with_receipt(self):
        revision_id = self.draft_to_accept()
        payload = self.accept_payload(revision_id)
        result = self.post('/api/accept', payload)
        self.assertEqual(result['accepted']['number'], 1)
        receipt = result['receipt']
        self.assertEqual(receipt['provider'], 'manual')
        self.assertEqual(receipt['feedback_count'], 0)
        self.assertGreaterEqual(receipt['prompt_version'], 1)
        # A retry that re-sends identical prose stays accepted, not duplicated.
        retry = self.post('/api/accept', payload)
        self.assertEqual(retry['accepted']['revision_id'], revision_id)
        state = self.state()
        self.assertIsNone(state['pending'])
        self.assertEqual(len(state['accepted']), 1)
        self.assertEqual(len(state['receipts']), 1)

    def test_short_final_prose_is_refused_not_trimmed(self):
        revision_id = self.draft_to_accept('Too short by far.')
        self.post('/api/accept', self.accept_payload(revision_id), expect=400)
        self.assertEqual(self.state()['pending']['id'], revision_id)

    def test_reject_requires_original_loaded_versions(self):
        revision_id = self.draft_to_accept()
        original = self.accept_payload(revision_id)
        self.post('/api/draft/edit', {'revision_id': revision_id, 'text': PROSE + ' New saved words.', 'expected_text_version': 1})
        before = self.state()
        self.post('/api/reject', original, expect=409)
        self.assertEqual(self.state(), before)
        self.post('/api/reject', {'revision_id': revision_id}, expect=400)
        self.assertEqual(self.state(), before)
        fresh = self.accept_payload(revision_id)
        self.post('/api/settings', {'expected_version': 1, 'prompt_template': 'New directions.'})
        before = self.state()
        self.post('/api/reject', fresh, expect=409)
        self.assertEqual(self.state(), before)
        self.post('/api/reject', self.accept_payload(revision_id))
        self.assertIsNone(self.state()['pending'])

    def test_rejection_records_note_and_clears_pending(self):
        revision_id = self.draft_to_accept()
        self.post('/api/reject', {**self.accept_payload(revision_id), 'note': 'Restart from the storm.'})
        self.assertIsNone(self.state()['pending'])
        self.assertEqual(self.state()['accepted'], [])

    # -- Memory -------------------------------------------------------------
    def test_memory_confirmation_is_separate_and_saved(self):
        revision_id = self.draft_to_accept()
        self.post('/api/accept', self.accept_payload(revision_id))
        entity = self.post('/api/memory/entity', {'name': 'Lamp', 'kind': 'location'})
        proposal = self.post('/api/memory/fact', {
            'subject_id': entity['entity_id'], 'predicate': 'turns', 'value': 'nightly',
            'source_revision_id': revision_id, 'evidence': 'The lamp turned once each night.'})
        self.assertEqual(proposal['status'], 'proposed')
        confirmed = self.post('/api/memory/confirm', {'fact_id': proposal['fact_id']})
        self.assertEqual(confirmed['status'], 'confirmed')
        self.assertGreater(confirmed['memory_revision'], 0)
        again = self.post('/api/memory/confirm', {'fact_id': proposal['fact_id']})
        self.assertEqual(again['fact_id'], proposal['fact_id'])

    # -- Settings -----------------------------------------------------------
    def test_settings_persist_with_version_and_cas(self):
        self.post('/api/setup', {'premise': 'A lighthouse story.'})
        stale = self.post('/api/settings', {'expected_version': 99, 'provider': 'merge'},
                          expect=409)
        self.assertIn('changed', stale['message'])
        saved = self.post('/api/settings', {'expected_version': 1, 'provider': 'merge',
                                            'model': 'vendor/model-x', 'output_limit_words': 650})
        settings = saved['settings']
        self.assertEqual(settings['provider'], 'merge')
        self.assertEqual(settings['version'], 2)
        self.assertEqual(self.state()['settings']['model'], 'vendor/model-x')
        bad = self.post('/api/settings', {'expected_version': 2, 'provider': 'gpt'}, expect=400)
        self.assertIn('provider', bad['message'])


if __name__ == '__main__':
    unittest.main()
