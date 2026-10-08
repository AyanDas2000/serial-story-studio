"""Native Node DOM behavior, no application dependencies or browser claims."""
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class StudioDOMTests(unittest.TestCase):
    def test_dirty_form_conflicts(self):
        self.run_dom('studio_dom_test.js')

    def test_successful_response_races(self):
        self.run_dom('studio_race_test.js')

    def run_dom(self, name):
        result = subprocess.run(['node', str(ROOT / 'tests' / name), str(ROOT / 'serial_story/assets/studio.js')],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
