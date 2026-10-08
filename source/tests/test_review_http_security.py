"""Behavioral checks of the local, read-only HTTP boundary."""
import hashlib
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from serial_story.repository import SQLiteRepository
from serial_story.service import StoryService
from serial_story.review_web import create_server


class ReviewHttpSecurityTests(unittest.TestCase):
    def setUp(self):
        scratch = Path('C:/Users/ayan1/AppData/Local/hermes/cache/scratch/story-polish-20261001')
        self.tmp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'story.db'
        with SQLiteRepository(self.path) as repo:
            StoryService(repo).initialize('Private lighthouse story.')

    def start_server(self, provider_info=None):
        server = create_server(self.path, port=0, provider_info=provider_info)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def stop():
            server.shutdown()
            server.server_close()
            thread.join(5)
        self.addCleanup(stop)
        return server

    def request(self, server, route='/api/provider', method='GET', headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
        try:
            connection.request(method, route, headers=headers or {})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_provider_metadata_rejects_nested_values_and_invalid_prices(self):
        server = self.start_server({
            'model': {'api_key': 'DO_NOT_EXPOSE'},
            'display_name': ['DO_NOT_EXPOSE'],
            'checked_at': 42,
            'vendor_for_rates': 'catalog vendor',
            'availability': {'token': 'DO_NOT_EXPOSE'},
            'advertised_streaming': 'false',
            'api_key': 'DO_NOT_EXPOSE',
            'pricing': {'currency': {'password': 'DO_NOT_EXPOSE'},
                        'input_per_million': True, 'output_per_million': -1,
                        'cache_read_per_million': float('nan'),
                        'cache_write_per_million': float('inf'),
                        'secret': 'DO_NOT_EXPOSE'},
            'generation_enabled': True,
        })
        status, _, body = self.request(server)
        self.assertEqual(status, 200)
        public = json.loads(body)
        self.assertNotIn(b'DO_NOT_EXPOSE', body)
        for field in ('model', 'display_name', 'checked_at', 'availability', 'advertised_streaming'):
            self.assertNotIn(field, public)
        self.assertEqual(public['vendor_for_rates'], 'catalog vendor')
        self.assertEqual(public['pricing'], {})
        self.assertFalse(public['generation_enabled'])
        self.assertEqual(public['inference_calls'], 0)
        self.assertFalse(public['cache_hits_measured'])

    def test_hostile_headers_cannot_disclose_data_on_any_method(self):
        server = self.start_server()
        for method in ('GET', 'HEAD', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'TRACE', 'CONNECT', 'UNRECOGNIZED'):
            for headers in ({'Host': 'attacker.test'},
                            {'Origin': 'https://attacker.test'},
                            {'Referer': 'https://attacker.test/story'},
                            {'Sec-Fetch-Site': 'cross-site'}):
                with self.subTest(method=method, headers=headers):
                    status, response_headers, body = self.request(server, '/api/story', method, headers)
                    self.assertEqual(status, 403)
                    self.assertNotIn(b'Private lighthouse story', body)
                    self.assertEqual(response_headers.get('Cache-Control'), 'no-store')
                    self.assertEqual(response_headers.get('X-Content-Type-Options'), 'nosniff')
                    self.assertIn('script-src', response_headers.get('Content-Security-Policy', ''))
                    self.assertNotIn('Python', response_headers.get('Server', ''))
                    self.assertNotIn('BaseHTTP', response_headers.get('Server', ''))

    def test_unsupported_methods_have_generic_errors_and_security_headers(self):
        server = self.start_server()
        for method in ('POST', 'HEAD', 'TRACE', 'CONNECT', 'UNRECOGNIZED'):
            with self.subTest(method=method):
                status, headers, body = self.request(server, '/api/story', method)
                self.assertIn(status, (405, 501))
                self.assertEqual(headers.get('Content-Type'), 'application/json')
                self.assertEqual(headers.get('Cache-Control'), 'no-store')
                self.assertEqual(headers.get('X-Content-Type-Options'), 'nosniff')
                self.assertEqual(headers.get('Referrer-Policy'), 'no-referrer')
                self.assertNotIn(b'UNRECOGNIZED', body)
                self.assertNotIn(b'Private lighthouse story', body)
                self.assertNotIn('Python', headers.get('Server', ''))
                self.assertNotIn('BaseHTTP', headers.get('Server', ''))

    def test_exact_module_routes_serve_javascript_not_arbitrary_files(self):
        from unittest.mock import patch
        from serial_story.review import server as transport
        assets = Path(self.tmp.name) / 'assets'
        (assets / 'ui').mkdir(parents=True)
        names = ('dom', 'reader', 'planning', 'evidence', 'review-details')
        for name in names:
            (assets / 'ui' / f'{name}.js').write_text(f'export const name = "{name}";', encoding='utf-8')
        (assets / 'ui' / 'private.js').write_text('PRIVATE_ASSET', encoding='utf-8')
        server = self.start_server()
        with patch.object(transport, 'ASSETS', assets):
            for name in names:
                with self.subTest(module=name):
                    status, headers, body = self.request(server, f'/ui/{name}.js')
                    self.assertEqual(status, 200)
                    self.assertEqual(headers.get('Content-Type'), 'text/javascript; charset=utf-8')
                    self.assertEqual(body, (assets / 'ui' / f'{name}.js').read_bytes())
            for route in ('/ui/private.js', '/ui/../private.js', '/ui/%2e%2e/private.js',
                          '/ui/dom.js/extra', '/ui/dom.js.bak', '/ui/', '/provider.py'):
                with self.subTest(route=route):
                    status, headers, body = self.request(server, route)
                    self.assertEqual(status, 404)
                    self.assertEqual(headers.get('X-Content-Type-Options'), 'nosniff')
                    self.assertNotIn(b'PRIVATE_ASSET', body)

    def test_absolute_request_targets_do_not_bypass_fixed_routes(self):
        server = self.start_server()
        for route in ('http://attacker.test/api/story', '//attacker.test/api/story', '//api/story'):
            with self.subTest(route=route):
                # Isolate request-target validation from http.client's auto Host.
                status, _, body = self.request(server, route, headers={
                    'Host': f'127.0.0.1:{server.server_port}'})
                self.assertEqual(status, 404)
                self.assertNotIn(b'Private lighthouse story', body)


if __name__ == '__main__':
    unittest.main()
