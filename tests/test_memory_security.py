# Local memory security regression tests
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from serial_story.graph import render_graph
from serial_story.memory import SQLiteMemory
from serial_story.records import StoryError
from serial_story.repository import SQLiteRepository
from serial_story.service import StoryService


class MemorySafetyTest(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1] / 'local' / 'test-runs'
        root.mkdir(parents=True, exist_ok=True)
        self.folder = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(self.folder.cleanup)
        self.repo = SQLiteRepository(Path(self.folder.name) / 'story.db')
        self.addCleanup(self.repo.connection.close)
        self.studio = StoryService(self.repo)
        self.studio.initialize('Offline security fixture')
        self.studio.approve_plan(self.studio.propose_plan().id)
        self.memory = self.studio.memory
        self.hero = self.memory.add_entity('Ivo', 'character', 'protagonist')

    def accept(self, prefix='Ivo is alive. '):
        draft = self.studio.draft()
        return self.studio.accept(draft.id, edited_text=prefix + draft.text)

    def test_drafts_rejections_missing_and_ambiguous_evidence_are_not_sources(self):
        draft = self.studio.draft()
        with self.assertRaises(StoryError):
            self.memory.propose_fact(self.hero.id, 'status', 'alive', draft.id, 'Ivo is alive.')
        self.studio.reject(draft.id)
        with self.assertRaises(StoryError):
            self.memory.propose_fact(self.hero.id, 'status', 'alive', draft.id, 'Ivo is alive.')
        accepted = self.accept('Ivo is alive. Ivo is alive. ')
        for quote in ('Ivo is dead.', 'Ivo is alive.'):
            with self.subTest(quote=quote), self.assertRaises(StoryError):
                self.memory.propose_fact(self.hero.id, 'status', 'alive', accepted.revision_id, quote)
        self.assertEqual(self.memory.query_facts(), [])

    def test_rejected_proposal_stays_out_of_context_and_cannot_be_confirmed(self):
        accepted = self.accept()
        proposal = self.memory.propose_fact(self.hero.id, 'status', 'alive', accepted.revision_id, 'Ivo is alive.')
        self.assertEqual(self.studio.context().fact_ids, ())
        self.memory.reject_fact(proposal.id, 'Wrong interpretation')
        self.memory.reject_fact(proposal.id)
        with self.assertRaises(StoryError):
            self.memory.confirm_fact(proposal.id)
        self.assertEqual(self.studio.context().fact_ids, ())

    def test_confirmation_failure_rolls_back_memory_and_review(self):
        accepted = self.accept()
        proposal = self.memory.propose_fact(self.hero.id, 'status', 'alive', accepted.revision_id, 'Ivo is alive.')
        before = self.memory.revision()
        self.repo.connection.execute("CREATE TRIGGER fail_fact BEFORE INSERT ON reviews WHEN NEW.target_kind='fact' BEGIN SELECT RAISE(ABORT,'injected fact review failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.memory.confirm_fact(proposal.id)
        self.assertEqual(self.memory.fact(proposal.id).status, 'proposed')
        self.assertEqual(self.memory.revision(), before)
        self.assertEqual(self.memory.query_facts(), [])

    def test_sql_shaped_input_is_literal_and_search_does_not_change_storage(self):
        accepted = self.accept()
        name = "'; DROP TABLE episodes; --"
        entity = self.memory.add_entity(name, 'character', 'supporting')
        proposal = self.memory.propose_fact(entity.id, 'quoted_text', name, accepted.revision_id, 'Ivo is alive.')
        self.memory.confirm_fact(proposal.id)
        self.assertEqual(self.memory.query_facts(search=name)[0].value, name)
        self.assertEqual(self.repo.read(1).text, accepted.text)
        self.assertEqual(self.memory.query_facts(search="' OR 1=1 --"), [])

    def test_essential_memory_overflow_refuses_instead_of_silently_dropping_facts(self):
        accepted = self.accept()
        proposal = self.memory.propose_fact(self.hero.id, 'description', 'x' * 1000, accepted.revision_id, 'Ivo is alive.')
        self.memory.confirm_fact(proposal.id)
        attempts = self.studio.status()['budget']['attempts']
        with self.assertRaises(StoryError):
            StoryService(self.repo, max_context_characters=200).draft()
        self.assertEqual(self.studio.status()['budget']['attempts'], attempts)

    def test_future_scopes_and_active_cast_limit_are_explicit(self):
        self.accept()
        direction = self.memory.set_direction('reveal', 'Save the reveal for episode 4.', start_episode=4)
        self.assertNotIn(direction.id, self.studio.context().direction_ids)
        before = self.memory.revision()
        self.assertEqual(self.memory.set_direction('reveal', 'Save the reveal for episode 4.', start_episode=4).id, direction.id)
        self.assertEqual(self.memory.revision(), before)
        with self.assertRaises(StoryError):
            self.memory.set_direction('past', 'Change episode 1.', start_episode=1)
        others = [self.memory.add_entity(f'Support {i}', 'character', 'supporting').id for i in range(10)]
        with self.assertRaises(StoryError):
            self.studio.context(focus_entity_ids=tuple([self.hero.id] + others))
        place = self.memory.add_entity('Harbor', 'location')
        with self.assertRaises(StoryError):
            self.studio.context(focus_entity_ids=(place.id,))

    def test_storyboard_snapshot_is_consistent_and_keeps_proposals_visible(self):
        from unittest.mock import patch
        accepted = self.accept()
        proposal = self.memory.propose_fact(self.hero.id, 'status', 'alive', accepted.revision_id, 'Ivo is alive.')
        with SQLiteRepository(Path(self.folder.name) / 'story.db') as other_repo:
            other = SQLiteMemory(other_repo)
            other_repo.connection.execute('PRAGMA busy_timeout=0')
            original_query = self.memory.query_facts
            blocked = []
            def query_while_another_writer_attempts_change(*args, **kwargs):
                try:
                    other.set_direction('racing-change', 'This must not enter a mixed snapshot.')
                except sqlite3.OperationalError:
                    blocked.append(True)
                return original_query(*args, **kwargs)
            with patch.object(self.memory, 'query_facts', side_effect=query_while_another_writer_attempts_change):
                snapshot = self.memory.storyboard_snapshot()
        self.assertEqual(blocked, [True])
        self.assertEqual(snapshot['current_facts'], [])
        self.assertEqual(snapshot['pending_fact_proposals'][0]['id'], proposal.id)
        self.assertEqual(snapshot['future_directions'], [])
        self.assertEqual(snapshot['memory_revision'], self.memory.revision())

    def test_graph_refuses_dangling_connections_and_preserves_template_shaped_text(self):
        graph = {'nodes':[{'id':'entity-1','kind':'character','label':'__STYLES__ <img src=x onerror=alert(1)>','status':'registry'}], 'edges':[], 'memory_revision':0, 'next_episode':1}
        page = render_graph(graph)
        payload = page.split('<script id="story-data" type="application/json">', 1)[1].split('</script>', 1)[0]
        self.assertEqual(json.loads(payload)['nodes'][0]['label'], graph['nodes'][0]['label'])
        self.assertNotIn('<img src=x', page)
        graph['edges'] = [{'source':'entity-1','target':'entity-2','kind':'about'}]
        with self.assertRaises(StoryError):
            render_graph(graph)


if __name__ == '__main__':
    unittest.main()
