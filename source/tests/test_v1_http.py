"""V1 desk over real HTTP: the served studio drives the whole journey through `Desk`."""
import ast
import http.client
import json
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path

from serial_story.studio.server import create_server
from serial_story.v1.desk import Desk
from serial_story.v1.provider import ScriptedProvider

REPO = Path(__file__).resolve().parents[1]
RUNS = REPO / 'local' / 'test-runs'

SKELETON = {'premise': 'Leena Vale borrows voices; each use costs a memory.',
            'spine': 'Expose coercion; useful lies give way to accountable uncertainty.'}
INTENTIONS = ['Leena stages a witness interview; the reader sees her memory cost.',
              'A witness says courier Oren died in a lockhouse fire; Darin hears it.',
              'Darin obtains the dispatch ledger that predates the alleged death.']
ARC = {'purpose': 'make Darin suspect a manufactured witness',
       'end_state': 'an ordinary record the recorder cannot alter', 'intentions': INTENTIONS}


class V1HttpCase(unittest.TestCase):
    def setUp(self):
        RUNS.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=RUNS)
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'legacy.db'
        self.v1_path = Path(self.tmp.name) / 'story.v1.db'
        self.provider = ScriptedProvider()
        self.server = create_server(self.path, port=0, writes=True, v1_path=self.v1_path, v1_provider=self.provider)
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.port = self.server.server_port
        self.token = self.get('/api/session')[1]['token']

    def request(self, method, route, body=None, token=True):
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
        headers = {'Host': f'127.0.0.1:{self.port}'}
        data = None
        if method == 'POST':
            headers.update({'Origin': f'http://127.0.0.1:{self.port}', 'Content-Type': 'application/json'})
            if token:
                headers['X-Studio-Token'] = self.token
            data = json.dumps(body).encode()
        connection.request(method, route, body=data, headers=headers)
        response = connection.getresponse()
        raw = response.read()
        connection.close()
        return response.status, json.loads(raw)

    def get(self, route):
        return self.request('GET', route)

    def post(self, command, payload=None, expected=None, status=200):
        body = {'payload': payload or {}}
        if expected is not None:
            body['expected'] = expected
        code, data = self.request('POST', f'/api/v1/{command}', body)
        self.assertEqual(code, status, (command, data))
        return data

    def state(self):
        code, data = self.get('/api/v1/state')
        self.assertEqual(code, 200, data)
        return data

    def episode(self, state, ordinal):
        return next(e for e in state['episodes'] if e['ordinal'] == ordinal)


class V1HttpJourneyTest(V1HttpCase):
    def test_full_journey_over_http_with_persisted_state(self):
        self.assertIsNone(self.state()['story'])
        self.assertFalse(self.v1_path.exists(), 'opening the studio never creates the v1 story')
        self.post('create_story')
        self.assertTrue(self.v1_path.exists())

        # Adopt overall direction.
        s1 = self.post('save_direction', {'layer': 'skeleton', 'content': SKELETON})['revision_id']
        self.post('adopt', {'revision_id': s1}, {'governing': None})
        a1 = self.post('save_direction', {'layer': 'arc', 'content': ARC})['revision_id']
        self.post('adopt', {'revision_id': a1}, {'governing': None})
        stale = self.post('adopt', {'revision_id': a1}, {'governing': None}, status=409)
        self.assertEqual(stale['code'], 'stale_pointer')
        state = self.state()
        self.assertEqual(state['governing']['skeleton']['revision_id'], s1)
        self.assertEqual(state['governing']['arc']['revision_id'], a1)
        self.assertEqual([e['ordinal'] for e in state['episodes']], [1, 2, 3])

        # Commission linked drafts.
        commission = self.post('commission_arc', {'slots': [1, 3], 'progression': 'provisional_chain'})
        self.assertEqual(commission['status'], 'complete')
        state = self.state()
        drafts = [self.episode(state, n) for n in (1, 2, 3)]
        self.assertTrue(all(e['selection']['selected_by'] == 'commission' for e in drafts))
        self.assertEqual(len({e['text'] for e in drafts}), 3)
        self.assertEqual(state['canon'], [])
        original = drafts[0]

        # Selectively rewrite one block.
        target = original['blocks'][0]
        candidate = self.post('request_rewrite', {'ordinal': 1, 'block_id': target['block_id'], 'intent': 'polish',
                                                  'reason': 'tighten the rhythm'}, {'block_sha256': target['sha256']})
        self.assertNotEqual(candidate['replacement'], target['text'])
        self.assertEqual(self.episode(self.state(), 1)['selection']['revision_id'], original['selection']['revision_id'])
        applied = self.post('apply_candidate', {'candidate_id': candidate['candidate_id']},
                            {'selection_cas': original['selection']['cas']})
        self.assertEqual(applied['flagged'], [2, 3])
        rewritten = self.episode(self.state(), 1)
        self.assertEqual(rewritten['blocks'][0]['text'], candidate['replacement'])
        self.assertEqual([b['text'] for b in rewritten['blocks'][1:]], [b['text'] for b in original['blocks'][1:]])

        # Undo.
        self.post('revert_event', {'event_id': applied['event_id']})
        undone = self.episode(self.state(), 1)
        self.assertEqual(undone['text'], original['text'])
        self.assertNotEqual(undone['selection']['revision_id'], original['selection']['revision_id'])

        # Accept: downstream drafts were flagged by the edit, so the author revalidates first.
        refused = self.post('accept_prefix', {'episodes': self.group(self.state(), (1, 2, 3))}, {'canon_seq': 0}, status=400)
        self.assertEqual(refused['code'], 'open_conflict')
        for n in (2, 3):
            self.post('revalidate', {'ordinal': n})
        state = self.state()
        receipt = self.post('accept_prefix', {'episodes': self.group(state, (1, 2, 3))}, {'canon_seq': 0})
        self.assertEqual(receipt['canon_seq'], 1)
        for warning in receipt['warnings']:
            self.assertEqual(warning['band'], [550, 700, 900])
            self.assertFalse(550 <= warning['words'] <= 900)
        words = {n: self.episode(state, n)['words'] for n in (1, 2, 3)}
        self.assertEqual(sorted(w['ordinal'] for w in receipt['warnings']),
                         sorted(n for n, count in words.items() if not 550 <= count <= 900))
        state = self.state()
        self.assertEqual([c['ordinal'] for c in state['canon']], [1, 2, 3])
        self.assertEqual(state['canon'][0]['text'], original['text'])

        # Inspect memory: nothing until the author authorizes the pass over accepted text.
        self.assertEqual(state['memory']['accepted'], [])
        counts = self.post('update_memory')
        self.assertEqual(counts, {'imported': 3, 'obsolete': 0})
        state = self.state()
        canon_text = {c['revision_id']: c['text'] for c in state['canon']}
        self.assertTrue(state['memory']['accepted'])
        for claim in state['memory']['accepted']:
            block = next(b for b in self.blocks_of(state, claim['revision_id']) if b['block_id'] == claim['block_id'])
            self.assertEqual(block['text'][claim['start']:claim['end']], claim['quote'])
            self.assertIn(claim['quote'], canon_text[claim['revision_id']])
        self.assertNotIn('not in text', [c['quote'] for c in state['memory']['accepted']])

        # Continue: context comes from accepted memory, then the next slot drafts from exact canon.
        code, context = self.get('/api/v1/context?boundary=3')
        self.assertEqual(code, 200, context)
        self.assertEqual(context['mode'], 'indexed')
        self.assertEqual([i['ordinal'] for i in context['items']], [1, 2, 3])
        a2 = self.post('save_direction', {'layer': 'arc', 'content': {**ARC, 'intentions': INTENTIONS + [
            'Darin files the dispatch ledger as an ordinary record.']}})['revision_id']
        self.post('adopt', {'revision_id': a2}, {'governing': a1})
        self.assertEqual(self.post('commission_arc', {'slots': [4, 4]})['status'], 'complete')
        state = self.state()
        fourth = self.episode(state, 4)
        self.assertEqual(fourth['predecessors'], [[c['revision_id'], c['sha256']] for c in state['canon']])
        self.assertFalse(fourth['accepted'])
        self.assertEqual(len(state['canon']), 3)
        self.assertIn('Darin files the dispatch ledger', self.provider.calls[-1]['prompt'])

        # Persisted state, read straight from the file the server wrote.
        self.server.shutdown()
        raw = sqlite3.connect(self.v1_path)
        try:
            rows = raw.execute('SELECT ordinal, text, sha256 FROM v1_canon ORDER BY ordinal').fetchall()
            self.assertEqual([(r[0], r[1]) for r in rows], [(c['ordinal'], c['text']) for c in state['canon']])
            actions = [r[0] for r in raw.execute('SELECT action FROM v1_event ORDER BY seq')]
            for action in ('adopt', 'commission_start', 'rewrite_apply', 'revert', 'revalidate', 'accept'):
                self.assertIn(action, actions)
            self.assertEqual(raw.execute("SELECT count(*) FROM v1_outbox WHERE state='imported'").fetchone()[0], 3)
        finally:
            raw.close()
        reopened = Desk.open(self.v1_path, provider=ScriptedProvider())
        try:
            self.assertEqual(reopened.selection(4)['revision_id'], fourth['selection']['revision_id'])
        finally:
            reopened.close()
        self.assertTrue(all(c['recipe'] in {'sequential_draft', 'polish_rewrite', 'promotion'} for c in self.provider.calls))

    def group(self, state, ordinals):
        return [{'ordinal': n, 'revision_id': self.episode(state, n)['selection']['revision_id'],
                 'sha256': self.episode(state, n)['selection']['sha256']} for n in ordinals]

    def blocks_of(self, state, revision_id):
        return next(e['blocks'] for e in state['episodes'] if e['selection']['revision_id'] == revision_id)


class V1HttpBoundaryTest(V1HttpCase):
    def test_v1_mutations_need_the_session_token_and_known_commands(self):
        code, _ = self.request('POST', '/api/v1/create_story', {'payload': {}}, token=False)
        self.assertEqual(code, 403)
        self.assertFalse(self.v1_path.exists())
        code, _ = self.request('POST', '/api/v1/drop_tables', {'payload': {}})
        self.assertEqual(code, 404)
        code, body = self.request('POST', '/api/v1/create_story', {'payload': {}, 'sql': 'x'})
        self.assertEqual(code, 400, body)
        code, body = self.request('POST', '/api/v1/save_direction', {'payload': {'layer': 'skeleton', 'content': SKELETON}})
        self.assertEqual(code, 400, body)

    def test_state_reports_the_offline_provider(self):
        self.assertEqual(self.state()['provider'], {'kind': 'scripted', 'live': False})


class V1ProviderIsolationTest(unittest.TestCase):
    NETWORK = {'urllib', 'http', 'socket', 'ssl', 'requests', 'httpx', 'aiohttp'}
    LIVE = {'merge', 'authoring', 'budget'}

    def test_v1_package_cannot_import_a_network_or_live_provider_path(self):
        for source in (REPO / 'serial_story' / 'v1').glob('*.py'):
            tree = ast.parse(source.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ''] + [a.name for a in node.names]
                for name in names:
                    parts = set(name.split('.'))
                    self.assertFalse(parts & (self.NETWORK | self.LIVE), f'{source.name} imports {name}')

    def test_server_default_v1_provider_is_scripted(self):
        from serial_story.studio import server
        self.assertIs(server.default_v1_provider().__class__, ScriptedProvider)


if __name__ == '__main__':
    unittest.main()
