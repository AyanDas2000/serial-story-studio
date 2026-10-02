import importlib.util
import json
import unittest


class GraphTest(unittest.TestCase):
    def test_offline_graph_safely_embeds_untrusted_labels_and_bundles_its_font(self):
        self.assertIsNotNone(importlib.util.find_spec('serial_story.graph'), 'The offline graph renderer is missing')
        from serial_story.graph import render_graph
        attack = '</script><script>window.attack=1</script>'
        graph = {'memory_revision': 1, 'next_episode': 2, 'warning': 'Manual memory',
                 'nodes': [{'id': 'entity-1', 'kind': 'character', 'label': attack, 'status': 'registry'}], 'edges': []}
        page = render_graph(graph)
        self.assertNotIn(attack, page)
        self.assertIn('\\u003c/script\\u003e', page)
        self.assertIn('Content-Security-Policy', page)
        self.assertIn("connect-src 'none'", page)
        self.assertIn('data:font/ttf;base64,', page)
        self.assertIn('SIL OPEN FONT LICENSE', page)
        self.assertNotIn('innerHTML', page)
        self.assertNotIn('<script src=', page)
        marker = '<script id="story-data" type="application/json">'
        payload = page.split(marker, 1)[1].split('</script>', 1)[0]
        self.assertEqual(json.loads(payload)['nodes'][0]['label'], attack)
        self.assertIn('Inspect a source', page)


if __name__ == '__main__':
    unittest.main()
