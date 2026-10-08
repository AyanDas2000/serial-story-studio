"""Draft requests are laid out for prefix caching: stable first, volatile last, cache markers on stable blocks."""
import json
import unittest

from tests.test_v1_slice import V1Case


def group(desk, ordinals):
    return [(n, desk.selection(n)['revision_id'], desk.selection(n)['sha256']) for n in ordinals]


class CacheLayoutTest(V1Case):
    def sent(self):
        return [c for c in self.provider.calls if c['recipe'] == 'sequential_draft']

    def test_the_system_block_and_shared_episodes_repeat_exactly_across_a_batch(self):
        self.drafted()
        two, three = self.sent()[1]['params']['messages'], self.sent()[2]['params']['messages']
        one = self.sent()[0]['params']['messages']
        self.assertEqual(two[0], three[0])
        self.assertEqual(two[1]['content'], three[1]['content'], 'episode 1 is the same message in both requests')
        self.assertEqual([m['role'] for m in three], ['system', 'user', 'user', 'user'])
        self.assertNotEqual(one[0]['content'], two[0]['content'], 'episode 1 says there is no earlier story; later ones do not')
        for messages in (one, two, three):
            self.assertNotIn("THIS EPISODE'S JOB", messages[0]['content'])
            self.assertNotIn('OUTPUT RULES', messages[0]['content'])
            self.assertIn("THIS EPISODE'S JOB", messages[-1]['content'])
            self.assertTrue(messages[-1]['content'].rstrip().endswith('- Return the Title line and the episode text, nothing else.'))

    def test_markers_sit_on_the_last_accepted_episode_and_the_last_predecessor(self):
        self.drafted()
        self.desk.accept_prefix(group(self.desk, (1,)), expected_canon_seq=0)
        self.desk.redraft(3)
        messages = self.sent()[-1]['params']['messages']
        self.assertEqual([m['cache'] for m in messages], [True, True, True, False], 'system, accepted 1, last predecessor 2, final')
        self.desk.accept_prefix(group(self.desk, (2,)), expected_canon_seq=1)
        self.desk.redraft(3)
        messages = self.sent()[-1]['params']['messages']
        self.assertEqual([m['cache'] for m in messages], [True, False, True, False], 'system, 1, episode 2 (accepted and last), final')

    def test_the_stored_prompt_is_the_joined_messages_and_the_job_keeps_them(self):
        self.drafted()
        job = self.desk.connection.execute('SELECT * FROM v1_job ORDER BY rowid DESC LIMIT 1').fetchone()
        messages = self.desk.job_messages(job['job_id'])
        self.assertEqual(job['prompt'], '\n\n'.join(m['content'] for m in messages))
        self.assertEqual(json.dumps(self.sent()[-1]['params']['messages']), json.dumps(messages))
        self.assertTrue(all(set(m) == {'role', 'content', 'cache'} for m in messages))

    def test_a_changed_style_sheet_changes_only_the_system_block(self):
        self.drafted()
        before = self.sent()[1]['params']['messages']
        self.desk.save_style_sheet('Keep sentences short.', [])
        self.desk.redraft(2)
        after = self.sent()[-1]['params']['messages']
        self.assertNotEqual(before[0]['content'], after[0]['content'])
        self.assertEqual(before[1:-1], after[1:-1])


class SnapshotMemoryStateTest(V1Case):
    def test_an_approved_episode_waits_until_its_story_changes_are_read(self):
        self.drafted()
        self.desk.accept_prefix(group(self.desk, (1,)), expected_canon_seq=0)
        episodes = {e['ordinal']: e for e in self.desk.snapshot()['episodes']}
        self.assertEqual((episodes[1]['memory_state'], episodes[2]['memory_state']), ('waiting', None))
        self.desk.update_memory()
        snapshot = self.desk.snapshot()
        self.assertEqual(snapshot['episodes'][0]['memory_state'], 'read')
        self.assertTrue(snapshot['extractions'])
        self.assertEqual(snapshot['style_versions'], [])


if __name__ == '__main__':
    unittest.main()
