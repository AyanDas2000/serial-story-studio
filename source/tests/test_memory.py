import importlib.util
import tempfile
import unittest
from pathlib import Path

from serial_story.repository import SQLiteRepository
from serial_story.service import StoryService


class MemoryTest(unittest.TestCase):
    def temporary_directory(self):
        root = Path(__file__).resolve().parents[1] / 'local' / 'test-runs'
        root.mkdir(parents=True, exist_ok=True)
        return tempfile.TemporaryDirectory(dir=root)

    def memory(self, repo):
        self.assertIsNotNone(importlib.util.find_spec('serial_story.memory'),
                             'A source-linked memory ledger is not implemented')
        from serial_story.memory import SQLiteMemory
        return SQLiteMemory(repo)

    def accepted(self, repo, evidence='Ivo is alive.'):
        studio = StoryService(repo)
        studio.initialize('Offline fixture: a harbor map conceals a room.')
        studio.approve_plan(studio.propose_plan().id)
        draft = studio.draft()
        text = evidence + ' ' + draft.text
        return studio.accept(draft.id, edited_text=text)

    def test_human_confirmed_fact_uses_edited_accepted_source(self):
        with self.temporary_directory() as folder:
            db = Path(folder) / 'story.db'
            with SQLiteRepository(db) as repo:
                accepted = self.accepted(repo)
                memory = self.memory(repo)
                ivo = memory.add_entity('Ivo', 'character', 'protagonist')
                proposal = memory.propose_fact(ivo.id, 'status', 'alive', accepted.revision_id,
                                               'Ivo is alive.')
                self.assertEqual(memory.query_facts(), [])
                confirmed = memory.confirm_fact(proposal.id)
                self.assertEqual(memory.confirm_fact(proposal.id), confirmed)
                self.assertEqual(repo.story()['next_episode'], 2)
            with SQLiteRepository(db) as repo:
                memory = self.memory(repo)
                facts = memory.query_facts()
                self.assertEqual(len(facts), 1)
                self.assertEqual(facts[0].value, 'alive')
                self.assertEqual(facts[0].source_revision_id, accepted.revision_id)
                self.assertEqual(facts[0].evidence, 'Ivo is alive.')
                self.assertEqual(repo.read(1).text, accepted.text)


    def test_registry_limits_and_idempotent_identity(self):
        from serial_story.records import StoryError
        with self.temporary_directory() as folder, SQLiteRepository(Path(folder) / 'story.db') as repo:
            repo.initialize('Offline fixture')
            memory = self.memory(repo)
            hero = memory.add_entity('Ivo', 'character', 'protagonist')
            self.assertEqual(memory.add_entity(' IVO ', 'character', 'protagonist').id, hero.id)
            with self.assertRaises(StoryError):
                memory.add_entity('Other hero', 'character', 'protagonist')
            for i in range(9):
                memory.add_entity(f'Major {i}', 'character', 'core')
            with self.assertRaises(StoryError):
                memory.add_entity('Eleventh major', 'character', 'core')
            for i in range(20):
                memory.add_entity(f'Support {i}', 'character', 'supporting')
            with self.assertRaises(StoryError):
                memory.add_entity('Character 31', 'character', 'supporting')
            harbor = memory.add_entity('Harbor', 'location')
            self.assertEqual(harbor.kind, 'location')
            self.assertEqual(len([e for e in memory.entities() if e.kind == 'character']), 30)


    def test_explicit_later_supersession_keeps_history_and_refuses_old_corrections(self):
        from serial_story.records import StoryError
        with self.temporary_directory() as folder, SQLiteRepository(Path(folder) / 'story.db') as repo:
            first = self.accepted(repo)
            memory = self.memory(repo)
            ivo = memory.add_entity('Ivo', 'character', 'protagonist')
            alive = memory.confirm_fact(memory.propose_fact(ivo.id, 'status', 'alive', first.revision_id, 'Ivo is alive.').id)
            studio = StoryService(repo)
            draft = studio.draft()
            second = studio.accept(draft.id, edited_text='Ivo is dead. ' + draft.text)
            death = memory.propose_fact(ivo.id, 'status', 'dead', second.revision_id, 'Ivo is dead.')
            with self.assertRaises(StoryError):
                memory.confirm_fact(death.id)
            dead = memory.confirm_fact(death.id, supersedes=alive.id)
            self.assertEqual(memory.query_facts(subject_id=ivo.id)[0].id, dead.id)
            self.assertEqual(len(memory.query_facts(current_only=False)), 2)
            self.assertEqual(memory.fact(alive.id).superseded_by, dead.id)
            # Original evidence cannot silently replace a later accepted development.
            old = memory.propose_fact(ivo.id, 'status', 'alive again', first.revision_id, 'Ivo is alive.')
            with self.assertRaises(StoryError):
                memory.confirm_fact(old.id, supersedes=dead.id)
            self.assertEqual(repo.story()['next_episode'], 3)


    def test_graph_links_character_fact_situation_location_and_accepted_evidence(self):
        with self.temporary_directory() as folder, SQLiteRepository(Path(folder) / 'story.db') as repo:
            accepted = self.accepted(repo, 'Ivo is alive. Ivo waits at the harbor.')
            memory = self.memory(repo)
            ivo = memory.add_entity('Ivo', 'character', 'protagonist')
            harbor = memory.add_entity('Harbor', 'location')
            self.assertTrue(hasattr(memory, 'add_situation'), 'Accepted-source situations are not implemented')
            situation = memory.add_situation('Waiting at the harbor', accepted.revision_id, 'Ivo waits at the harbor.')
            fact = memory.propose_fact(ivo.id, 'at', 'Harbor', accepted.revision_id, 'Ivo waits at the harbor.', object_id=harbor.id, situation_id=situation.id)
            memory.confirm_fact(fact.id)
            graph = memory.graph_snapshot()
            ids = {n['id'] for n in graph['nodes']}
            self.assertTrue({f'entity-{ivo.id}', f'entity-{harbor.id}', f'fact-{fact.id}', f'situation-{situation.id}', f'episode-{accepted.revision_id}'} <= ids)
            edges = {(e['source'], e['target'], e['kind']) for e in graph['edges']}
            self.assertIn((f'fact-{fact.id}', f'entity-{ivo.id}', 'about'), edges)
            self.assertIn((f'fact-{fact.id}', f'entity-{harbor.id}', 'relates_to'), edges)
            self.assertIn((f'fact-{fact.id}', f'situation-{situation.id}', 'in_situation'), edges)
            self.assertIn((f'fact-{fact.id}', f'episode-{accepted.revision_id}', 'evidenced_by'), edges)
            for edge in graph['edges']:
                self.assertIn(edge['source'], ids)
                self.assertIn(edge['target'], ids)


    def test_filtered_graph_exports_after_supersession_changes_object(self):
        import json
        import subprocess
        import sys
        from serial_story.graph import render_graph

        with self.temporary_directory() as folder:
            db = Path(folder) / 'story.db'
            with SQLiteRepository(db) as repo:
                first = self.accepted(repo, 'Ivo waits at the harbor.')
                memory = self.memory(repo)
                ivo = memory.add_entity('Ivo', 'character', 'protagonist')
                harbor = memory.add_entity('Harbor', 'location')
                lighthouse = memory.add_entity('Lighthouse', 'location')
                old = memory.confirm_fact(memory.propose_fact(
                    ivo.id, 'at', 'Harbor', first.revision_id,
                    'Ivo waits at the harbor.', object_id=harbor.id).id)
                studio = StoryService(repo)
                draft = studio.draft()
                second = studio.accept(draft.id, edited_text='Ivo waits at the lighthouse. ' + draft.text)
                new = memory.confirm_fact(memory.propose_fact(
                    ivo.id, 'at', 'Lighthouse', second.revision_id,
                    'Ivo waits at the lighthouse.', object_id=lighthouse.id).id,
                    supersedes=old.id)

                # The exact reviewed symptom must work through a fresh CLI process.
                out = Path(folder) / 'lighthouse.html'
                result = subprocess.run([
                    sys.executable, '-m', 'serial_story', '--db', str(db),
                    'graph', '--subject', str(lighthouse.id), '--out', str(out),
                ], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(out.exists())
                exported = json.loads(result.stdout)
                filtered = memory.graph_snapshot(subject_id=lighthouse.id)
                self.assertEqual(exported['node_count'], len(filtered['nodes']))
                self.assertEqual(out.read_text(encoding='utf-8'), render_graph(filtered))

                # Filtering stays strict; unfiltered/character views retain history.
                for subject, expected in [
                    (None, {old.id, new.id}), (ivo.id, {old.id, new.id}),
                    (harbor.id, {old.id}), (lighthouse.id, {new.id}),
                ]:
                    with self.subTest(subject=subject):
                        graph = memory.graph_snapshot(subject_id=subject)
                        ids = {node['id'] for node in graph['nodes']}
                        self.assertEqual(
                            {node['id'] for node in graph['nodes'] if node['kind'] == 'fact'},
                            {f'fact-{fact_id}' for fact_id in expected})
                        for edge in graph['edges']:
                            self.assertIn(edge['source'], ids)
                            self.assertIn(edge['target'], ids)
                        links = {(edge['source'], edge['target'], edge['kind']) for edge in graph['edges']}
                        supersession = (f'fact-{new.id}', f'fact-{old.id}', 'supersedes')
                        self.assertEqual(supersession in links, {old.id, new.id} <= expected)
                        if subject is not None:
                            self.assertIn('Filtered view', graph['warning'])
                        self.assertIsInstance(render_graph(graph), str)
                self.assertEqual(memory.fact(old.id).superseded_by, new.id)
                self.assertEqual(memory.fact(new.id).supersedes, old.id)

    def test_future_direction_enters_context_and_invalidates_pending_acceptance(self):
        from serial_story.records import StoryError
        with self.temporary_directory() as folder, SQLiteRepository(Path(folder) / 'story.db') as repo:
            first = self.accepted(repo)
            memory = self.memory(repo)
            ivo = memory.add_entity('Ivo', 'character', 'protagonist')
            alive = memory.confirm_fact(memory.propose_fact(ivo.id, 'status', 'alive', first.revision_id, 'Ivo is alive.').id)
            self.assertTrue(hasattr(memory, 'set_direction'), 'Durable future directions are not implemented')
            direction = memory.set_direction('pace', 'Slow down the romance.', subject_id=ivo.id)
            studio = StoryService(repo)
            context = studio.context(focus_entity_ids=(ivo.id,))
            self.assertIn('Slow down the romance.', context.text)
            self.assertIn(alive.id, context.fact_ids)
            self.assertIn(direction.id, context.direction_ids)
            self.assertLessEqual(len(context.text), studio.max_context_characters)
            draft = studio.draft(focus_entity_ids=(ivo.id,))
            memory.set_direction('pace', 'Focus on friendship before romance.', subject_id=ivo.id)
            with self.assertRaises(StoryError):
                studio.accept(draft.id)
            self.assertEqual(repo.story()['next_episode'], 2)
            self.assertEqual(studio.draft().id, draft.id, 'A changed direction must not silently regenerate')
            studio.reject(draft.id)
            replacement = studio.draft(focus_entity_ids=(ivo.id,))
            self.assertNotEqual(replacement.id, draft.id)
            self.assertIn('Focus on friendship before romance.', studio.context().text)
            self.assertNotIn('Slow down the romance.', studio.context().text)
            self.assertEqual(len(memory.directions(include_retired=True)), 2)


if __name__ == '__main__':
    unittest.main()
