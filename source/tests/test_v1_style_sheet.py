"""Editable writing-style sheet (storyboard S12): versioned, recorded on each draft, checked after each draft."""
import sqlite3
import unittest

from serial_story.v1.desk import Refused
from tests.test_v1_slice import V1Case

SHEET = 'Close third person, short paragraphs, dry humour. Keep dialogue plain.'
AVOID = ['\u2014', 'suddenly', 'a testament to']


class SheetVersionTest(V1Case):
    def test_each_change_is_a_new_immutable_version_and_a_repeat_is_not(self):
        self.assertIsNone(self.desk.style_sheet())
        one = self.desk.save_style_sheet(SHEET, AVOID)
        self.assertEqual(self.desk.save_style_sheet(SHEET, AVOID), one)
        two = self.desk.save_style_sheet(SHEET + ' No semicolons.', AVOID)
        self.assertEqual((one, two), (1, 2))
        self.assertEqual(self.desk.style_sheet(), {'version': 2, 'body': SHEET + ' No semicolons.', 'avoid': AVOID})
        self.assertEqual([v['version'] for v in self.desk.style_sheet_versions()], [2, 1])
        with self.assertRaises(sqlite3.IntegrityError):
            self.desk.connection.execute("UPDATE v1_style_sheet SET body='x' WHERE version=1")
        with self.assertRaises(sqlite3.IntegrityError):
            self.desk.connection.execute('DELETE FROM v1_style_sheet WHERE version=1')

    def test_bad_sheets_are_refused(self):
        for body, avoid in (('', []), ('x' * 4001, []), (SHEET, ['a'] * 2), (SHEET, ['']), (SHEET, ['x' * 41]),
                            (SHEET, [str(n) for n in range(41)]), (SHEET, 'suddenly'), (5, [])):
            with self.assertRaises(Refused) as refused:
                self.desk.save_style_sheet(body, avoid)
            self.assertEqual(refused.exception.code, 'invalid_style_sheet', (str(body)[:10], avoid))
        self.assertIsNone(self.desk.style_sheet())


class SheetInDraftsTest(V1Case):
    def prompts(self):
        return [r['prompt'] for r in self.desk.connection.execute('SELECT prompt FROM v1_job ORDER BY rowid')]

    def test_without_a_sheet_the_prompt_has_no_sheet_section(self):
        self.drafted()
        self.assertTrue(all("AUTHOR'S STYLE SHEET" not in p for p in self.prompts()))
        self.assertIsNone(self.desk.style_version_for(self.desk.selection(1)['revision_id']))

    def test_a_draft_carries_the_sheet_and_records_the_version_it_used(self):
        self.desk.save_style_sheet(SHEET, AVOID)
        self.drafted()
        prompt = self.prompts()[0]
        self.assertIn("AUTHOR'S STYLE SHEET", prompt)
        self.assertIn(SHEET, prompt)
        self.assertIn('Never use: \u2014; suddenly; a testament to', prompt)
        self.assertLess(prompt.index("AUTHOR'S STYLE SHEET"), prompt.index('OUTPUT RULES'))
        self.assertEqual(self.desk.style_version_for(self.desk.selection(1)['revision_id']), 1)

    def test_a_later_sheet_changes_later_drafts_not_the_record_of_earlier_ones(self):
        self.desk.save_style_sheet(SHEET, AVOID)
        self.drafted()
        self.desk.save_style_sheet(SHEET + ' Prefer concrete nouns.', AVOID)
        alternative = self.desk.redraft(2)
        self.assertEqual(self.desk.style_version_for(self.desk.selection(2)['revision_id']), 1)
        self.assertEqual(self.desk.style_version_for(alternative), 2)

    def test_the_avoid_list_is_checked_after_the_draft_and_flags_the_episode(self):
        self.desk.save_style_sheet(SHEET, AVOID)
        self.drafted()
        selection = self.desk.selection(1)
        revision = self.desk.revision(selection['revision_id'])
        blocks = [(b['block_id'], b['text']) for b in revision['blocks']]
        blocks[0] = (blocks[0][0], 'Leena paused \u2014 and then, Suddenly, spoke.')
        self.desk.save_revision(1, base_revision_id=revision['revision_id'], blocks=blocks, expected_cas=selection['cas'])
        episodes = {e['ordinal']: e for e in self.desk.snapshot()['episodes']}
        self.assertEqual(episodes[1]['style_hits'], ['\u2014', 'suddenly'])
        self.assertEqual(episodes[2]['style_hits'], [])
        self.assertEqual(self.desk.snapshot()['style_sheet']['version'], 1)

    def test_a_sheet_cannot_carry_a_guarded_word_and_a_secret_cannot_guard_a_word_in_the_sheet(self):
        self.desk.add_secret(label='Oren', body='Oren is alive.', canaries=['Zorvathian'])
        with self.assertRaises(Refused) as refused:
            self.desk.save_style_sheet('Never describe the Zorvathian crest.', [])
        self.assertEqual(refused.exception.code, 'secret_in_input')
        with self.assertRaises(Refused) as refused:
            self.desk.save_style_sheet(SHEET, ['zorvathian'])
        self.assertEqual(refused.exception.code, 'secret_in_input')
        self.assertIsNone(self.desk.style_sheet())
        self.desk.save_style_sheet('Mention the Quillfeather crest sparingly.', [])
        with self.assertRaises(Refused) as refused:
            self.desk.add_secret(label='Another', body='x is true.', canaries=['Quillfeather'])
        self.assertEqual(refused.exception.code, 'canary_already_visible')


if __name__ == '__main__':
    unittest.main()
