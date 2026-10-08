"""Claim ledger: immutable rows, derived standing, previews kept apart, and extraction that never loses a claim silently.

Maps to docs/research/MEMORY-CONTEXT-REVIEW.md answers 4 and 5 and findings F7 and F8.
"""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from serial_story.records import StoryError
from serial_story.v1.desk import Desk, Refused
from serial_story.v1.provider import GenerationRequest, GenerationResult, ScriptedProvider
from tests.test_v1_slice import RUNS, V1Case


def group(desk):
    return [(n, s['revision_id'], s['sha256']) for n, s in enumerate((desk.selection(n) for n in (1, 2, 3)), 1)]


class RepeatingProvider(ScriptedProvider):
    """Returns whatever extraction output the test sets; everything else behaves as scripted."""
    output = None

    def generate(self, request: GenerationRequest) -> GenerationResult:
        if request.recipe == 'promotion' and self.output is not None:
            self.calls.append({'recipe': request.recipe, 'key': request.key, 'prompt': request.prompt,
                               'variant': request.variant, 'params': dict(request.params)})
            blocks = request.params['blocks']
            out = self.output(blocks) if callable(self.output) else self.output
            return GenerationResult(out if isinstance(out, str) else json.dumps(out))
        return super().generate(request)


class SloppyCase(unittest.TestCase):
    def setUp(self):
        RUNS.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=RUNS)
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'story.db'
        self.provider = RepeatingProvider()
        self.desk = Desk.create(self.path, provider=self.provider)
        self.addCleanup(lambda: self.desk.close())
        V1Case.adopt_direction(self)
        self.desk.commission_arc(slots=(1, 3), progression='provisional_chain')

    def accept_and_read(self):
        self.desk.accept_prefix(group(self.desk), expected_canon_seq=0)
        return self.desk.update_memory()


def sloppy_items(blocks):
    first = blocks[0]
    text, bid = first['text'], first['block_id']
    sentence = text[:text.index('. ') + 1]
    word_run = next(text[i:i + 4] for i in range(len(text) - 4) if text.count(text[i:i + 4]) > 1)
    spaced = sentence[: sentence.index(' ') + 1] + ' ' + sentence[sentence.index(' ') + 1:]
    return [
        {'kind': 'event', 'subject': 'quote only', 'quote': sentence},
        {'kind': 'event', 'subject': 'wrong offsets', 'block_id': bid, 'start': 5, 'end': 9, 'quote': sentence},
        {'kind': 'event', 'subject': 'doubled space', 'block_id': bid, 'quote': spaced},
        {'kind': 'event', 'subject': 'quote only', 'quote': sentence},
        {'kind': 'summary', 'subject': 'repeats in the block', 'block_id': bid, 'quote': word_run},
        {'kind': 'event', 'subject': 'invented', 'block_id': bid, 'quote': 'nothing like this is written anywhere'},
        {'kind': 'testimony', 'subject': 'nobody spoke', 'block_id': bid, 'quote': sentence},
        {'kind': 'prophecy', 'subject': 'bad kind', 'block_id': bid, 'quote': sentence},
        42,
    ]


class LedgerTest(V1Case):
    def accept_and_read(self):
        self.drafted()
        self.desk.accept_prefix(group(self.desk), expected_canon_seq=0)
        return self.desk.update_memory()

    def test_claim_rows_cannot_be_updated_or_deleted(self):
        self.accept_and_read()
        claim = self.desk.memory()['accepted'][0]
        with self.assertRaises(sqlite3.IntegrityError):
            self.desk.connection.execute("UPDATE v1_claim SET quote='changed' WHERE claim_id=?", (claim['claim_id'],))
        with self.assertRaises(sqlite3.IntegrityError):
            self.desk.connection.execute("DELETE FROM v1_claim WHERE claim_id=?", (claim['claim_id'],))

    def test_a_correction_adds_a_row_and_never_touches_the_old_one(self):
        self.accept_and_read()
        old = self.desk.memory()['accepted'][0]
        before = dict(self.desk.connection.execute('SELECT * FROM v1_claim WHERE claim_id=?', (old['claim_id'],)).fetchone())
        new = self.desk.interpret(old['claim_id'], kind='testimony', speaker='witness', world_validity='unknown', note='attributed')
        after = dict(self.desk.connection.execute('SELECT * FROM v1_claim WHERE claim_id=?', (old['claim_id'],)).fetchone())
        self.assertEqual(before, after)
        self.assertNotIn(old['claim_id'], [c['claim_id'] for c in self.desk.memory()['accepted']])
        history = self.desk.claim_history(new)
        self.assertEqual([c['standing'] for c in history], ['accepted_derived', 'superseded'])
        with self.assertRaises(Refused) as again:
            self.desk.interpret(old['claim_id'], kind='event', speaker=None, world_validity='unknown', note='second try')
        self.assertEqual(again.exception.code, 'stale_pointer')

    def test_a_preview_never_enters_the_ledger(self):
        self.drafted()
        self.assertGreater(self.desk.read_provisional(1), 0)
        memory = self.desk.memory()
        self.assertTrue(memory['provisional'])
        self.assertTrue(all(c['standing'] == 'preview' for c in memory['provisional']))
        self.assertEqual(self.desk.connection.execute('SELECT count(*) FROM v1_claim').fetchone()[0], 0)

    def test_reading_the_same_text_twice_costs_one_model_call(self):
        self.drafted()
        first = self.desk.read_provisional(1)
        calls = len(self.provider.calls)
        self.assertEqual(self.desk.read_provisional(1), first)
        self.assertEqual(len(self.provider.calls), calls)

    def test_confirming_memory_reuses_a_matching_preview_without_a_second_model_call(self):
        self.drafted()
        self.desk.read_provisional(1)
        self.desk.accept_prefix(group(self.desk), expected_canon_seq=0)
        promotions = lambda: sum(1 for c in self.provider.calls if c['recipe'] == 'promotion')
        self.assertEqual(promotions(), 1)
        self.assertEqual(self.desk.update_memory(), {'imported': 3, 'obsolete': 0})
        self.assertEqual(promotions(), 3, 'episode 1 reused its preview; episodes 2 and 3 were read once each')
        first = [c for c in self.desk.memory()['accepted'] if c['narrative_ordinal'] == 1]
        self.assertTrue(first)
        self.assertTrue(all(c['standing'] == 'accepted_derived' for c in first))
        modes = [(r['mode'], r['source_extraction_id'] is not None) for r in self.desk.extraction_receipts()
                 if r['revision_id'] == self.desk.selection(1)['revision_id']]
        self.assertEqual(modes, [('preview', False), ('accepted', True)])

    def test_a_preview_of_replaced_text_is_no_longer_shown(self):
        self.drafted()
        self.desk.read_provisional(1)
        selection = self.desk.selection(1)
        revision = self.desk.revision(selection['revision_id'])
        blocks = [(b['block_id'], b['text']) for b in revision['blocks']]
        blocks[0] = (blocks[0][0], 'Leena wrote this opening herself.')
        self.desk.save_revision(1, base_revision_id=revision['revision_id'], blocks=blocks, expected_cas=selection['cas'])
        self.assertEqual(self.desk.memory()['provisional'], [])

    def test_an_older_schema_is_refused_not_half_read(self):
        self.desk.connection.execute("UPDATE v1_meta SET schema_version='v1_0001'")
        self.desk.close()
        with self.assertRaises(StoryError) as refused:
            Desk.open(self.path, provider=self.provider)
        self.assertIn('older', str(refused.exception))
        self.desk = Desk.create(Path(self.tmp.name) / 'fresh.db', provider=self.provider)


class ExtractionReceiptTest(SloppyCase):
    def test_every_returned_item_is_counted_and_none_vanishes(self):
        self.provider.output = sloppy_items
        self.accept_and_read()
        receipt = next(r for r in self.desk.extraction_receipts() if r['mode'] == 'accepted' and r['returned'] == 9)
        self.assertEqual(receipt['anchored_exact'] + receipt['anchored_loose'] + receipt['anchored_ambiguous']
                         + receipt['duplicates'] + receipt['quarantined'], receipt['returned'])
        self.assertEqual((receipt['anchored_exact'], receipt['anchored_loose'], receipt['anchored_ambiguous'],
                          receipt['duplicates'], receipt['quarantined']), (2, 1, 1, 1, 4))
        reasons = sorted(q['reason'] for q in self.desk.quarantine() if q['extraction_id'] == receipt['extraction_id'])
        self.assertEqual(reasons, ['invalid_kind', 'not_an_object', 'quote_not_found', 'testimony_needs_speaker'])

    def test_positions_are_found_in_code_and_the_stored_quote_is_the_source_text(self):
        self.provider.output = sloppy_items
        self.accept_and_read()
        claims = self.desk.memory()['accepted']
        self.assertTrue(claims)
        for claim in claims:
            block = next(b for b in self.desk.revision(claim['revision_id'])['blocks'] if b['block_id'] == claim['block_id'])
            self.assertEqual(block['text'][claim['start']:claim['end']], claim['quote'])
        by_subject = {c['subject']: c for c in claims if c['narrative_ordinal'] == 1}
        self.assertEqual(by_subject['quote only']['anchor'], 'exact')
        self.assertEqual(by_subject['wrong offsets']['anchor'], 'exact')
        self.assertEqual(by_subject['doubled space']['anchor'], 'loose')
        self.assertNotIn('  ', by_subject['doubled space']['quote'])
        self.assertEqual(by_subject['repeats in the block']['anchor'], 'ambiguous')

    def test_unreadable_output_is_recorded_and_the_task_stays_waiting(self):
        self.provider.output = 'this is not json'
        self.desk.accept_prefix(group(self.desk), expected_canon_seq=0)
        with self.assertRaises(Refused) as refused:
            self.desk.update_memory()
        self.assertEqual(refused.exception.code, 'unreadable_extraction')
        waiting = self.desk.connection.execute("SELECT count(*) FROM v1_outbox WHERE state='awaiting_authority'").fetchone()[0]
        self.assertEqual(waiting, 3)
        self.assertEqual([r['outcome'] for r in self.desk.extraction_receipts()], ['unreadable'])
        self.assertEqual([q['reason'] for q in self.desk.quarantine()], ['unreadable_output'])
        self.assertEqual(self.desk.memory()['accepted'], [])

    def test_a_list_is_required_not_an_object(self):
        self.provider.output = {'claims': []}
        self.desk.accept_prefix(group(self.desk), expected_canon_seq=0)
        with self.assertRaises(Refused) as refused:
            self.desk.update_memory()
        self.assertEqual(refused.exception.code, 'unreadable_extraction')


if __name__ == '__main__':
    unittest.main()
