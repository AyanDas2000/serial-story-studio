import tempfile
import unittest
from pathlib import Path

from serial_story.records import StoryError
from serial_story.v1.api import V1Api
from serial_story.v1.provider import GenerationRequest, NotSent, ProviderUnavailable, ScriptedProvider

REPO = Path(__file__).resolve().parents[1]
RUNS = REPO / 'local' / 'test-runs'


class Failing:
    def __init__(self, error):
        self.error = error

    def generate(self, request: GenerationRequest):
        raise self.error


class ApiCommandTests(unittest.TestCase):
    def setUp(self):
        RUNS.mkdir(parents=True, exist_ok=True)
        tmp = tempfile.TemporaryDirectory(dir=RUNS)
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / 's.v1.db'

    def api(self, provider=None):
        return V1Api(self.path, provider or ScriptedProvider())

    def run_command(self, api, name, payload, expected=None):
        return api.command(name, {'payload': payload, 'expected': expected or {}})

    def test_secret_and_style_commands_round_trip(self):
        api = self.api()
        self.run_command(api, 'create_story', {})
        status, body = self.run_command(api, 'add_secret', {'label': 'Who did it', 'body': 'The clerk burned the ledger.', 'canaries': ['clerk']})
        self.assertEqual(status, 200, body)
        self.assertEqual(api.state()['secrets'][0]['canaries'], ['clerk'])
        status, body = self.run_command(api, 'save_style_sheet', {'body': 'Short sentences.', 'avoid': ['suddenly']})
        self.assertEqual(status, 200, body)
        self.assertEqual(api.state()['style_sheet']['avoid'], ['suddenly'])
        status, _ = self.run_command(api, 'retire_secret', {'secret_id': api.state()['secrets'][0]['secret_id']})
        self.assertEqual(status, 200)
        self.assertEqual(api.state()['secrets'][0]['status'], 'retired')

    def test_bad_secret_is_refused_cleanly(self):
        api = self.api()
        self.run_command(api, 'create_story', {})
        with self.assertRaises(StoryError):
            self.run_command(api, 'add_secret', {'label': 'x', 'body': 'y', 'canaries': 'not a list'})

    def test_provider_outage_maps_to_503_and_says_whether_billed(self):
        self.run_command(self.api(), 'create_story', {})
        status, body = self.run_command(self.api(Failing(NotSent('cap'))), 'converse', {'target': 'skeleton', 'text': 'hello'})
        self.assertEqual((status, body['code'], body['detail']['billed']), (503, 'provider_not_sent', 'no'))
        status, body = self.run_command(self.api(Failing(ProviderUnavailable('?'))), 'converse', {'target': 'skeleton', 'text': 'hello'})
        self.assertEqual((status, body['code'], body['detail']['billed']), (503, 'provider_unverified', 'unknown'))


if __name__ == '__main__':
    unittest.main()
