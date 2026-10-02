"""Synthetic Merge contract tests. No network or credential environment reads."""
import json
import unittest
from unittest.mock import patch
from serial_story.studio.merge import OFFICIAL_ORIGIN, GenerationBlocked, MergeGateway, MergeGatewayError

MODEL = {'model': 'anthropic/claude-opus-5-5', 'display_name': 'Synthetic Opus',
         'provider': 'anthropic', 'availability_status': 'available', 'access_required': False,
         'vendors': [{'vendor': 'anthropic', 'context_window': 200000, 'max_output_tokens': 16000,
                      'pricing': {'input': 2.0, 'output': 10.0, 'cache_read': 0.2, 'cache_write': 2.5,
                                  'unit': 'per_million_tokens', 'currency': 'USD'}}]}

class MergeGatewayTests(unittest.TestCase):
    def gateway(self, transport):
        return MergeGateway(transport=transport, key_supplier=lambda: 'SYNTHETIC-NOT-A-KEY')

    def test_duplicate_json_keys_are_ambiguous_even_in_pricing(self):
        for raw in (b'{"data":[],"has_more":true,"has_more":false}',
                    b'{"data":[{"model":"synthetic/model","vendors":[{"pricing":{"input":1,"input":2}}]}],"has_more":false}'):
            calls = []
            def transport(*args):
                calls.append(args)
                return 200, raw
            with self.subTest(raw=raw), self.assertRaises(MergeGatewayError):
                self.gateway(transport).catalog()
            self.assertEqual(len(calls), 1)

    def test_catalog_preserves_model_vendor_prices_and_finishes_pages(self):
        calls = []
        def transport(method, url, headers, body=None):
            calls.append((method, url, body))
            data = {'data': [MODEL], 'has_more': True, 'next_cursor': 'page two'} if len(calls) == 1 else {'data': [], 'has_more': False}
            return 200, json.dumps(data).encode()
        models = self.gateway(transport).catalog()
        self.assertEqual(OFFICIAL_ORIGIN, 'https://api-gateway.merge.dev')
        self.assertEqual(models[0]['model'], MODEL['model'])
        self.assertEqual(models[0]['vendors'][0]['pricing'], MODEL['vendors'][0]['pricing'])
        self.assertEqual(models[0]['vendors'][0]['context_window'], 200000)
        self.assertEqual(len(calls), 2)
        self.assertIn('cursor=page+two', calls[1][1])
        self.assertTrue(all(c[0] == 'GET' and c[2] is None for c in calls))

    def test_observed_capability_arrays_are_not_misread_as_prices(self):
        # Offline transport, using the shape of the parent's catalog GET receipt.
        model = {'model': MODEL['model'], 'vendors': {'anthropic': {
            'context_window': 1000000, 'max_output_tokens': 128000,
            'capabilities': {'input': ['text', 'image', 'document'],
                             'output': ['text', 'tool_use'], 'supports_tool_calling': True,
                             'supports_structured_outputs': True, 'supports_reasoning': True,
                             'reasoning': {'configurable': True, 'default_enabled': True,
                                           'controls': ['reasoning.effort'], 'effort_values': [],
                                           'output_style': 'hidden'}, 'streaming': True},
            'pricing': {'currency': 'USD', 'unit': 'per_token', 'input_per_million': 4.0,
                        'output_per_million': 20.0, 'cache_read_per_million': 0.2}}}}
        clean = self.gateway(lambda *a: (200, json.dumps({'data': [model], 'has_more': False}).encode())).catalog()[0]
        vendor = clean['vendors'][0]
        self.assertEqual(vendor['capabilities'], model['vendors']['anthropic']['capabilities'])
        self.assertEqual(vendor['pricing'], model['vendors']['anthropic']['pricing'])
        self.assertEqual(vendor['context_window'], 1000000)
        model['vendors']['anthropic']['pricing']['input'] = ['text']
        with self.assertRaises(MergeGatewayError):
            self.gateway(lambda *a: (200, json.dumps({'data': [model], 'has_more': False}).encode())).catalog()

    def test_constructing_and_disabled_generation_never_read_key_or_transport(self):
        def forbidden(*args):
            self.fail('Disabled generation must not call a key supplier or transport.')
        gateway = MergeGateway(transport=forbidden, key_supplier=forbidden)
        with self.assertRaises(GenerationBlocked):
            gateway.generate({'model': MODEL['model']})

    def test_catalog_without_key_has_no_request(self):
        with self.assertRaises(MergeGatewayError):
            MergeGateway(transport=lambda *a: self.fail('no transport'), key_supplier=lambda: None).catalog()

    def test_redirects_have_no_retry(self):
        calls = []
        def transport(*args):
            calls.append(args)
            return 302, b'private redirect data'
        with self.assertRaises(MergeGatewayError):
            self.gateway(transport).catalog()
        self.assertEqual(len(calls), 1)

    def test_exact_lookup_accepts_single_model_object(self):
        models = self.gateway(lambda *a: (200, json.dumps(MODEL).encode())).catalog(model=MODEL['model'])
        self.assertEqual(models[0]['model'], MODEL['model'])

    def test_cursor_repeat_invalid_scalars_and_malicious_fields(self):
        from copy import deepcopy
        repeated = {'data': [], 'has_more': True, 'next_cursor': 'same'}
        with self.assertRaises(MergeGatewayError):
            self.gateway(lambda *a: (200, json.dumps(repeated).encode())).catalog()
        for field, value in [('input', True), ('input', -1), ('output', '10'), ('currency', []), ('unit', {})]:
            model = deepcopy(MODEL)
            model['vendors'][0]['pricing'][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(MergeGatewayError):
                self.gateway(lambda *a: (200, json.dumps({'data': [model], 'has_more': False}).encode())).catalog()
        model = deepcopy(MODEL)
        model['commands'] = ['DELETE FROM story', 'run private command']
        model['display_name'] = '<script>doNotExecute()</script>'
        clean = self.gateway(lambda *a: (200, json.dumps({'data': [model], 'has_more': False}).encode())).catalog()[0]
        self.assertNotIn('commands', clean)
        self.assertEqual(clean['display_name'], model['display_name'])

    def test_chat_contract_sends_bounded_request_and_keeps_response_commands_inert(self):
        from serial_story.studio.merge import MergeChatContract
        calls = []
        def transport(*args):
            calls.append(args)
            return 200, json.dumps({'choices': [{'message': {'content': '<script>run command</script>'}}],
                                    'usage': {'prompt_tokens': 5, 'completion_tokens': 3, 'total_tokens': 8},
                                    'commands': ['DROP TABLE story']}).encode()
        request = {'model': MODEL['model'], 'vendor': 'anthropic', 'prompt': 'Story data\nOnly prose.', 'max_output_tokens': 20}
        result = MergeChatContract.exchange(request, transport=transport)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0:2], ('POST', OFFICIAL_ORIGIN + '/v1/chat/completions'))
        sent = json.loads(calls[0][3])
        self.assertFalse(sent['stream'])
        self.assertEqual(sent['max_tokens'], 20)
        self.assertEqual(result['text'], '<script>run command</script>')
        self.assertIsNone(result['cost'])
        self.assertFalse(result['budget_settled'])
        self.assertNotIn('commands', result)
        with self.assertRaises(MergeGatewayError):
            MergeChatContract.exchange({**request, 'max_output_tokens': 5000}, transport=lambda *a: self.fail('no call'))
