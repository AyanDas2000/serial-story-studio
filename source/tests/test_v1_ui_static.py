"""Static guards for the v1 writing desk front end: strict CSP, copy rules, fixed contracts."""
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / 'serial_story' / 'v1' / 'web'
FILES = ('v1.html', 'v1.css', 'v1.js')


class V1UiStaticTests(unittest.TestCase):
    def read(self, name):
        return (WEB / name).read_text(encoding='utf-8')

    def test_no_inline_style_attributes_in_markup_or_template_strings(self):
        for name in ('v1.html', 'v1.js'):
            text = self.read(name)
            hits = [m.group(0) for m in re.finditer(r"""[\s'"`]style\s*=""", text)]
            self.assertEqual(hits, [], f'{name} contains an inline style attribute')

    def test_no_inline_script_or_data_url(self):
        html = self.read('v1.html')
        for m in re.finditer(r'<script\b([^>]*)>', html):
            self.assertIn('src=', m.group(1), 'inline script found')
        for name in FILES:
            self.assertNotRegex(self.read(name), r'data:[a-z]+/', f'{name} contains a data: URL')

    def test_no_em_or_en_dash_in_product_files(self):
        for name in FILES:
            text = self.read(name)
            self.assertNotIn('\u2014', text, name)
            self.assertNotIn('\u2013', text, name)

    def test_logic_link_and_landmarks_are_static(self):
        html = self.read('v1.html')
        self.assertIn('href="/logic"', html)
        for needle in ('<header', '<main', 'role="status"', '<nav class="rooms"'):
            self.assertIn(needle, html)

    def test_chat_panel_landmarks_and_composer(self):
        html = self.read('v1.html')
        for needle in ('id="chat"', 'id="chatlog" role="log"', 'aria-live="polite"', 'for="composer"', 'Does not change your story.'):
            self.assertIn(needle, html)
        self.assertEqual(html.count('Does not change your story.'), 1)
        self.assertLess(html.index('id="chat"'), html.index('id="book"'))

    def test_chat_dock_tabs_and_context_chips_exist(self):
        html = self.read('v1.html')
        for needle in ('id="chips"', 'id="peekline"', 'id="dock-cycle"'):
            self.assertIn(needle, html)
        css = self.read('v1.css')
        self.assertIn('(min-width:600px) and (max-width:1023px)', css)
        self.assertIn('.slip', css)

    def test_slip_flight_uses_transform_and_opacity_only(self):
        js = self.read('v1.js')
        a = js.index('function flySlip')
        b = js.index('function flyDot')
        body = js[a:b]
        for prop in ('top:', 'left:', 'width:', 'height:', 'margin'):
            self.assertNotIn(prop, body.replace("'translate", ''), prop)
        self.assertIn('transform:', body)
        self.assertIn('opacity:', body)

    def test_orb_has_four_states_reduced_twin_and_no_layout_animation(self):
        css = self.read('v1.css')
        for state in ('reasoning', 'working', 'compacting', 'waiting'):
            self.assertIn(f'.orb[data-s={state}]', css)
        start = css.index('/* Orb:')
        block = css[start:]
        reduced = block.index('prefers-reduced-motion')
        self.assertIn('animation:none', block[reduced:])
        for frames in block[:reduced].split('@keyframes')[1:]:
            for prop in ('left:', 'top:', 'width:', 'height:', 'margin', 'box-shadow'):
                self.assertNotIn(prop, frames.split('}}')[0], prop)

    def test_orb_markup_is_decorative_with_a_text_status(self):
        js = self.read('v1.js')
        self.assertIn('aria-hidden="true"><i class="o-r">', js)
        self.assertIn('role="status">${orbHtml(', js)
        html = self.read('v1.html')
        self.assertIn('id="memchip"', html)

    def test_chat_never_sends_staged_text_anywhere(self):
        js = self.read('v1.js')
        self.assertNotRegex(js, r"api\('converse',\s*\{[^}]*staged")

    def test_chat_replies_have_no_placement_buttons(self):
        # Chat suggestions are read and copied by hand; nothing places them into the story.
        js = self.read('v1.js')
        self.assertNotIn('usebtn', js)
        self.assertNotIn('use-menu', js)
        self.assertNotIn('useItems', js)

    def test_episode_title_is_shown_when_the_writer_names_one(self):
        js = self.read('v1.js')
        self.assertIn('e.title', js)
        self.assertIn('e.title || titleOf(e.ordinal)', js)

    def test_fonts_are_local_and_reduced_motion_exists(self):
        css = self.read('v1.css')
        self.assertIn('/fonts/literata.woff2', css)
        self.assertIn('/fonts/space-grotesk.woff2', css)
        self.assertIn('prefers-reduced-motion', css)
        self.assertNotRegex(css, r'url\((?!"/fonts/)[^)]*http')

    def test_three_files_are_served_identically(self):
        for name in FILES:
            served = ROOT / 'serial_story' / 'assets' / name
            if served.exists():
                self.assertEqual(served.read_bytes(), (WEB / name).read_bytes(), f'{name} drifted from the served copy')

    @unittest.skipUnless(shutil.which('node'), 'node is not installed')
    def test_script_parses(self):
        result = subprocess.run(['node', '--check', str(WEB / 'v1.js')], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
