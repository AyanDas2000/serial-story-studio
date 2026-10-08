"""The shelf: several series in one app, each with its own database and nothing shared."""
import http.client
import json
import re
import tempfile
import threading
import unittest
from pathlib import Path

from serial_story.records import StoryError
from serial_story.studio.server import create_server
from serial_story.v1.provider import ScriptedProvider
from serial_story.v1.shelf import SAMPLE_MARKER, Shelf, clean_title

REPO = Path(__file__).resolve().parents[1]
RUNS = REPO / 'local' / 'test-runs'
SAMPLE = REPO / 'serial_story' / 'samples' / 'court-recorder.sample'
WEB = REPO / 'serial_story' / 'v1' / 'web'


class ShelfCase(unittest.TestCase):
    def make(self, sample=None):
        RUNS.mkdir(parents=True, exist_ok=True)
        tmp = tempfile.TemporaryDirectory(dir=RUNS)
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / 'stories'
        self.shelf = Shelf(self.root, ScriptedProvider, sample=sample)
        self.addCleanup(self.shelf.close)
        return self.shelf


class ShelfTest(ShelfCase):
    def test_titles_are_cleaned_and_bad_ones_refused(self):
        self.assertEqual(clean_title('  Night   shift  '), 'Night shift')
        self.assertEqual(clean_title('two\nlines'), 'two lines')
        for bad in ('', '   ', None, 7, 'x' * 81, 'bell\x07name', 'nul\x00name'):
            with self.assertRaises(StoryError, msg=repr(bad)):
                clean_title(bad)

    def test_create_makes_unique_folders_with_their_own_files(self):
        shelf = self.make()
        a, b, c = shelf.create('Night Shift'), shelf.create('Night Shift'), shelf.create('!!!')
        self.assertEqual((a, b), ('night-shift', 'night-shift-2'))
        self.assertEqual(c, 'series')
        self.assertEqual(len({shelf.desk(s).path for s in (a, b, c)}), 3)
        for s in (a, b, c):
            self.assertEqual(shelf.desk(s).path.parent, self.root / s)

    def test_unknown_or_hostile_names_open_nothing(self):
        shelf = self.make()
        shelf.create('Real')
        for slug in ('missing', '..', '../real', 'Real', 'real/..', '', 'a' * 60, None):
            self.assertIsNone(shelf.desk(slug), repr(slug))

    def test_the_sample_is_offered_once(self):
        self.assertTrue(SAMPLE.is_file(), 'the sample story must ship with the program')
        shelf = self.make(SAMPLE)
        self.assertEqual([r['title'] for r in shelf.listing()], ['The Court Recorder'])
        row = shelf.listing()[0]
        self.assertTrue(row['sample'] and row['started'])
        self.assertEqual((row['approved'], row['planned']), (6, 6))
        self.assertGreater(row['facts'], 0)
        self.assertTrue(row['premise'])
        # Remove it, reopen the shelf: it stays gone because it was already offered.
        import shutil
        shelf.close()
        shutil.rmtree(self.root / 'the-court-recorder')
        again = Shelf(self.root, ScriptedProvider, sample=SAMPLE)
        self.addCleanup(again.close)
        self.assertEqual(again.listing(), [])
        self.assertTrue((self.root / SAMPLE_MARKER).exists())

    def test_the_sample_is_not_added_to_a_shelf_that_already_has_series(self):
        RUNS.mkdir(parents=True, exist_ok=True)
        tmp = tempfile.TemporaryDirectory(dir=RUNS)
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name) / 'stories'
        first = Shelf(root, ScriptedProvider)
        first.create('Mine')
        first.close()
        second = Shelf(root, ScriptedProvider, sample=SAMPLE)
        self.addCleanup(second.close)
        self.assertEqual([r['title'] for r in second.listing()], ['Mine'])


class ShelfHttpTest(ShelfCase):
    def setUp(self):
        self.shelf = self.make(SAMPLE)
        self.server = create_server(self.root / '.legacy.db', port=0, writes=True, shelf=self.shelf)
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.port = self.server.server_port
        self.token = self.json('GET', '/api/session')[1]['token']

    def raw(self, method, route, body=None, token=True):
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
        payload = response.read()
        connection.close()
        return response.status, payload

    def json(self, method, route, body=None, token=True):
        status, payload = self.raw(method, route, body, token)
        return status, json.loads(payload)

    def command(self, slug, name, payload=None, status=200):
        code, data = self.json('POST', f'/s/{slug}/api/v1/{name}', {'payload': payload or {}})
        self.assertEqual(code, status, (name, data))
        return data

    def test_home_is_the_app_root_and_lists_the_sample(self):
        status, page = self.raw('GET', '/')
        self.assertEqual(status, 200)
        self.assertIn(b'Your series', page)
        self.assertIn(self.token.encode(), page)
        status, data = self.json('GET', '/api/shelf')
        self.assertEqual((status, [s['slug'] for s in data['series']]), (200, ['the-court-recorder']))

    def test_creating_a_series_needs_the_token_and_a_valid_name(self):
        self.assertEqual(self.json('POST', '/api/shelf/create', {'title': 'No token'}, token=False)[0], 403)
        self.assertEqual(self.json('POST', '/api/shelf/create', {'title': '  '})[0], 400)
        self.assertEqual(self.json('POST', '/api/shelf/create', {'title': 'Fine', 'extra': 1})[0], 400)
        status, data = self.json('POST', '/api/shelf/create', {'title': 'Night Shift'})
        self.assertEqual((status, data), (200, {'slug': 'night-shift', 'path': '/s/night-shift/'}))
        self.assertEqual(len(self.json('GET', '/api/shelf')[1]['series']), 2)

    def test_old_single_story_routes_are_not_reachable_on_a_shelf(self):
        for route in ('/v1', '/api/v1/state', '/api/state', '/s/missing/', '/s/Bad_Slug/v1', '/s/the-court-recorder/api/state',
                      '/s/the-court-recorder/api/setup'):
            self.assertEqual(self.raw('GET', route)[0], 404, route)
        self.assertEqual(self.raw('POST', '/api/setup', {'premise': 'x'})[0], 404)
        self.assertEqual(self.raw('POST', '/s/the-court-recorder/api/setup', {'premise': 'x'})[0], 404)

    def test_a_series_page_carries_its_base_and_an_escaped_title(self):
        slug = self.json('POST', '/api/shelf/create', {'title': '<b>"Bold" & more</b>'})[1]['slug']
        status, page = self.raw('GET', f'/s/{slug}/')
        self.assertEqual(status, 200)
        text = page.decode()
        self.assertIn(f'name="studio-base" content="/s/{slug}"', text)
        self.assertIn('name="studio-home" content="1"', text)
        self.assertIn('content="&lt;b&gt;&quot;Bold&quot; &amp; more&lt;/b&gt;"', text)
        self.assertNotIn('<b>"Bold"', text)
        self.assertEqual(self.raw('GET', f'/s/{slug}/v1')[1], page)

    def test_the_sample_series_serves_its_own_story(self):
        status, state = self.json('GET', '/s/the-court-recorder/api/v1/state')
        self.assertEqual(status, 200)
        self.assertEqual(len(state['canon']), 6)

    def test_series_are_isolated_from_each_other(self):
        a = self.json('POST', '/api/shelf/create', {'title': 'Alpha'})[1]['slug']
        b = self.json('POST', '/api/shelf/create', {'title': 'Beta'})[1]['slug']
        marker = 'Zephyrine keeps the brass key under the third stair.'
        self.command(a, 'create_story')
        self.command(a, 'save_direction', {'layer': 'skeleton', 'content': {'premise': marker, 'spine': 'A secret changes hands.'}})
        a_state = self.json('GET', f'/s/{a}/api/v1/state')[1]
        self.assertIn(marker, json.dumps(a_state))
        # Beta has no story yet: nothing of Alpha is visible, and no file was created for it.
        b_state = self.json('GET', f'/s/{b}/api/v1/state')[1]
        self.assertIsNone(b_state['story'])
        self.assertNotIn('Zephyrine', json.dumps(b_state))
        self.assertTrue((self.root / a / 'story.db').exists())
        self.assertFalse((self.root / b / 'story.db').exists())
        # Once Beta has its own story it starts empty and stays that way.
        self.command(b, 'create_story')
        b_state = self.json('GET', f'/s/{b}/api/v1/state')[1]
        self.assertNotEqual(b_state['story']['story_id'], a_state['story']['story_id'])
        self.assertNotIn('Zephyrine', json.dumps(b_state))
        self.assertNotIn('Zephyrine', json.dumps(self.json('GET', '/s/the-court-recorder/api/v1/state')[1]))
        listing = {s['slug']: s for s in self.json('GET', '/api/shelf')[1]['series']}
        self.assertEqual(listing[a]['premise'], '')  # a saved direction is not adopted yet, so it is not the premise
        self.assertEqual(listing[b]['planned'], 0)


class ShelfStaticTest(unittest.TestCase):
    def test_every_desk_request_goes_through_the_series_base(self):
        js = (WEB / 'v1.js').read_text(encoding='utf-8')
        self.assertEqual(re.findall(r"(?<!BASE \+ )'/api/v1/", js), [])
        self.assertIn("BASE + '/api/v1/", js)

    def test_home_files_follow_the_same_rules_as_the_desk(self):
        for name in ('home.html', 'home.js', 'home.css', 'guide.js', 'guide.css'):
            text = (WEB / name).read_text(encoding='utf-8')
            self.assertNotIn('\u2014', text, name)
            self.assertNotIn('\u2013', text, name)
            self.assertNotRegex(text, r"""[\s'"`]style\s*=""", name)
            served = REPO / 'serial_story' / 'assets' / name
            if served.exists():
                self.assertEqual(served.read_bytes(), (WEB / name).read_bytes(), f'{name} drifted from the served copy')
        for m in re.finditer(r'<script\b([^>]*)>', (WEB / 'home.html').read_text(encoding='utf-8')):
            self.assertIn('src=', m.group(1), 'inline script found')

    def test_both_pages_load_the_guide_and_it_never_uses_data_urls(self):
        for name in ('home.html', 'v1.html'):
            html = (WEB / name).read_text(encoding='utf-8')
            self.assertIn('/guide.js', html, name)
            self.assertIn('/guide.css', html, name)
        for name in ('guide.js', 'guide.css'):
            self.assertNotRegex((WEB / name).read_text(encoding='utf-8'), r'data:[a-z]+/', name)


if __name__ == '__main__':
    unittest.main()
