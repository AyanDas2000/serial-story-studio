"""Offline guarded Merge tests. Only new synthetic SQLite files and injected I/O."""
import json
import tempfile
import unittest
from pathlib import Path
from serial_story.records import StoryError
from serial_story import budget

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / 'local/test-runs/merge-integration'

class SharedLedgerTests(unittest.TestCase):
    def setUp(self):
        RUN.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=RUN)
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'synthetic-ledger.db'

    def test_two_workspaces_share_cap_exact_replay_and_uncertainty(self):
        self.assertTrue(hasattr(budget, 'ProjectMergeLedger'), 'Missing project-shared Merge ledger')
        first = budget.ProjectMergeLedger(self.path)
        second = budget.ProjectMergeLedger(self.path)
        self.addCleanup(first.close)
        self.addCleanup(second.close)
        call = first.reserve('one', 'fingerprint-one', 600_000, {'workspace': 'story-one'})
        first.succeed('one', 550_000, {'text': 'Synthetic provider success'})
        self.assertEqual(second.reserve('one', 'fingerprint-one', 600_000, {}), first.get('one'))
        with self.assertRaises(StoryError):
            second.reserve('one', 'changed-fingerprint', 1, {})
        with self.assertRaises(StoryError):
            second.reserve('two', 'fingerprint-two', 500_000, {'workspace': 'story-two'})
        second.reserve('two', 'fingerprint-two', 450_000, {'workspace': 'story-two'})
        second.uncertain('two')
        self.assertEqual(first.snapshot()['remaining_micro_usd'], 0)
        with self.assertRaises(StoryError):
            first.reserve('three', 'fingerprint-three', 0, {})
        self.assertEqual(first.get('two')['status'], 'uncertain')

class RuntimeWireTests(unittest.TestCase):
    def request(self):
        return {'model': 'synthetic/concrete-v1', 'vendor': 'synthetic-vendor', 'prompt': 'Only inert story data',
                'max_output_tokens': 100, 'max_input_tokens': 2048}

    def response(self):
        return (200, json.dumps({'choices': [{'finish_reason': 'stop', 'message': {'content': '<script>inert prose</script>'}}],
            'usage': {'prompt_tokens': 20, 'completion_tokens': 10, 'total_tokens': 30, 'cost': 0.001},
            'routing': {'merge_fee_usd': 0.00005}}).encode(),
            {'x-merge-model': 'synthetic/concrete-v1', 'x-merge-vendor': 'synthetic-vendor', 'x-request-id': 'synthetic-request'})

    def test_runtime_auth_exact_route_actual_cost_and_disabled_gate(self):
        from serial_story.studio import merge
        self.assertTrue(hasattr(merge, 'MergeRuntime'), 'Missing callable authenticated runtime adapter')
        calls = []
        adapter = merge.MergeRuntime(enabled=True, key_supplier=lambda: 'SYNTHETIC-NOT-A-KEY',
                                     transport=lambda *args: (calls.append(args) or self.response()))
        result = adapter.exchange(self.request())
        self.assertEqual(result['charge_micro_usd'], 1050)
        self.assertEqual(result['provider_cost_usd'], 0.001)
        self.assertEqual(result['merge_fee_usd'], 0.00005)
        self.assertEqual(result['request_id'], 'synthetic-request')
        sent = json.loads(calls[0][3])
        self.assertEqual(set(sent), {'model', 'vendor', 'messages', 'max_tokens', 'stream', 'service_tier', 'service_tier_fallback', 'include_routing_metadata'})
        self.assertEqual(sent['service_tier'], 'standard')
        self.assertIs(sent['service_tier_fallback'], False)
        self.assertIs(sent['include_routing_metadata'], True)
        self.assertIn('Authorization', calls[0][2])
        forbidden = lambda *a: self.fail('disabled adapter touched key or transport')
        with self.assertRaises(merge.GenerationBlocked):
            merge.MergeRuntime(key_supplier=forbidden, transport=forbidden).exchange(self.request())

class AuthoringIntegrationTests(unittest.TestCase):
    def setUp(self):
        RUN.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=RUN)
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)

    def make(self):
        from serial_story.repository import SQLiteRepository
        from serial_story.service import StoryService
        from serial_story.studio.store import StudioStore
        from serial_story.studio.merge import MergeGateway, MergeRuntime
        import importlib.util
        self.assertIsNotNone(importlib.util.find_spec('serial_story.studio.authoring'), 'Missing consent-bound authoring integration')
        from serial_story.studio import authoring
        self.assertTrue(hasattr(authoring, 'MergeAuthoring'))
        repo = SQLiteRepository(self.folder / 'story.db')
        self.addCleanup(repo.connection.close)
        service = StoryService(repo)
        store = StudioStore(repo)
        service.initialize('Synthetic story')
        plan = store.save_plan({'beats': [{'intention': 'Open the synthetic door.'}]}, None)
        store.approve_plan(plan.id)
        store.save_settings(1, provider='merge', model='synthetic/concrete-v1', vendor='synthetic-vendor')
        self.metadata = {'model': 'synthetic/concrete-v1', 'availability_status': 'available', 'access_required': False,
            'vendors': [{'vendor': 'synthetic-vendor', 'availability_status': 'available', 'context_window': 200000,
                         'max_output_tokens': 4096, 'service_tiers': ['standard'], 'capabilities': {'supports_reasoning': False},
                         'pricing': {'currency': 'USD', 'unit': 'per_token', 'input_per_million': 2,
                                     'output_per_million': 10, 'cache_read_per_million': 0.2, 'cache_write_per_million': 2.5}}]}
        self.calls = []
        gateway = MergeGateway(transport=lambda *a: (200, json.dumps(self.metadata).encode()), key_supplier=lambda: 'SYNTHETIC')
        runtime = MergeRuntime(enabled=True, transport=lambda *a: (self.calls.append(a) or RuntimeWireTests().response()), key_supplier=lambda: 'SYNTHETIC')
        ledger = budget.ProjectMergeLedger(self.folder / 'ledger.db')
        self.addCleanup(ledger.close)
        controller = authoring.MergeAuthoring(enabled=True, gateway=gateway, runtime=runtime, ledger=ledger, qualification_supplier=lambda model, vendor: {"input_bound_qualified": True, "output_bound_qualified": True, "account_fee_bps": 500, "pricing_unit": "observed_per_million_fields", "reasoning": "disabled", "input_strategy": "utf8_bytes_plus_1024", "output_strategy": "max_tokens_total_billable", "max_input_tokens": 200000, "max_output_tokens": 4096})
        return repo, service, store, ledger, controller

    def test_explicit_preflight_confirm_persists_actual_prose_and_replays_without_advancement(self):
        repo, service, store, ledger, controller = self.make()
        preflight = controller.preflight(store, service, {'basis': store.basis(), 'operation_id': 'author-one'})
        self.assertEqual(self.calls, [])
        self.assertEqual(preflight['service_tier'], 'standard')
        self.assertGreater(preflight['reservation_micro_usd'], 1050)
        confirmation = {'preflight_id': preflight['preflight_id'], 'operation_id': 'author-one', 'confirm': True}
        result = controller.confirm(store, service, confirmation)
        self.assertFalse(result['synthetic'])
        self.assertEqual(store.pending_with_version()['text'], '<script>inert prose</script>')
        self.assertEqual(store.pending_with_version()['run']['source'], 'merge')
        self.assertEqual(store.pending_with_version()['run']['merge_receipt']['charge_micro_usd'], 1050)
        self.assertEqual(controller.confirm(store, service, confirmation), result)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(repo.accepted(), [])
        self.assertEqual(repo.story()['next_episode'], 1)
        self.assertEqual(ledger.snapshot()['spent_micro_usd'], 1050)

class DispatchOwnershipTests(unittest.TestCase):
    setUp = SharedLedgerTests.setUp
    def test_a_replayed_reserved_operation_can_only_be_claimed_once(self):
        ledger = budget.ProjectMergeLedger(self.path)
        self.addCleanup(ledger.close)
        ledger.reserve('one', 'same', 1000, {})
        self.assertTrue(hasattr(ledger, 'claim_dispatch'), 'Reserved replay must not redispatch')
        self.assertTrue(ledger.claim_dispatch('one'))
        self.assertFalse(ledger.claim_dispatch('one'))

class RecoveryTests(unittest.TestCase):
    setUp = AuthoringIntegrationTests.setUp
    make = AuthoringIntegrationTests.make
    def test_charged_success_survives_story_insert_failure_and_process_reopen(self):
        import sqlite3
        from serial_story.studio.authoring import MergeAuthoring
        repo, service, store, ledger, controller = self.make()
        flight = controller.preflight(store, service, {'basis': store.basis(), 'operation_id': 'recover'})
        payload = {'preflight_id': flight['preflight_id'], 'operation_id': 'recover', 'confirm': True}
        repo.connection.execute("CREATE TRIGGER synthetic_failure BEFORE INSERT ON studio_runs BEGIN SELECT RAISE(ABORT,'synthetic'); END")
        with self.assertRaises(sqlite3.Error):
            controller.confirm(store, service, payload)
        self.assertIsNone(store.pending_with_version())
        self.assertEqual(ledger.get('recover')['status'], 'succeeded')
        self.assertEqual(ledger.snapshot()['spent_micro_usd'], 1050)
        self.assertTrue(hasattr(controller, 'recovery'), 'Charged receipt must be discoverable after reload')
        recovery = controller.recovery(store)
        self.assertEqual(recovery['calls'][0]['confirmation'], payload)
        repo.connection.execute('DROP TRIGGER synthetic_failure')
        reopened = budget.ProjectMergeLedger(self.folder / 'ledger.db')
        self.addCleanup(reopened.close)
        restarted = MergeAuthoring(enabled=True, ledger=reopened, clock=lambda: 10**12,
                                   gateway=object(), runtime=object())
        result = restarted.confirm(store, service, payload)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(store.pending_with_version()['id'], result['revision_id'])

class ServerIntegrationTests(unittest.TestCase):
    def test_enabled_server_still_requires_preflight_confirmation(self):
        import http.client
        import threading
        from serial_story.studio.server import create_server
        from serial_story.studio.authoring import MergeAuthoring
        from serial_story.studio.merge import MergeGateway, MergeRuntime
        helper = AuthoringIntegrationTests()
        helper.setUp()
        self.addCleanup(helper.doCleanups)
        repo, service, store, ledger, controller = helper.make()
        story_path = helper.folder / 'story.db'
        ledger_path = helper.folder / 'ledger.db'
        def factory():
            return MergeAuthoring(enabled=True, gateway=controller.gateway, runtime=controller.runtime,
                                  ledger=budget.ProjectMergeLedger(ledger_path), qualification_supplier=controller.qualification_supplier)
        self.assertIn('merge_generation', __import__('inspect').signature(create_server).parameters,
                      'Missing explicit server startup gate')
        server = create_server(story_path, port=0, writes=True, merge_catalog=True,
                               merge_generation=True, authoring_factory=factory)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(lambda: (server.shutdown(), server.server_close(), thread.join(5)))
        def request(route, payload=None):
            conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
            try:
                headers = {'Origin': f'http://127.0.0.1:{server.server_port}', 'Content-Type': 'application/json', 'X-Studio-Token': token} if payload is not None else {}
                conn.request('POST' if payload is not None else 'GET', route,
                             json.dumps(payload).encode() if payload is not None else None, headers)
                response = conn.getresponse()
                return response.status, json.loads(response.read())
            finally:
                conn.close()
        token = ''
        token = request('/api/session')[1]['token']
        self.assertTrue(request('/api/state')[1]['generation_enabled'])
        payload = {'basis': store.basis(), 'operation_id': 'http-once'}
        self.assertEqual(request('/api/draft/generate', payload)[0], 400)
        self.assertEqual(helper.calls, [])
        status, flight = request('/api/merge/preflight', payload)
        self.assertEqual(status, 200)
        confirmation = {'preflight_id': flight['preflight_id'], 'operation_id': 'http-once', 'confirm': True}
        self.assertEqual(request('/api/merge/confirm', {**confirmation, 'confirm': False})[0], 400)
        self.assertEqual(helper.calls, [])
        self.assertEqual(request('/api/merge/confirm', confirmation)[0], 200)
        self.assertEqual(len(helper.calls), 1)
        self.assertEqual(request('/api/state')[1]['accepted'], [])
        status, lookup = request('/api/merge/model?model=synthetic%2Fconcrete-v1')
        self.assertEqual(status, 200)
        self.assertEqual(lookup['models'][0]['model'], 'synthetic/concrete-v1')

class MergeDOMTests(unittest.TestCase):
    def test_preflight_requires_clean_explicit_author_confirmation(self):
        import subprocess
        result = subprocess.run(['node', str(ROOT / 'tests/studio_merge_test.js'), str(ROOT / 'serial_story/assets/studio.js')], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

class SafetyRegressionTests(unittest.TestCase):
    setUp = AuthoringIntegrationTests.setUp
    make = AuthoringIntegrationTests.make
    def test_missing_cost_fee_unverified_route_and_invalid_usage_stay_uncertain(self):
        from serial_story.studio.merge import MergeRuntime
        repo, service, store, ledger, controller = self.make()
        for index, mutation in enumerate(('cost-null', 'fee-missing', 'wrong-route', 'usage-over-limit', 'duplicate-json', 'timeout', 'overcharge')):
            with self.subTest(mutation=mutation):
                isolated = budget.ProjectMergeLedger(self.folder / f'isolated-{index}.db')
                self.addCleanup(isolated.close)
                controller._ledger = isolated
                status, raw, headers = RuntimeWireTests().response()
                body = json.loads(raw)
                if mutation == 'cost-null': body['usage']['cost'] = None
                if mutation == 'fee-missing': del body['routing']['merge_fee_usd']
                if mutation == 'wrong-route': headers['x-merge-vendor'] = 'other-vendor'
                if mutation == 'usage-over-limit': body['usage']['completion_tokens'] = 99999
                if mutation == 'overcharge': body['usage']['cost'] = 2
                raw = json.dumps(body).encode()
                if mutation == 'duplicate-json': raw = b'{"choices":[],"usage":{},"usage":{}}'
                def transport(*args):
                    if mutation == 'timeout': raise TimeoutError('SYNTHETIC-SECRET must never appear')
                    return status, raw, headers
                controller.runtime = MergeRuntime(enabled=True, transport=transport, key_supplier=lambda: 'SYNTHETIC')
                flight = controller.preflight(store, service, {'basis': store.basis(), 'operation_id': f'bad-{index}'})
                confirmation = {'preflight_id': flight['preflight_id'], 'operation_id': f'bad-{index}', 'confirm': True}
                with self.assertRaises(StoryError) as problem:
                    controller.confirm(store, service, confirmation)
                self.assertNotIn('SYNTHETIC-SECRET', str(problem.exception))
                self.assertEqual(isolated.get(f'bad-{index}')['status'], 'uncertain')
                self.assertGreater(isolated.snapshot()['reserved_micro_usd'], 0)
                with self.assertRaises(StoryError): controller.confirm(store, service, confirmation)
                self.assertIsNone(store.pending_with_version())

    def test_stale_price_settings_and_expiration_refuse_before_dispatch(self):
        repo, service, store, ledger, controller = self.make()
        flight = controller.preflight(store, service, {'basis': store.basis(), 'operation_id': 'stale-price'})
        self.metadata['vendors'][0]['pricing']['output_per_million'] = 11
        with self.assertRaises(StoryError): controller.confirm(store, service, {'preflight_id': flight['preflight_id'], 'operation_id': 'stale-price', 'confirm': True})
        flight = controller.preflight(store, service, {'basis': store.basis(), 'operation_id': 'expired'})
        controller.clock = lambda: 10**12
        with self.assertRaises(StoryError): controller.confirm(store, service, {'preflight_id': flight['preflight_id'], 'operation_id': 'expired', 'confirm': True})
        controller.clock = __import__('time').time
        flight = controller.preflight(store, service, {'basis': store.basis(), 'operation_id': 'settings'})
        store.save_settings(2, prompt_template='Changed saved instructions')
        with self.assertRaises(StoryError): controller.confirm(store, service, {'preflight_id': flight['preflight_id'], 'operation_id': 'settings', 'confirm': True})
        self.assertEqual(self.calls, [])
        self.assertEqual(ledger.snapshot()['spent_micro_usd'], 0)
        self.assertEqual(ledger.snapshot()['reserved_micro_usd'], 0)

    def test_paid_disabled_never_opens_ledger_or_touches_provider(self):
        from serial_story.studio.authoring import MergeAuthoring
        controller = MergeAuthoring(gateway=object(), runtime=object(), ledger=object())
        with self.assertRaises(StoryError): controller.preflight(object(), object(), {})
        with self.assertRaises(StoryError): controller.confirm(object(), object(), {})

    def test_reasoning_default_without_verified_billing_bound_fails_closed(self):
        repo, service, store, ledger, controller = self.make()
        self.metadata['vendors'][0]['capabilities'] = {'reasoning': {'default_enabled': True}}
        with self.assertRaises(StoryError): controller.preflight(store, service, {'basis': store.basis(), 'operation_id': 'reasoning'})
        self.assertEqual(self.calls, [])

    def test_nul_prompt_is_known_before_dispatch_failure(self):
        from serial_story.studio.merge import MergeRuntime
        request = RuntimeWireTests().request()
        request['prompt'] = 'Bad\x00prompt'
        forbidden = lambda *a: self.fail('Invalid input must not resolve auth or transport')
        with self.assertRaises(StoryError):
            MergeRuntime(enabled=True, key_supplier=forbidden, transport=forbidden).exchange(request)

class RuntimePreparationTests(unittest.TestCase):
    def test_auth_supplier_failure_is_secret_safe_before_reservation(self):
        from serial_story.studio.merge import MergeRuntime
        def broken_key(): raise RuntimeError('SYNTHETIC-PRIVATE-VALUE')
        with self.assertRaises(StoryError) as problem:
            MergeRuntime(enabled=True, key_supplier=broken_key, transport=lambda *a: self.fail('no dispatch')).exchange(RuntimeWireTests().request())
        self.assertNotIn('SYNTHETIC-PRIVATE-VALUE', str(problem.exception))

class LedgerConcurrencyTests(unittest.TestCase):
    setUp = SharedLedgerTests.setUp
    def test_competing_connections_cannot_both_reserve(self):
        import threading
        barrier = threading.Barrier(2)
        results = []
        # Initialize before contenders to isolate reservation rather than DDL.
        budget.ProjectMergeLedger(self.path).close()
        def worker(operation):
            ledger = budget.ProjectMergeLedger(self.path)
            try:
                barrier.wait(3)
                try: ledger.reserve(operation, operation, 600000, {'workspace': operation})
                except StoryError: results.append('blocked')
                else: results.append('reserved')
            finally: ledger.close()
        threads = [threading.Thread(target=worker, args=(name,)) for name in ('story-a', 'story-b')]
        for thread in threads: thread.start()
        for thread in threads: thread.join(5)
        self.assertEqual(sorted(results), ['blocked', 'reserved'])
