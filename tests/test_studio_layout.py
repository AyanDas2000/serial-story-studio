"""Presentation contract, with the original authoring IDs preserved."""
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'serial_story/assets'
CORE_IDS = re.findall(r"(?:id|click)\('([^']+)'", (ASSETS / 'studio.js').read_text())

class StudioLayoutTests(unittest.TestCase):
    def test_navigation_exposes_every_work_area(self):
        html = (ASSETS / 'studio.html').read_text()
        for area in ('plan', 'write', 'continuity', 'models'):
            self.assertIn(f'data-view="{area}"', html)
            self.assertIn(f'id="view-{area}"', html)
        ids = re.findall(r'\bid="([^"]+)"', html)
        self.assertEqual(len(ids), len(set(ids)))
        for name in CORE_IDS:
            self.assertIn(name, ids)
        self.assertIn('/studio-layout.js', html)

    def test_editor_actions_precede_the_long_manuscript(self):
        html = (ASSETS / 'studio.html').read_text()
        self.assertLess(html.index('id="draft-actions"'), html.index('id="manuscript"'))
        self.assertLess(html.index('id="prompt-template"'), html.index('id="lookup-model"'))
        self.assertIn('400 to 700', html)

    def test_keyboard_navigation_preserves_inputs(self):
        result = subprocess.run(['node', str(ROOT / 'tests/studio_layout_test.js'),
                                 str(ASSETS / 'studio-layout.js')],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_layout_script_has_a_fixed_local_route(self):
        from serial_story.studio.server import ROUTES
        self.assertEqual(ROUTES.get('/studio-layout.js'),
                         ('studio-layout.js', 'text/javascript; charset=utf-8'))
