import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path
from serial_story.repository import SQLiteRepository
from serial_story.service import StoryService


class ReviewWebTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / 'local' / 'test-runs')
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'story.db'
        with SQLiteRepository(self.path) as repo:
            studio = StoryService(repo)
            studio.initialize('A keeper hears a voice from the lighthouse.')
            plan = studio.propose_plan()
            studio.approve_plan(plan.id)
            self.accepted = studio.accept(studio.draft().id)
            self.pending = studio.draft()
            studio.memory.add_entity('Ivo', 'character', 'protagonist')

    def test_read_only_snapshot_has_exact_prose_plan_and_word_checks(self):
        self.assertIsNotNone(importlib.util.find_spec('serial_story.review_web'), 'Live review workspace module is missing')
        from serial_story.review_web import story_snapshot
        before = hashlib.sha256(self.path.read_bytes()).hexdigest()
        view = story_snapshot(self.path, fixture=True)
        self.assertTrue(view['fixture_only'])
        self.assertFalse(view['generation_enabled'])
        self.assertEqual(len(view['plan']['content']['beats']), 200)
        accepted = next(e for e in view['episodes'] if e['status'] == 'accepted')
        self.assertEqual(accepted['prose'], self.accepted.text)
        self.assertEqual(accepted['words'], len(self.accepted.text.split()))
        self.assertTrue(accepted['word_count_ok'])
        self.assertEqual(view['story']['next_episode'], 2)
        self.assertEqual(view['entities'][0]['name'], 'Ivo')
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(), before)


    def test_http_is_live_read_only_and_rejects_other_origins_and_paths(self):
        import threading
        import urllib.request
        import urllib.error
        import json
        import serial_story.review_web as web
        self.assertTrue(hasattr(web, 'create_server'), 'Loopback review server is missing')
        before = hashlib.sha256(self.path.read_bytes()).hexdigest()
        server = web.create_server(self.path, port=0, fixture=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            root = 'http://127.0.0.1:' + str(server.server_port)
            with urllib.request.urlopen(root + '/api/story') as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(response.headers['Cache-Control'], 'no-store')
                self.assertEqual(json.load(response)['story']['next_episode'], 2)
            for target, headers, method, expected in (
                ('/api/story', {'Host': 'attacker.test'}, 'GET', 403),
                ('/api/story', {'Origin': 'https://attacker.test'}, 'GET', 403),
                ('/api/story', {'Sec-Fetch-Site': 'cross-site'}, 'GET', 403),
                ('/api/story', {}, 'POST', 405),
                ('/../../config.example.toml', {}, 'GET', 404),
                ('/api/generate', {}, 'GET', 404),
            ):
                request = urllib.request.Request(root + target, headers=headers, method=method)
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    urllib.request.urlopen(request)
                self.assertEqual(caught.exception.code, expected)
                caught.exception.close()
            self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(), before)
            with SQLiteRepository(self.path) as repo:
                repo.reject(self.pending.id, 'Author wants a different opening.')
            with urllib.request.urlopen(root + '/api/story') as response:
                view = json.load(response)
                self.assertEqual(view['episodes'][-1]['status'], 'rejected')
        finally:
            server.shutdown()
            server.server_close()
            thread.join(5)

    def test_review_assets_and_live_graph_are_served_without_database_writes(self):
        import threading
        import urllib.request
        from serial_story.review_web import create_server
        before = hashlib.sha256(self.path.read_bytes()).hexdigest()
        server = create_server(self.path, port=0, fixture=True, provider_info={'model': 'test/model', 'synthetic_sensitive_field': 'DO_NOT_EXPOSE_TEST_VALUE', 'generation_enabled': True})
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            root = 'http://127.0.0.1:' + str(server.server_port)
            with urllib.request.urlopen(root + '/api/provider') as response:
                public = response.read()
                self.assertNotIn(b'DO_NOT_EXPOSE_TEST_VALUE', public)
                import json
                self.assertFalse(json.loads(public)['generation_enabled'])
            for route, content in (('/', b'Review the story'), ('/review.js', b'textContent'),
                                   ('/review.css', b'prefers-reduced-motion'), ('/graph', b'Story memory')):
                with urllib.request.urlopen(root + route) as response:
                    self.assertEqual(response.status, 200)
                    self.assertIn(content, response.read())
                    self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')
                    self.assertIn('script-src', response.headers['Content-Security-Policy'])
            with urllib.request.urlopen(root + '/review.js') as response:
                source = response.read()
                self.assertNotIn(b'innerHTML', source)
                self.assertNotIn(b'eval(', source)
            self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(), before)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(5)

    def test_client_disconnect_does_not_attempt_a_second_error_response(self):
        from serial_story.review_web import create_server
        server = create_server(self.path, port=0, fixture=True)
        try:
            handler = object.__new__(server.RequestHandlerClass)
            handler.server = server
            handler.path = '/api/story'
            handler.headers = {'Host': f'127.0.0.1:{server.server_port}'}
            statuses = []
            handler.send_response = statuses.append
            handler.send_header = lambda *args: None
            handler.end_headers = lambda: None
            class Disconnected:
                def write(self, body):
                    raise ConnectionAbortedError('Injected disconnected local browser')
            handler.wfile = Disconnected()
            handler.do_GET()
            self.assertEqual(statuses, [200])
        finally:
            server.server_close()

    def test_missing_database_is_not_created(self):
        from serial_story.review_web import story_snapshot
        missing = Path(self.tmp.name) / 'missing.db'
        with self.assertRaises(FileNotFoundError):
            story_snapshot(missing)
        self.assertFalse(missing.exists())


if __name__ == '__main__':
    unittest.main()
