"""Live series on the shelf: separate money per series, a hard cap, and no way to run live on the practice writer."""
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from serial_story.records import StoryError
from serial_story.studio.server import create_server
from serial_story.v1.merge_provider import MergeProvider
from serial_story.v1.provider import GenerationRequest, ScriptedProvider
from serial_story.v1.shelf import Live, Shelf

REPO = Path(__file__).resolve().parents[1]
RUNS = REPO / 'local' / 'test-runs'


def ok_body(cost=0.01):
    return {'choices': [{'message': {'content': 'Hello.'}, 'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 100, 'completion_tokens': 50, 'cost': cost,
                      'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0}},
            'routing': {'model_used': 'anthropic/claude-sonnet-5-5', 'vendor_used': 'anthropic',
                        'merge_fee_usd': 0.0, 'reasoning_effort_applied': 'none'}}


class Transport:
    def __init__(self):
        self.sent = 0

    def __call__(self, payload):
        self.sent += 1
        return 200, ok_body(), {'x-request-id': 'r'}, 0.1


def request():
    return GenerationRequest('sequential_draft', 'x', 'k', params={'messages': [{'role': 'user', 'content': 'JOB'}]})


class LiveShelfCase(unittest.TestCase):
    def tmp(self) -> Path:
        RUNS.mkdir(parents=True, exist_ok=True)
        tmp = tempfile.TemporaryDirectory(dir=RUNS)
        self.addCleanup(tmp.cleanup)
        return Path(tmp.name) / 'stories'

    def live(self, root: Path, transport=None, **limits) -> Shelf:
        transport = transport or Transport()
        live = Live(build=lambda folder, cap: MergeProvider(transport=transport, spend_log=folder / 'story.spend.jsonl', cap_usd=cap), **limits)
        shelf = Shelf(root, ScriptedProvider, live=live)
        self.addCleanup(shelf.close)
        return shelf

    def practice(self, root: Path) -> Shelf:
        shelf = Shelf(root, ScriptedProvider)
        self.addCleanup(shelf.close)
        return shelf


class LiveCreateTest(LiveShelfCase):
    def test_a_practice_shelf_refuses_to_create_a_live_series(self):
        shelf = self.practice(self.tmp())
        self.assertEqual(shelf.capabilities(), {'live': False})
        with self.assertRaises(StoryError):
            shelf.create('Nope', 'live', 2)
        self.assertEqual(shelf.slugs(), [])

    def test_limits_are_checked_and_clamped(self):
        shelf = self.live(self.tmp(), max_cap=2.0, default_cap=1.0)
        for bad in (0, -1, 2.01, 5, True, '3', float('nan')):
            with self.assertRaises(StoryError, msg=repr(bad)):
                shelf.create('Capped', 'live', bad)
        self.assertEqual(shelf.slugs(), [])
        slug = shelf.create('Capped', 'live', 2)
        self.assertEqual(shelf.summary(slug)['cap_usd'], 2.0)
        self.assertEqual(shelf.summary(shelf.create('Default', 'live'))['cap_usd'], 1.0)

    def test_an_unknown_writer_is_refused(self):
        with self.assertRaises(StoryError):
            self.live(self.tmp()).create('Odd', 'robot')

    def test_capabilities_state_the_limits(self):
        self.assertEqual(self.live(self.tmp()).capabilities(), {'live': True, 'max_cap': 5.0, 'default_cap': 3.0})


class LiveIsolationTest(LiveShelfCase):
    def test_each_series_has_its_own_money_and_log(self):
        transport = Transport()
        shelf = self.live(self.tmp(), transport)
        a, b = shelf.create('Alpha', 'live', 0.5), shelf.create('Beta', 'live', 4)
        shelf.desk(a).provider.generate(request())
        shelf.desk(a).provider.generate(request())
        self.assertEqual(transport.sent, 2)
        sa, sb = shelf.summary(a), shelf.summary(b)
        self.assertGreater(sa['spent_usd'], 0)
        self.assertEqual(sb['spent_usd'], 0)
        self.assertEqual((sa['cap_usd'], sb['cap_usd']), (0.5, 4.0))
        self.assertTrue((shelf.root / a / 'story.spend.jsonl').is_file())
        self.assertFalse((shelf.root / b / 'story.spend.jsonl').exists())

    def test_one_series_hitting_its_cap_does_not_stop_another(self):
        from serial_story.v1.provider import NotSent
        shelf = self.live(self.tmp(), Transport())
        small, big = shelf.create('Small', 'live', 0.5), shelf.create('Big', 'live', 5)
        with self.assertRaises(NotSent):
            for _ in range(500):
                shelf.desk(small).provider.generate(request())
        self.assertLessEqual(shelf.summary(small)['spent_usd'], 0.5)
        shelf.desk(big).provider.generate(request())

    def test_spend_survives_a_restart(self):
        root = self.tmp()
        shelf = self.live(root, Transport())
        slug = shelf.create('Keeps', 'live', 1)
        shelf.desk(slug).provider.generate(request())
        spent = shelf.summary(slug)['spent_usd']
        shelf.close()
        again = self.live(root, Transport())
        self.assertEqual(again.summary(slug)['spent_usd'], spent)


class LiveNeverFallsBackTest(LiveShelfCase):
    def test_a_live_series_is_not_opened_on_a_practice_desk(self):
        root = self.tmp()
        slug = self.live(root).create('Real money', 'live', 1)
        practice = self.practice(root)
        self.assertIsNone(practice.desk(slug))
        row = practice.summary(slug)
        self.assertEqual((row['writer'], row['available']), ('live', False))
        self.assertIsNone(row['spent_usd'])

    def test_a_damaged_live_record_does_not_become_a_practice_series(self):
        root = self.tmp()
        shelf = self.live(root)
        slug = shelf.create('Broken', 'live', 1)
        shelf.close()
        meta = root / slug / 'meta.json'
        meta.write_text(json.dumps({'title': 'Broken', 'writer': 'live'}), encoding='utf-8')
        again = self.live(root)
        with self.assertRaises((KeyError, TypeError, ValueError)):
            again.desk(slug)

    def build_zip(self, beta):
        import importlib.util
        import zipfile
        spec = importlib.util.spec_from_file_location('make_trial_zip', REPO / 'scripts' / 'make_trial_zip.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        out = Path(self.tmp()) / ('beta.zip' if beta else 'trial.zip')
        module.build(out, module.BETA_EXTRAS if beta else module.TRIAL_EXTRAS)
        with zipfile.ZipFile(out) as z:
            return {n: z.read(n) for n in z.namelist()}

    def test_the_trial_zip_has_no_live_launcher(self):
        names = {Path(n).name for n in self.build_zip(False)}
        self.assertNotIn('run_shelf_live.py', names)
        self.assertNotIn('run_v1_live.py', names)
        self.assertNotIn('live-it.bat', names)

    def test_the_beta_zip_has_the_live_launcher_but_never_a_key(self):
        files = self.build_zip(True)
        names = {Path(n).name for n in files}
        for needed in ('run_shelf_live.py', 'live-it.bat', 'live-it.sh', '.env.example', 'README.md', 'guide.js'):
            self.assertIn(needed, names)
        self.assertNotIn('.env', names)
        self.assertNotIn('run_v1_live.py', names)
        self.assertFalse([n for n in names if n.endswith(('.db', '.jsonl'))])
        for name, data in files.items():
            for line in data.decode('utf-8', 'ignore').splitlines():
                if 'MERGE_GATEWAY_API_KEY=' in line and Path(name).suffix not in ('.py', '.md'):
                    self.assertEqual(line.split('MERGE_GATEWAY_API_KEY=', 1)[1].strip(), '', f'{name} holds a key value')
        self.assertIn(b'gateway.merge.dev/api-keys', files['serial-story-studio/README.md'])


class LiveHttpTest(LiveShelfCase):
    def serve(self, shelf):
        self.server = create_server(shelf.root / '.legacy.db', port=0, writes=True, shelf=shelf)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.port = self.server.server_port
        self.token = self.call('GET', '/api/session')[1]['token']

    def call(self, method, route, body=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
        headers = {'Host': f'127.0.0.1:{self.port}'}
        data = None
        if method == 'POST':
            headers.update({'Origin': f'http://127.0.0.1:{self.port}', 'Content-Type': 'application/json',
                            'X-Studio-Token': self.token})
            data = json.dumps(body).encode()
        connection.request(method, route, body=data, headers=headers)
        response = connection.getresponse()
        raw = response.read()
        connection.close()
        try:
            return response.status, json.loads(raw)
        except ValueError:
            return response.status, raw

    def test_the_shelf_api_reports_what_this_desk_can_do(self):
        self.serve(self.practice(self.tmp()))
        self.assertEqual(self.call('GET', '/api/shelf')[1]['live'], False)
        self.assertEqual(self.call('POST', '/api/shelf/create', {'title': 'X', 'writer': 'live', 'cap_usd': 1})[0] // 100, 4)

    def test_live_create_over_http_and_money_shows_in_state(self):
        shelf = self.live(self.tmp())
        self.serve(shelf)
        data = self.call('GET', '/api/shelf')[1]
        self.assertEqual((data['live'], data['max_cap']), (True, 5.0))
        status, made = self.call('POST', '/api/shelf/create', {'title': 'Over HTTP', 'writer': 'live', 'cap_usd': 2})
        self.assertEqual(status, 200, made)
        state = self.call('GET', made['path'].rstrip('/') + '/api/v1/state')[1]
        self.assertTrue(state['provider']['live'])
        self.assertEqual(state['provider']['cap_usd'], 2.0)
        self.assertEqual(self.call('POST', '/api/shelf/create', {'title': 'Too much', 'writer': 'live', 'cap_usd': 50})[0] // 100, 4)

    def test_a_live_series_is_a_404_on_a_practice_desk(self):
        root = self.tmp()
        slug = self.live(root).create('Closed', 'live', 1)
        self.serve(self.practice(root))
        self.assertEqual(self.call('GET', f'/s/{slug}/api/v1/state')[0], 404)
        self.assertEqual(self.call('GET', f'/s/{slug}/')[0], 404)


if __name__ == '__main__':
    unittest.main()
