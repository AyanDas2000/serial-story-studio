import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class MemoryCLITest(unittest.TestCase):
    def test_ledger_and_graph_survive_separate_cli_processes(self):
        root = Path(__file__).resolve().parents[1] / 'local' / 'test-runs'
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as folder:
            db = Path(folder) / 'story.db'
            def run(*args):
                result = subprocess.run([sys.executable, '-m', 'serial_story', '--db', str(db), *args], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                return json.loads(result.stdout)
            run('init', '--premise', 'Offline fixture: a harbor map conceals a room.')
            plan = run('plan')
            run('approve-plan', str(plan['id']))
            draft = run('draft')
            edited = Path(folder) / 'edited.txt'
            edited.write_text('Ivo is alive. Ivo waits at the harbor. ' + draft['text'], encoding='utf-8')
            accepted = run('accept', str(draft['id']), '--text-file', str(edited))
            hero = run('entity-add', '--name', 'Ivo', '--kind', 'character', '--role', 'protagonist')
            place = run('entity-add', '--name', 'Harbor', '--kind', 'location')
            scene = run('situation-add', '--title', 'Waiting at the harbor', '--revision', str(accepted['revision_id']), '--evidence', 'Ivo waits at the harbor.')
            fact = run('fact-propose', '--subject', str(hero['id']), '--predicate', 'at', '--value', 'Harbor', '--revision', str(accepted['revision_id']), '--evidence', 'Ivo waits at the harbor.', '--object', str(place['id']), '--situation', str(scene['id']))
            self.assertEqual(run('facts')['facts'], [])
            run('fact-confirm', str(fact['id']))
            run('fact-confirm', str(fact['id']))
            direction = run('direction-set', '--key', 'pace', '--text', 'Build trust before romance.', '--subject', str(hero['id']))
            board = run('storyboard')
            self.assertEqual(len(board['current_facts']), 1)
            self.assertEqual(board['future_directions'][0]['id'], direction['id'])
            context = run('context', '--character', str(hero['id']))
            self.assertIn(fact['id'], context['fact_ids'])
            self.assertIn('Build trust before romance.', context['text'])
            out = Path(folder) / 'graph.html'
            exported = run('graph', '--out', str(out))
            self.assertTrue(out.exists())
            self.assertGreater(exported['node_count'], 0)
            self.assertIn('Ivo', out.read_text(encoding='utf-8'))
            self.assertEqual(run('status')['next_episode'], 2)
            self.assertEqual(run('facts', '--search', 'Harbor')['facts'][0]['source_revision_id'], accepted['revision_id'])


if __name__ == '__main__':
    unittest.main()
