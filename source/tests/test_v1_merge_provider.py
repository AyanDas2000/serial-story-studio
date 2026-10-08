import json
import tempfile
import unittest
from pathlib import Path

from serial_story.v1.merge_provider import ROUTES, MergeProvider, _strip_fence, find_key, load_env_key, role_for
from serial_story.v1.provider import AnswerUnusable, GenerationRequest, NotSent, ProviderUnavailable


def good_body(model='anthropic/claude-sonnet-5-5', vendor='anthropic', cost=0.01, fee=0.0, text='Hello.', finish='stop'):
    return {'choices': [{'message': {'content': text}, 'finish_reason': finish}],
            'usage': {'prompt_tokens': 100, 'completion_tokens': 50, 'cost': cost,
                      'prompt_tokens_details': {'cached_tokens': 40, 'cache_write_tokens': 0}},
            'routing': {'model_used': model, 'vendor_used': vendor, 'merge_fee_usd': fee, 'reasoning_effort_applied': 'none'}}


class FakeTransport:
    def __init__(self, *replies):
        self.replies, self.sent = list(replies), []

    def __call__(self, payload):
        self.sent.append(payload)
        status, body = self.replies.pop(0)
        return status, body, {'x-request-id': 'req_1'}, 0.5


def draft_request(messages=None):
    messages = messages if messages is not None else [
        {'role': 'system', 'content': 'SPINE', 'cache': True}, {'role': 'user', 'content': 'JOB'}]
    return GenerationRequest('sequential_draft', 'x', 'k', params={'messages': messages})


class MergeProviderTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.log = Path(self.dir.name) / 'spend.jsonl'

    def provider(self, transport, cap=1.0):
        return MergeProvider(transport=transport, spend_log=self.log, cap_usd=cap)

    def rows(self):
        return [json.loads(line) for line in self.log.read_text(encoding='utf-8').splitlines()]

    def test_good_call_returns_text_and_charge_and_logs_without_reply(self):
        t = FakeTransport((200, good_body(cost=0.01, fee=0.002, text='SECRET REPLY')))
        result = self.provider(t).generate(draft_request())
        self.assertEqual(result.text, 'SECRET REPLY')
        self.assertEqual(result.charge_micro_usd, 12000)
        row = self.rows()[0]
        self.assertEqual(row['outcome'], 'ok')
        self.assertNotIn('SECRET REPLY', self.log.read_text(encoding='utf-8'))
        self.assertNotIn('Authorization', self.log.read_text(encoding='utf-8'))

    def test_cache_marker_goes_on_marked_messages_only(self):
        t = FakeTransport((200, good_body()))
        self.provider(t).generate(draft_request())
        sent = t.sent[0]['messages']
        self.assertEqual(sent[0]['cache_control'], {'type': 'ephemeral'})
        self.assertNotIn('cache_control', sent[1])
        self.assertNotIn('reasoning_effort', t.sent[0])

    def test_extraction_uses_luna_with_flat_effort_none_and_strips_fence(self):
        body = good_body(model='openai/gpt-6-luna', vendor='openai', text='```json\n[]\n```')
        t = FakeTransport((200, body))
        req = GenerationRequest('promotion', '', 'k', params={'blocks': [{'block_id': 'b1', 'text': 'Text.'}]})
        result = self.provider(t).generate(req)
        self.assertEqual(result.text, '[]')
        self.assertEqual(t.sent[0]['reasoning_effort'], 'none')
        self.assertNotIn('reasoning', t.sent[0])
        self.assertEqual(t.sent[0]['model'], 'openai/gpt-6-luna')

    def test_cap_stops_a_call_before_sending(self):
        t = FakeTransport()
        with self.assertRaises(NotSent):
            self.provider(t, cap=0.01).generate(draft_request())
        self.assertEqual(t.sent, [])
        self.assertEqual(self.rows()[0]['outcome'], 'not_sent_cap')

    def test_spent_money_counts_toward_the_cap(self):
        t = FakeTransport((200, good_body(cost=0.95)), )
        p = self.provider(t, cap=1.0)
        p.generate(draft_request())
        with self.assertRaises(NotSent):
            p.generate(draft_request())
        self.assertEqual(len(t.sent), 1)

    def test_cap_must_be_in_range(self):
        for cap in (0, -1, 5.01):
            with self.assertRaises(ValueError):
                self.provider(FakeTransport(), cap=cap)

    def test_refusal_is_not_sent_and_unclear_failures_are_unverified(self):
        with self.assertRaises(NotSent):
            self.provider(FakeTransport((403, {'error': {'code': 'model_not_allowed'}}))).generate(draft_request())
        self.assertEqual(self.rows()[-1]['error_code'], 'model_not_allowed')
        for status in (500, 502, 504, 0):
            with self.assertRaises(ProviderUnavailable) as caught:
                self.provider(FakeTransport((status, 'oops'))).generate(draft_request())
            self.assertNotIsInstance(caught.exception, NotSent)
            self.assertEqual(self.rows()[-1]['outcome'], 'unverified')

    def test_missing_cost_is_unverified(self):
        body = good_body()
        del body['usage']['cost']
        with self.assertRaises(ProviderUnavailable):
            self.provider(FakeTransport((200, body))).generate(draft_request())
        self.assertEqual(self.rows()[-1]['outcome'], 'unverified_cost')

    def test_wrong_model_is_discarded(self):
        body = good_body(model='anthropic/claude-haiku-4-5')
        with self.assertRaises(ProviderUnavailable):
            self.provider(FakeTransport((200, body))).generate(draft_request())
        self.assertEqual(self.rows()[-1]['outcome'], 'route_mismatch')

    def test_cut_off_or_empty_answers_are_billed_and_discarded(self):
        for body in (good_body(finish='length'), good_body(text='  ')):
            with self.assertRaises(AnswerUnusable):
                self.provider(FakeTransport((200, body))).generate(draft_request())
            self.assertEqual(self.rows()[-1]['outcome'], 'unusable_answer')
        self.assertGreater(self.provider(FakeTransport()).spent_usd(), 0)

    def test_rewrite_preamble_and_echoed_original_are_stripped(self):
        block = '"Don\'t touch the lock," Nadiya said. Her voice shook.'
        messy = f'Hmm, that needs tightening. Here it is:\n\n{block}\n\n"Nobody touches my crime scene," Nadiya snapped.'
        result = self.provider(FakeTransport((200, good_body(text=messy)))).generate(
            GenerationRequest('polish_rewrite', 'tighten it', 'k', params={'block_text': block}))
        self.assertEqual(result.text, '"Nobody touches my crime scene," Nadiya snapped.')

    def test_rewrite_intro_line_without_echo_is_stripped(self):
        block = 'The lock clicked open.'
        messy = 'Sure, here is the tightened paragraph:\nThe lock clicked. Nadiya froze.'
        result = self.provider(FakeTransport((200, good_body(text=messy)))).generate(
            GenerationRequest('polish_rewrite', 'tighten it', 'k', params={'block_text': block}))
        self.assertEqual(result.text, 'The lock clicked. Nadiya froze.')

    def test_rewrite_starting_with_dialogue_is_kept_intact(self):
        block = 'The lock clicked open.'
        clean = '"Stop," she said. "Walk away from the door."'
        result = self.provider(FakeTransport((200, good_body(text=clean)))).generate(
            GenerationRequest('polish_rewrite', 'tighten it', 'k', params={'block_text': block}))
        self.assertEqual(result.text, clean)

    def test_rewrite_that_returns_the_original_unchanged_is_unusable(self):
        block = 'The lock clicked open.'
        with self.assertRaises(AnswerUnusable):
            self.provider(FakeTransport((200, good_body(text=block)))).generate(
                GenerationRequest('polish_rewrite', 'tighten it', 'k', params={'block_text': block}))
        self.assertEqual(self.rows()[-1]['outcome'], 'unusable_rewrite')

    def test_draft_without_frozen_messages_is_not_sent(self):
        t = FakeTransport()
        with self.assertRaises(NotSent):
            self.provider(t).generate(draft_request(messages=[]))
        self.assertEqual(t.sent, [])

    def test_roles(self):
        self.assertEqual(role_for('sequential_draft'), 'draft')
        self.assertEqual(role_for('promotion'), 'extract')
        self.assertEqual(role_for('propose_spine'), 'plan')
        self.assertEqual(role_for('block_rewrite'), 'polish')
        with self.assertRaises(ValueError):
            role_for('nope')
        self.assertEqual(ROUTES['extract'].effort, 'none')

    def test_recent_calls_list_newest_first_without_reply_text(self):
        t = FakeTransport((200, good_body(text='PRIVATE')), (200, good_body(cost=0.02)))
        p = self.provider(t)
        p.generate(draft_request())
        p.generate(draft_request())
        rows = p.recent()
        self.assertEqual([r['cost_usd'] for r in rows], [0.02, 0.01])
        self.assertNotIn('PRIVATE', json.dumps(rows))
        self.assertEqual(p.budget()['spent_usd'], 0.03)

    def test_two_calls_at_once_cannot_both_spend_the_same_money(self):
        import threading
        import time

        class Slow(FakeTransport):
            def __call__(self, payload):
                time.sleep(0.3)
                return super().__call__(payload)

        t = Slow((200, good_body(cost=0.01)), (200, good_body(cost=0.01)))
        p = self.provider(t, cap=0.1)
        outcomes = []

        def go():
            try:
                p.generate(draft_request())
                outcomes.append('sent')
            except NotSent:
                outcomes.append('held back')

        threads = [threading.Thread(target=go) for _ in range(2)]
        for th in threads:
            th.start()
        for th in threads:
            th.join(20)
        self.assertEqual(sorted(outcomes), ['held back', 'sent'])
        self.assertEqual(len(t.sent), 1)

    def test_an_unverified_call_keeps_its_hold_and_a_refusal_releases_it(self):
        p = self.provider(FakeTransport((502, 'oops')), cap=1.0)
        with self.assertRaises(ProviderUnavailable):
            p.generate(draft_request())
        self.assertGreater(p.budget()['held_usd'], 0)
        self.assertEqual(p.budget()['spent_usd'], 0)
        q = self.provider(FakeTransport((403, {'error': {'code': 'x'}})), cap=1.0)
        held_before = q.budget()['held_usd']
        with self.assertRaises(NotSent):
            q.generate(draft_request())
        self.assertEqual(q.budget()['held_usd'], held_before)

    def test_a_settled_call_replaces_its_hold_with_the_real_charge(self):
        p = self.provider(FakeTransport((200, good_body(cost=0.01, fee=0.002))), cap=1.0)
        p.generate(draft_request())
        self.assertEqual((p.budget()['spent_usd'], p.budget()['held_usd']), (0.012, 0))

    def test_a_connection_error_is_unverified_not_a_crash(self):
        def broken(payload):
            raise OSError('reset')
        p = self.provider(broken, cap=1.0)
        with self.assertRaises(ProviderUnavailable):
            p.generate(draft_request())
        self.assertGreater(p.budget()['held_usd'], 0)

    def test_chat_sends_the_messages_the_desk_built(self):
        t = FakeTransport((200, good_body(model='anthropic/claude-opus-5-5', text='Fine.')))
        msgs = [{'role': 'system', 'content': 'EDITOR'}, {'role': 'user', 'content': 'CONTEXT'}, {'role': 'user', 'content': 'ASK'}]
        self.provider(t).generate(GenerationRequest('converse', 'ASK', 'k', params={'messages': msgs}))
        self.assertEqual([m['content'] for m in t.sent[0]['messages']], ['EDITOR', 'CONTEXT', 'ASK'])

    def test_chat_runs_on_opus_and_drafting_on_sonnet(self):
        self.assertEqual(ROUTES['chat'].model, 'anthropic/claude-opus-5-5')
        self.assertEqual(ROUTES['draft'].model, 'anthropic/claude-sonnet-5-5')

    def test_strip_fence_and_env_key(self):
        self.assertEqual(_strip_fence('```\n[1]\n```'), '[1]')
        self.assertEqual(_strip_fence(' [1] '), '[1]')
        env = Path(self.dir.name) / '.env'
        env.write_text('OTHER=1\nMERGE_GATEWAY_API_KEY="abc"\n', encoding='utf-8')
        self.assertEqual(load_env_key(env), 'abc')
        with self.assertRaises(ProviderUnavailable):
            load_env_key(env, 'MISSING')

    def test_find_key_prefers_the_file_then_the_environment_and_never_returns_empty(self):
        env = Path(self.dir.name) / '.env'
        self.assertEqual(find_key(env, {'MERGE_GATEWAY_API_KEY': ' from-env '}), 'from-env')
        env.write_text('MERGE_GATEWAY_API_KEY=\n', encoding='utf-8')
        self.assertEqual(find_key(env, {'MERGE_GATEWAY_API_KEY': 'from-env'}), 'from-env')
        env.write_text('MERGE_GATEWAY_API_KEY=from-file\n', encoding='utf-8')
        self.assertEqual(find_key(env, {'MERGE_GATEWAY_API_KEY': 'from-env'}), 'from-file')
        env.unlink()
        with self.assertRaises(ProviderUnavailable) as caught:
            find_key(env, {})
        self.assertNotIn('from-', str(caught.exception))


if __name__ == '__main__':
    unittest.main()
