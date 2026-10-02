"""Security boundary of the NEW writable authoring studio (loopback only)."""
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from serial_story.studio.server import create_server

REPO = Path(__file__).resolve().parents[1]
RUNS = REPO / 'local' / 'test-runs'


class StudioBoundaryTests(unittest.TestCase):
    def setUp(self):
        RUNS.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=RUNS)
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'studio.db'
        self.writes = False

    def start_server(self):
        server = create_server(self.path, port=0, writes=self.writes)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def stop():
            server.shutdown()
            server.server_close()
            thread.join(5)
        self.addCleanup(stop)
        return server

    def token(self, server):
        status, _, body = self.request(server, '/api/session')
        self.assertEqual(status, 200)
        return json.loads(body)['token']

    def request(self, server, route, method='GET', headers=None, body=None):
        connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
        try:
            connection.request(method, route, body=body, headers=headers or {})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def post(self, server, route, payload=None, token='missing', headers=None, raw=None):
        body = raw if raw is not None else json.dumps(payload or {}).encode()
        merged = {'Content-Type': 'application/json', 'X-Studio-Token': token,
                  'Origin': f'http://127.0.0.1:{server.server_port}'}
        merged.update(headers or {})
        return self.request(server, route, 'POST', merged, body)

    def test_repeated_refusals_have_no_effect_and_valid_requests_succeed(self):
        from unittest.mock import patch
        self.writes = True
        server = self.start_server()
        token = self.token(server)
        with patch('serial_story.studio.merge.MergeGateway.catalog', side_effect=AssertionError('No provider access')):
            for index in range(20):
                for headers, capability in (({'Origin': 'https://attacker.test'}, token), ({}, 'wrong')):
                    self.assertEqual(self.post(server, '/api/setup', {'premise': 'Rejected'}, capability, headers=headers)[0], 403)
                    self.assertFalse(self.path.exists())
                self.assertEqual(self.request(server, '/api/session')[0], 200)
            self.assertEqual(self.post(server, '/api/setup', {'premise': 'Synthetic valid'}, token)[0], 200)
            for index in range(20):
                self.assertEqual(self.request(server, '/api/state')[0], 200)

    def test_read_only_state_does_not_create_database(self):
        server = self.start_server()
        status, _, body = self.request(server, '/api/state')
        self.assertEqual(status, 200)
        self.assertIsNone(json.loads(body)['story'])
        self.assertFalse(self.path.exists(), 'Read-only reads must not create a database.')
        self.assertEqual(self.request(server, '/review.css')[0], 200)

    def test_mutation_requires_origin_and_json_type(self):
        self.writes = True
        server = self.start_server()
        token = self.token(server)
        body = json.dumps({'premise': 'Untrusted'}).encode()
        status, _, _ = self.request(server, '/api/setup', 'POST',
                  {'X-Studio-Token': token, 'Content-Type': 'application/json'}, body)
        self.assertEqual(status, 403)
        status, _, _ = self.post(server, '/api/setup', {'premise': 'Untrusted'}, token,
                                 headers={'Content-Type': 'text/plain'})
        self.assertEqual(status, 415)
        self.assertFalse(self.path.exists())

    def test_ambiguous_headers_and_slow_bodies_are_bounded(self):
        import socket
        import time
        self.writes = True
        server = self.start_server()
        token = self.token(server)
        base = f'POST /api/setup HTTP/1.1\r\nHost: 127.0.0.1:{server.server_port}\r\nOrigin: http://127.0.0.1:{server.server_port}\r\nContent-Type: application/json\r\nX-Studio-Token: {token}\r\n'
        cases = [('Content-Length: 20\r\nContent-Length: 20\r\n', 403),
                 (f'Content-Length: 20\r\nX-Studio-Token: {token}\r\n', 403),
                 ('Content-Length: 20\r\nTransfer-Encoding: chunked\r\n', 400),
                 ('Content-Length: 999999\r\n', 413),
                 ('Content-Length: 100\r\n', 400),
                 ('Content-Length: -2\r\n', 400)]
        for header, expected in cases:
            with self.subTest(header=header), socket.create_connection(('127.0.0.1', server.server_port), timeout=3) as sock:
                started = time.monotonic()
                sock.sendall((base + header + '\r\n').encode())
                reply = sock.recv(4096)
                self.assertIn(f' {expected} '.encode(), reply)
                self.assertLess(time.monotonic() - started, 2.0)
        self.assertFalse(self.path.exists())

    def test_read_only_existing_database_bytes_and_schema_do_not_change(self):
        from serial_story.repository import SQLiteRepository
        with SQLiteRepository(self.path) as repo:
            repo.initialize('Only a canonical database, no studio migrations.')
        before = self.path.read_bytes()
        server = self.start_server()
        self.assertEqual(self.request(server, '/api/state')[0], 200)
        self.assertEqual(self.path.read_bytes(), before)

    def test_reads_serve_without_writes(self):
        server = self.start_server()
        status, headers, body = self.request(server, '/api/state')
        self.assertEqual(status, 200)
        state = json.loads(body)
        self.assertFalse(state['writable'])

    def test_setup_requires_explicit_writes_switch(self):
        server = self.start_server()
        token = self.token(server)
        status, _, body = self.post(server, '/api/setup', {'premise': 'A lighthouse story.'}, token)
        self.assertEqual(status, 403)
        self.assertNotIn(b'lighthouse', body)
        status, _, body = self.request(server, '/api/state')
        self.assertFalse(json.loads(body)['writable'])

    def test_setup_saves_premise_with_valid_token(self):
        self.writes = True
        server = self.start_server()
        token = self.token(server)
        status, _, body = self.post(server, '/api/setup', {'premise': 'A lighthouse story.'}, token)
        self.assertEqual(status, 200)
        _, _, body = self.request(server, '/api/state')
        state = json.loads(body)
        self.assertEqual(state['story']['premise'], 'A lighthouse story.')
        self.assertTrue(state['writable'])

    def test_missing_or_wrong_token_is_refused(self):
        self.writes = True
        server = self.start_server()
        self.token(server)
        for token in ('missing', 'wrong-token'):
            with self.subTest(token=token):
                status, _, _ = self.post(server, '/api/setup', {'premise': 'P'}, token)
                self.assertEqual(status, 403)
        _, _, body = self.request(server, '/api/state')
        self.assertIsNone(json.loads(body)['story'])

    def test_foreign_origin_is_refused(self):
        self.writes = True
        server = self.start_server()
        status, _, _ = self.post(server, '/api/setup', {'premise': 'P'}, 'x',
                                 headers={'Origin': 'https://attacker.test'})
        self.assertEqual(status, 403)

    def test_duplicate_host_header_is_refused(self):
        self.writes = True
        server = self.start_server()
        connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
        try:
            body = json.dumps({'premise': 'P'}).encode()
            connection.putrequest('POST', '/api/setup')
            connection.putheader('Host', f'127.0.0.1:{server.server_port}')
            connection.putheader('Host', f'127.0.0.1:{server.server_port}')
            connection.putheader('Content-Type', 'application/json')
            connection.putheader('Content-Length', str(len(body)))
            connection.endheaders(body)
            response = connection.getresponse()
            status, body = response.status, response.read()
        finally:
            connection.close()
        self.assertEqual(status, 403)
        self.assertNotIn(b'P', body)

    def test_unsupported_methods_and_targets_are_refused(self):
        self.writes = True
        server = self.start_server()
        token = self.token(server)
        for method, route, headers in (
            ('TRACE', '/api/setup', {}),
            ('POST', 'http://attacker.test/api/setup', {'Host': f'127.0.0.1:{server.server_port}'}),
            ('POST', '//attacker.test/api/setup', {'Host': f'127.0.0.1:{server.server_port}'}),
            ('POST', '/serial_story/repository.py', {}),
            ('DELETE', '/api/setup', {}),
        ):
            with self.subTest(method=method, route=route):
                status, _, _ = self.request(server, route, method, headers)
                self.assertIn(status, (403, 404, 405))

    def test_invalid_request_bodies_fail_generically(self):
        self.writes = True
        server = self.start_server()
        token = self.token(server)
        cases = [
            ('not json', b'{broken'),
            ('array body', b'[]'),
            ('wrong premise type', json.dumps({'premise': 7}).encode()),
            ('empty premise', json.dumps({'premise': '   '}).encode()),
            ('unexpected field', json.dumps({'premise': 'P', 'db': 'other.db'}).encode()),
            ('oversized body', b'{"premise":"' + b'x' * 300000 + b'"}'),
        ]
        for label, raw in cases:
            with self.subTest(body=label):
                status, _, body = self.post(server, '/api/setup', raw=raw, token=token)
                self.assertIn(status, (400, 413))
                self.assertNotIn(b'Traceback', body)


if __name__ == '__main__':
    unittest.main()
