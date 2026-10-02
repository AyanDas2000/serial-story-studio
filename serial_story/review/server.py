"""Fixed-route loopback development HTTP server, not production hosting."""
import html
import json
import re
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .provider import public_provider_info
from .snapshot import live_graph, story_snapshot


ASSETS = Path(__file__).resolve().parents[1] / 'assets'
ROUTES = {
    '/': ('review.html', 'text/html; charset=utf-8'),
    '/review.css': ('review.css', 'text/css; charset=utf-8'),
    '/review.js': ('review.js', 'text/javascript; charset=utf-8'),
    '/ui/dom.js': ('ui/dom.js', 'text/javascript; charset=utf-8'),
    '/ui/reader.js': ('ui/reader.js', 'text/javascript; charset=utf-8'),
    '/ui/planning.js': ('ui/planning.js', 'text/javascript; charset=utf-8'),
    '/ui/evidence.js': ('ui/evidence.js', 'text/javascript; charset=utf-8'),
    '/ui/review-details.js': ('ui/review-details.js', 'text/javascript; charset=utf-8'),
    '/font.ttf': ('IBMPlexSans[wdth,wght].ttf', 'font/ttf'),
}
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; font-src 'self'; "
       "connect-src 'self'; frame-src 'self'; img-src 'self'; base-uri 'none'; "
       "form-action 'none'; frame-ancestors 'self'")
LOCAL_ONLY = b'{"message":"Open this review on the local address."}'
UNAVAILABLE = b'{"message":"This review page is not available."}'
READ_FAILED = b'{"message":"Could not read the selected story. Check it locally, then retry."}'
READ_ONLY = b'{"message":"This review cannot edit stories or generate text."}'
INVALID_REQUEST = b'{"message":"This review request is not available."}'


def create_server(path: Path, *, port: int = 8765, fixture: bool = False,
                  provider_info: dict | None = None):
    path = path.resolve(strict=True)
    public_info = public_provider_info(provider_info)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def version_string(self):
            return 'LocalReview'

        def respond(self, status: int, body: bytes, kind: str = 'application/json',
                    policy: str = CSP):
            self.close_connection = True
            self.send_response(status)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Security-Policy', policy)
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            try:
                self.end_headers()
                if getattr(self, 'command', None) != 'HEAD':
                    self.wfile.write(body)
            except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                # Never try a second response to a disconnected local client.
                return

        def allowed(self):
            headers = getattr(self, 'headers', None)
            if headers is None:
                return False
            if hasattr(headers, 'get_all'):
                for name in ('Host', 'Origin', 'Referer', 'Sec-Fetch-Site'):
                    if len(headers.get_all(name, [])) > 1:
                        return False
            port = self.server.server_address[1]
            hosts = {f'127.0.0.1:{port}', f'localhost:{port}'}
            origins = {'http://' + host for host in hosts}
            if (headers.get('Host') not in hosts or
                    headers.get('Origin') not in (None, *origins) or
                    headers.get('Sec-Fetch-Site') not in (None, 'none', 'same-origin')):
                return False
            referer = headers.get('Referer')
            if referer is not None:
                try:
                    source = urlsplit(referer)
                except ValueError:
                    return False
                if source.scheme != 'http' or source.netloc not in hosts:
                    return False
            return True

        def send_error(self, code, message=None, explain=None):
            # Also covers stdlib parser errors and arbitrary unsupported methods.
            # Never reflect its default exception/method text or HTML details.
            if not self.allowed():
                self.respond(403, LOCAL_ONLY)
            else:
                self.respond(code, INVALID_REQUEST)

        def do_GET(self):
            if not self.allowed():
                self.respond(403, LOCAL_ONLY)
                return
            try:
                # BaseHTTPRequestHandler normalizes leading // in self.path.
                # Validate the original target before resolving any fixed route.
                requestline = getattr(self, 'requestline', None)
                target = requestline.split()[1] if requestline else self.path
                parsed = urlsplit(target)
                if not target.startswith('/') or target.startswith('//') or parsed.scheme or parsed.netloc:
                    self.respond(404, UNAVAILABLE)
                    return
                route = parsed.path
                if route == '/api/story':
                    body = json.dumps(story_snapshot(path, fixture=fixture), ensure_ascii=True).encode()
                    self.respond(200, body)
                elif route == '/api/provider':
                    self.respond(200, json.dumps(public_info, allow_nan=False).encode())
                elif route in ROUTES:
                    filename, kind = ROUTES[route]
                    self.respond(200, (ASSETS / filename).read_bytes(), kind)
                elif route == '/graph':
                    body = live_graph(path)
                    match = re.search(r'<meta http-equiv="Content-Security-Policy" content="([^"]+)"', body)
                    if not match:
                        raise ValueError('Graph security policy missing')
                    # Preserve the graph builder's exact hashed-script policy.
                    policy = html.unescape(match[1]) + "; frame-ancestors 'self'"
                    self.respond(200, body.encode(), 'text/html; charset=utf-8', policy)
                else:
                    self.respond(404, UNAVAILABLE)
            except (OSError, sqlite3.Error, ValueError, KeyError):
                self.respond(503, READ_FAILED)

        def do_POST(self):
            if not self.allowed():
                self.respond(403, LOCAL_ONLY)
            else:
                self.respond(405, READ_ONLY)

        do_PUT = do_POST
        do_DELETE = do_POST
        do_PATCH = do_POST
        do_OPTIONS = do_POST
        do_HEAD = do_POST
        do_TRACE = do_POST
        do_CONNECT = do_POST

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)
