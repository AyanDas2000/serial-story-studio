"""Writable authoring-studio boundary: loopback only, explicit writes switch.

Fixed routes and assets, bounded JSON, session CSRF capability on every
mutation, per-request database connections. No request-selected paths, SQL,
commands or file handlers. Development server, not production hosting.
"""
import json
import logging
import secrets
import threading
import sqlite3
import socket
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, parse_qs

from ..records import StoryError
from ..repository import SQLiteRepository
from ..service import StoryService
from ..v1 import api as v1_api
from ..v1.provider import GenerationProvider, ScriptedProvider
from .store import Conflict, StudioStore

V1_LOG = logging.getLogger('serial_story.studio.v1')

ASSETS = Path(__file__).resolve().parents[2] / 'serial_story' / 'assets'
ROUTES = {
    '/': ('studio.html', 'text/html; charset=utf-8'),
    '/review.css': ('review.css', 'text/css; charset=utf-8'),
    '/studio.css': ('studio.css', 'text/css; charset=utf-8'),
    '/studio.js': ('studio.js', 'text/javascript; charset=utf-8'),
    '/studio-layout.js': ('studio-layout.js', 'text/javascript; charset=utf-8'),
    '/font.ttf': ('IBMPlexSans[wdth,wght].ttf', 'font/ttf'),
    '/v1': ('v1.html', 'text/html; charset=utf-8'),
    '/v1.css': ('v1.css', 'text/css; charset=utf-8'),
    '/v1.js': ('v1.js', 'text/javascript; charset=utf-8'),
}
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; font-src 'self'; "
       "connect-src 'self'; img-src 'self'; base-uri 'none'; form-action 'none'; "
       "frame-ancestors 'self'")
MAX_BODY = 262144
WRITES_OFF = b'{"message":"This studio opened read-only. Start it with --enable-writes to edit."}'
LOCAL_ONLY = b'{"message":"Open this studio on the local address."}'
UNAVAILABLE = b'{"message":"This page is not available."}'
INVALID_REQUEST = b'{"message":"This request is not available."}'
BAD_BODY = b'{"message":"The studio could not read that request. Reload the page and retry."}'
STALE = b'{"message":"Your edits are kept. The stored copy changed; refresh and reapply this action."}'


def _word_count(text: str) -> int:
    return len(text.split())


def _workspace(repo: SQLiteRepository, store: StudioStore, writable: bool,
               merge_catalog: bool) -> dict[str, Any]:
    story_row = repo.connection.execute("SELECT * FROM story WHERE id=1").fetchone()
    story = None if story_row is None else {
        'premise': story_row['premise'], 'next_episode': story_row['next_episode'],
        'history_revision': story_row['history_revision']}
    plan = repo.plan()
    plan_view = None
    if plan is not None:
        beats = plan.content.get('beats', [])
        plan_view = {'id': plan.id, 'status': plan.status, 'content': plan.content,
                     'established': [b for b in beats if story and b['episode'] < story['next_episode']],
                     'future': [b for b in beats if story and b['episode'] >= story['next_episode']],
                     'next_unplanned': next((b['episode'] for b in beats if b.get('unplanned')), None),
                     'feedback': store.plan_feedback(plan.id)}
    pending = store.pending_with_version()
    accepted = repo.accepted()
    memory_view = None
    if store.has_table('memory_meta') and story_row is not None:
        entities = [dict(r) for r in repo.connection.execute('SELECT id,name,kind,role FROM entities ORDER BY id')]
        names = {e['id']: e['name'] for e in entities}
        facts = [{**dict(r), 'subject_name': names.get(r['subject_id'], 'Entry')}
                 for r in repo.connection.execute('SELECT * FROM facts ORDER BY id')]
        memory_view = {'memory_revision': repo.memory_revision(), 'entities': entities,
                       'facts': facts, 'pending_fact_proposals': [f for f in facts if f['status'] == 'proposed']}
    return {
        'writable': writable, 'basis': store.basis(),
        'merge_catalog': merge_catalog,
        'generation_enabled': False,
        'story': story,
        'plan': plan_view,
        'pending': pending,
        'accepted': [{'revision_id': e.revision_id, 'number': e.number,
                      'words': _word_count(e.text), 'text': e.text, 'memory_review': 'not-reviewed'} for e in accepted],
        'settings': store.settings(),
        'receipts': store.receipts(),
        'memory': memory_view,
    }


def default_v1_provider() -> GenerationProvider:
    """The v1 desk is offline-only: no live route exists, so nothing here can spend."""
    return ScriptedProvider()


def create_server(path: Path, *, port: int = 8766, writes: bool = False,
                  merge_catalog: bool = False, merge_generation: bool = False, authoring_factory=None,
                  v1_path: Path | None = None, v1_provider: GenerationProvider | None = None):
    if merge_generation and not (writes and merge_catalog):
        raise ValueError("Paid startup requires explicit writes and catalog flags.")
    path = path.resolve()
    desk_api = v1_api.V1Api((v1_path or path.with_name(path.stem + '.v1.db')).resolve(),
                            v1_provider if v1_provider is not None else default_v1_provider())

    def authoring():
        from .authoring import MergeAuthoring
        return authoring_factory() if authoring_factory is not None else MergeAuthoring(enabled=merge_generation)

    def paid_action(method, store, service=None, payload=None):
        controller = authoring()
        try:
            if method == "recovery":
                return controller.recovery(store)
            return getattr(controller, method)(store, service, payload)
        finally:
            if controller._ledger is not None:
                controller._ledger.close()
    session_token = secrets.token_urlsafe(32)
    write_lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def version_string(self):
            return 'LocalStudio'

        def respond(self, status: int, body: bytes, kind: str = 'application/json'):
            self.close_connection = True
            self.send_response(status)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Security-Policy', CSP)
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            try:
                self.end_headers()
                self.wfile.write(body)
                self.wfile.flush()
                if status >= 400 and getattr(self, "command", None) == "POST":
                    self.drain_refused_body()
            except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                return

        def drain_refused_body(self):
            # Closing with unread inbound bytes can reset Windows TCP before the
            # refusal reaches the client. Never trust the rejected framing.
            end = time.monotonic() + 0.15
            drained = 0
            try:
                while time.monotonic() < end and drained < 2 * MAX_BODY:
                    self.connection.settimeout(max(0.001, end - time.monotonic()))
                    chunk = self.rfile.read1(min(65536, 2 * MAX_BODY - drained))
                    if not chunk:
                        break
                    drained += len(chunk)
            except OSError:
                pass  # Transport cleanup only; never represented as HTTP success.

        def allowed(self) -> bool:
            headers = getattr(self, 'headers', None)
            if headers is None:
                return False
            if hasattr(headers, 'get_all'):
                for name in ('Host', 'Origin', 'Referer', 'Sec-Fetch-Site', 'Content-Type', 'Content-Length', 'X-Studio-Token', 'Transfer-Encoding'):
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
            if getattr(self, 'command', None) == 'POST' and headers.get('Origin') != 'http://' + headers.get('Host', ''):
                return False
            return True

        def send_error(self, code, message=None, explain=None):
            if not self.allowed():
                self.respond(403, LOCAL_ONLY)
            else:
                self.respond(code, INVALID_REQUEST)

        def safe_target(self) -> str | None:
            requestline = getattr(self, 'requestline', None)
            target = requestline.split()[1] if requestline else self.path
            parsed = urlsplit(target)
            if not target.startswith('/') or target.startswith('//') or parsed.scheme or parsed.netloc:
                return None
            return parsed.path

        def open_story(self) -> tuple[SQLiteRepository, StoryService, StudioStore]:
            repo = SQLiteRepository(path)
            return repo, StoryService(repo), StudioStore(repo)

        def do_GET(self):
            if not self.allowed():
                self.respond(403, LOCAL_ONLY)
                return
            route = self.safe_target()
            if route is None:
                self.respond(404, UNAVAILABLE)
                return
            try:
                if route == '/api/session':
                    self.respond(200, json.dumps({'token': session_token,
                                                  'writable': writes}).encode())
                elif route == '/api/state':
                    if not writes and not path.exists():
                        body = json.dumps({'writable': False, 'story': None, 'plan': None, 'pending': None,
                                           'accepted': [], 'receipts': [], 'memory': None, 'settings': {},
                                           'basis': None, 'generation_enabled': False, 'merge_catalog': merge_catalog}).encode()
                    else:
                        repo = SQLiteRepository(path, read_only=not writes)
                        try:
                            if writes:
                                StoryService(repo)  # Initialize only in the explicitly writable boundary.
                            store = StudioStore(repo, initialize=writes)
                            repo.connection.execute('BEGIN')
                            view = _workspace(repo, store, writes, merge_catalog)
                            view['generation_enabled'] = merge_generation
                            if merge_generation:
                                view['merge_accounting'] = paid_action('recovery', store)
                            body = json.dumps(view, ensure_ascii=True).encode()
                            repo.connection.execute('ROLLBACK')
                        finally:
                            repo.connection.close()
                    self.respond(200, body)
                elif route in ('/api/merge/catalog', '/api/merge/model') and merge_catalog:
                    from .merge import MergeGateway, MergeGatewayError, urllib_transport
                    try:
                        query = parse_qs(urlsplit(self.path).query, keep_blank_values=True)
                        if route == '/api/merge/model':
                            if set(query) != {'model'} or len(query['model']) != 1:
                                raise MergeGatewayError('Supply exactly one canonical model ID.')
                            selected_model = query['model'][0]
                        else:
                            if query:
                                raise MergeGatewayError('The scoped catalog does not accept extra options.')
                            selected_model = None
                        controller = authoring()
                        try:
                            models = controller.gateway.catalog(model=selected_model)
                        finally:
                            if controller._ledger is not None:
                                controller._ledger.close()
                        if selected_model is not None and (len(models) != 1 or models[0]['model'] != selected_model):
                            raise MergeGatewayError('Exact lookup did not return the requested model.')
                    except MergeGatewayError as problem:
                        self.respond(400, json.dumps({'message': str(problem)}).encode())
                    else:
                        self.respond(200, json.dumps({'models': models}).encode())
                elif route in ('/api/merge/catalog', '/api/merge/model'):
                    self.respond(403, json.dumps({'message':
                        'Connect Merge at startup with the catalog option to list models.'}).encode())
                elif route == '/api/v1/state':
                    self.v1_respond('GET', route, 200, desk_api.state())
                elif route == '/api/v1/context':
                    query = parse_qs(urlsplit(self.path).query, keep_blank_values=True)
                    boundary = query.get('boundary', [''])
                    if set(query) != {'boundary'} or len(boundary) != 1 or not boundary[0].isdigit() or len(boundary[0]) > 6:
                        self.v1_respond('GET', route, 400, {'message': 'Choose the last accepted episode to continue from.'})
                    else:
                        try:
                            self.v1_respond('GET', route, 200, desk_api.context(int(boundary[0])))
                        except v1_api.Refused as refusal:
                            self.v1_respond('GET', route, 400, {'code': refusal.code, 'message': str(refusal), 'detail': refusal.detail})
                elif route in ROUTES:
                    filename, kind = ROUTES[route]
                    data = (ASSETS / filename).read_bytes()
                    if route in ('/', '/v1'):
                        data = data.replace(b'content=""', b'content="' + session_token.encode() + b'"', 1)
                    self.respond(200, data, kind)
                else:
                    self.respond(404, UNAVAILABLE)
            except (OSError, StoryError, sqlite3.Error):
                self.respond(503, UNAVAILABLE)

        def read_body(self) -> dict[str, Any] | None:
            if self.headers.get('Transfer-Encoding') is not None:
                self.respond(400, BAD_BODY)
                return None
            if self.headers.get('Content-Type', '').lower() not in ('application/json', 'application/json; charset=utf-8'):
                self.respond(415, BAD_BODY)
                return None
            length_header = self.headers.get('Content-Length', '')
            if len(length_header) > 7 or not length_header.isascii() or not length_header.isdigit():
                self.respond(400, BAD_BODY)
                return None
            length = int(length_header)
            if length > MAX_BODY:
                self.respond(413, BAD_BODY)
                return None
            deadline = time.monotonic() + 1.5
            raw = bytearray()
            try:
                while len(raw) < length:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError()
                    self.connection.settimeout(min(remaining, 0.5))
                    chunk = self.rfile.read1(min(length - len(raw), 65536))
                    if not chunk:
                        raise ValueError()
                    raw.extend(chunk)
                def unique_object(pairs):
                    result = {}
                    for key, value in pairs:
                        if key in result:
                            raise ValueError()
                        result[key] = value
                    return result
                def reject_constant(value):
                    raise ValueError()
                parsed = json.loads(raw.decode('utf-8'), object_pairs_hook=unique_object, parse_constant=reject_constant)
                if not isinstance(parsed, dict):
                    raise ValueError()
            except (ValueError, UnicodeDecodeError, TimeoutError, OSError, RecursionError):
                self.respond(400, BAD_BODY)
                return None
            return parsed

        def v1_respond(self, method: str, route: str, status: int, body: dict[str, Any]):
            V1_LOG.info('%s %s %d %s', method, route, status, body.get('code', '') if status >= 400 else '')
            self.respond(status, json.dumps(body, ensure_ascii=True).encode())

        def v1_post(self, route: str, command: str, payload: dict[str, Any]):
            # Not under write_lock: the desk commits in short BEGIN IMMEDIATE
            # transactions and runs every provider exchange outside them.
            try:
                status, body = desk_api.command(command, payload)
            except StoryError as problem:
                status, body = 400, {'message': str(problem)}
            except (OSError, ValueError, KeyError, TypeError, sqlite3.Error):
                V1_LOG.exception('POST %s failed', route)
                status, body = 500, {'message': 'The desk could not finish that action. Reload to see the saved copy before retrying.'}
            self.v1_respond('POST', route, status, body)

        def do_POST(self):
            if not self.allowed():
                self.respond(403, LOCAL_ONLY)
                return
            route = self.safe_target()
            if not writes:
                self.respond(403, WRITES_OFF)
                return
            v1_command = route[len('/api/v1/'):] if route is not None and route.startswith('/api/v1/') else None
            if v1_command not in v1_api.NAMES and (route is None or route not in self.MUTATIONS):
                self.respond(404, UNAVAILABLE)
                return
            if self.headers.get('X-Studio-Token') != session_token:
                self.respond(403, INVALID_REQUEST)
                return
            payload = self.read_body()
            if payload is None:
                return
            if v1_command is not None:
                self.v1_post(route, v1_command, payload)
                return
            with write_lock:
                repo = None
                try:
                    repo, service, store = self.open_story()
                    result = self.MUTATIONS[route](self, payload, repo, service, store)
                    status, body = result
                    self.respond(status, json.dumps(body, ensure_ascii=True).encode())
                except Conflict as problem:
                    self.respond(409, json.dumps({'message': str(problem)}).encode())
                except StoryError as problem:
                    self.respond(400, json.dumps({'message': str(problem)}).encode())
                except (OSError, ValueError, KeyError, TypeError, sqlite3.Error):
                    self.respond(500, b'{"message":"The studio could not finish that action. Compare the current saved copy before retrying."}')
                finally:
                    if repo is not None:
                        repo.connection.close()

        def _setup(self, payload, repo, service, store):
            premise = payload.get('premise')
            if not isinstance(premise, str):
                raise StoryError('Describe your story premise in a few words.')
            if set(payload) != {'premise'}:
                raise StoryError('Only a premise is needed to start a story.')
            service.initialize(premise)
            return 200, {'saved': True}

        def _save_settings(self, payload, repo, service, store):
            allowed_fields = {'provider', 'model', 'vendor', 'prompt_template',
                              'output_limit_words', 'feedback_scope'}
            if not set(payload) <= {'expected_version'} | allowed_fields:
                raise StoryError('That settings field is not recognized.')
            updated = store.save_settings(
                payload.get('expected_version'),
                **{k: payload[k] for k in allowed_fields if k in payload})
            return 200, {'settings': updated}

        def _save_plan(self, payload, repo, service, store):
            content = payload.get('content')
            plan = store.save_plan(content, payload.get('expected_plan_id'))
            return 200, {'plan_id': plan.id, 'status': plan.status}

        def _approve_plan(self, payload, repo, service, store):
            plan_id = payload.get('plan_id')
            if not isinstance(plan_id, int) or isinstance(plan_id, bool):
                raise StoryError('Read the current plan and use its ID.')
            plan = store.approve_plan(plan_id)
            return 200, {'plan_id': plan.id, 'status': plan.status}

        def _plan_feedback(self, payload, repo, service, store):
            if set(payload) != {'plan_id', 'note'} or type(payload.get('plan_id')) is not int:
                raise StoryError('Feedback requires the ID of the plan you loaded.')
            note = payload.get('note')
            if not isinstance(note, str):
                raise StoryError('Write the plan feedback in words.')
            store.add_plan_feedback(payload['plan_id'], note)
            return 200, {'saved': True}

        def _save_draft(self, payload, repo, service, store):
            if set(payload) != {'text', 'basis'}:
                raise StoryError('Saving a new draft requires prose and the loaded story versions.')
            revision_id = store.save_manual(payload['text'], payload['basis'])
            return 200, {'revision_id': revision_id}

        def _edit_draft(self, payload, repo, service, store):
            revision_id = payload.get('revision_id')
            text = payload.get('text')
            expected = payload.get('expected_text_version')
            if not isinstance(revision_id, int) or not isinstance(expected, int) \
                    or isinstance(revision_id, bool) or isinstance(expected, bool):
                raise StoryError('Reload the draft and retry the save.')
            if not isinstance(text, str):
                raise StoryError('The manuscript must be text.')
            version = store.save_pending_edit(revision_id, text, expected)
            return 200, {'text_version': version}

        def _draft_feedback(self, payload, repo, service, store):
            if set(payload) != {'revision_id', 'expected_text_version', 'basis', 'scope', 'note'}:
                raise StoryError('Feedback requires its saved source version and loaded story versions.')
            store.add_episode_feedback(payload['revision_id'], payload['scope'], payload['note'],
                                       payload['expected_text_version'], payload['basis'])
            return 200, {'saved': True, 'feedback_revision': store.basis()['feedback_revision']}

        def _generate(self, payload, repo, service, store):
            return 200, store.generate(service, payload)

        def _revise(self, payload, repo, service, store):
            return 200, store.generate(service, payload, revise=True)

        def _merge_preflight(self, payload, repo, service, store):
            return 200, paid_action('preflight', store, service, payload)

        def _merge_confirm(self, payload, repo, service, store):
            return 200, paid_action('confirm', store, service, payload)

        def _accept(self, payload, repo, service, store):
            return 200, store.accept(payload)

        def _reject(self, payload, repo, service, store):
            if set(payload) not in ({'revision_id', 'expected_text_version', 'basis'},
                                    {'revision_id', 'expected_text_version', 'basis', 'note'}):
                raise StoryError('Rejection requires the draft ID, saved text version and loaded story versions.')
            revision_id = payload['revision_id']
            note = payload.get('note', '')
            if not isinstance(note, str):
                raise StoryError('Write the rejection note in words.')
            with repo.transaction():
                store.check_pending(revision_id, payload['expected_text_version'], payload['basis'],
                                    require_original_plan=False)
                repo.reject(revision_id, note)
            return 200, {'rejected': revision_id}

        def _confirm_fact(self, payload, repo, service, store):
            fact_id = payload.get('fact_id')
            if not isinstance(fact_id, int) or isinstance(fact_id, bool):
                raise StoryError('Read the memory proposals and use the fact ID.')
            if service.memory is None:
                raise StoryError('Memory is not available for this database.')
            fact = service.memory.confirm_fact(fact_id)
            return 200, {'fact_id': fact.id, 'status': fact.status,
                         'memory_revision': service.memory.revision()}

        def _reject_fact(self, payload, repo, service, store):
            if type(payload.get('fact_id')) is not int or not isinstance(payload.get('note', ''), str):
                raise StoryError('Choose the memory proposal and write an optional rejection note.')
            fact = service.memory.reject_fact(payload['fact_id'], payload.get('note', ''))
            return 200, {'fact_id': fact.id, 'status': fact.status}

        def _add_entity(self, payload, repo, service, store):
            name, kind = payload.get('name'), payload.get('kind')
            role = payload.get('role', '')
            if not isinstance(name, str) or not isinstance(kind, str) or not isinstance(role, str):
                raise StoryError('Name the entry and choose what kind of thing it is.')
            entity = service.memory.add_entity(name.strip(), kind.strip(), role.strip())
            return 200, {'entity_id': entity.id, 'name': entity.name, 'kind': entity.kind}

        def _propose_fact(self, payload, repo, service, store):
            fields = ('subject_id', 'predicate', 'value', 'source_revision_id', 'evidence')
            if any(not isinstance(payload.get(f), (str, int)) or payload.get(f) is None for f in fields):
                raise StoryError('A memory fact needs the entity, its property, the value and the exact evidence.')
            fact = service.memory.propose_fact(
                payload['subject_id'], payload['predicate'], payload['value'],
                payload['source_revision_id'], payload['evidence'])
            return 200, {'fact_id': fact.id, 'status': fact.status}

        MUTATIONS = {
            '/api/merge/preflight': _merge_preflight,
            '/api/merge/confirm': _merge_confirm,
            '/api/setup': _setup,
            '/api/settings': _save_settings,
            '/api/plan/save': _save_plan,
            '/api/plan/approve': _approve_plan,
            '/api/plan/feedback': _plan_feedback,
            '/api/draft/save': _save_draft,
            '/api/draft/generate': _generate,
            '/api/draft/revise': _revise,
            '/api/draft/edit': _edit_draft,
            '/api/draft/feedback': _draft_feedback,
            '/api/accept': _accept,
            '/api/reject': _reject,
            '/api/memory/confirm': _confirm_fact,
            '/api/memory/reject': _reject_fact,
            '/api/memory/entity': _add_entity,
            '/api/memory/fact': _propose_fact,
        }

        def do_PUT(self):
            self._refuse_edit_methods()

        def _refuse_edit_methods(self):
            if not self.allowed():
                self.respond(403, LOCAL_ONLY)
            else:
                self.respond(405, INVALID_REQUEST)

        do_DELETE = do_PUT
        do_PATCH = do_PUT
        do_OPTIONS = do_PUT
        do_HEAD = do_PUT
        do_TRACE = do_PUT
        do_CONNECT = do_PUT

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


