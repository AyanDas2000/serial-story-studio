"""The author's terminal client: exit codes a script can trust, and the paragraph edit helper."""
import importlib.util
import unittest
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / 'scripts' / 'author_client.py'
spec = importlib.util.spec_from_file_location('author_client', PATH)
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)


class ExitCodeTest(unittest.TestCase):
    def test_success_refusal_and_pause_have_different_codes(self):
        self.assertEqual(client.exit_code((200, {'status': 'complete'})), 0)
        self.assertEqual(client.exit_code([400, {'code': 'invalid_length'}]), 1)
        self.assertEqual(client.exit_code((409, {})), 1)
        self.assertEqual(client.exit_code((200, {'status': 'paused', 'pause_reason': 'over_length'})), 3)
        self.assertEqual(client.exit_code({'low': 1}), 0, 'plain reads are not refusals')


class FakeDesk(client.Desk):
    def __init__(self, episodes):
        self.sent, self.episodes = [], episodes

    def state(self, slug):
        return {'episodes': self.episodes}

    def command(self, slug, name, payload, expected=None):
        self.sent.append((name, payload, expected))
        return 200, {}


class EditTest(unittest.TestCase):
    EPISODE = {'ordinal': 6, 'selection': {'revision_id': 'rv-1', 'cas': 4},
               'blocks': [{'block_id': 'b-1', 'text': 'one'}, {'block_id': 'b-2', 'text': 'two'}, {'block_id': 'b-3', 'text': 'three'}]}

    def test_only_the_chosen_paragraph_changes_and_the_versions_are_sent(self):
        desk = FakeDesk([self.EPISODE])
        desk.edit('s', 6, 2, 'TWO!')
        name, payload, expected = desk.sent[0]
        self.assertEqual(name, 'save_revision')
        self.assertEqual([b['text'] for b in payload['blocks']], ['one', 'TWO!', 'three'])
        self.assertEqual([b['block_id'] for b in payload['blocks']], ['b-1', 'b-2', 'b-3'])
        self.assertEqual((payload['base_revision_id'], expected), ('rv-1', {'selection_cas': 4}))

    def test_a_missing_draft_or_paragraph_stops_before_anything_is_sent(self):
        desk = FakeDesk([self.EPISODE, {'ordinal': 7, 'selection': None, 'blocks': []}])
        for args in ((7, 1), (6, 0), (6, 4), (9, 1)):
            with self.assertRaises(SystemExit):
                desk.edit('s', args[0], args[1], 'x')
        self.assertEqual(desk.sent, [])


if __name__ == '__main__':
    unittest.main()
