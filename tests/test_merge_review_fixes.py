"""Independent review regressions, synthetic offline I/O only."""
import copy
import json
import sqlite3
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
import test_merge_authoring as baseline
from serial_story.records import StoryError
from serial_story.studio.merge import MergeGateway, MergeRuntime
from serial_story.studio.authoring import MergeAuthoring
from serial_story.budget import ProjectMergeLedger


def synthetic_qualification(model, vendor):
    return {"input_bound_qualified": True, "output_bound_qualified": True,
            "account_fee_bps": 500, "pricing_unit": "observed_per_million_fields",
            "reasoning": "disabled", "input_strategy": "utf8_bytes_plus_1024", "output_strategy": "max_tokens_total_billable", "max_input_tokens": 200000, "max_output_tokens": 4096}

class ReviewFixTests(unittest.TestCase):
    def setUp(self):
        run = Path(__file__).resolve().parents[1] / 'local/test-runs/merge-review-fixes-20261002'
        run.mkdir(parents=True, exist_ok=True)
        self.folder = Path(tempfile.mkdtemp(prefix='synthetic-', dir=run))
    make = baseline.AuthoringIntegrationTests.make

    def test_production_and_unknown_reasoning_refuse_before_reserve(self):
        repo, service, store, ledger, controller = self.make()
        controller.qualification_supplier = None
        with self.assertRaises(StoryError):
            controller.preflight(store, service, {"basis": store.basis(), "operation_id": "unqualified"})
        self.assertEqual(ledger.snapshot()["reserved_micro_usd"], 0)
        controller.qualification_supplier = synthetic_qualification
        for capabilities in ({}, {"supports_reasoning": True}, {"reasoning": {"default_enabled": True}}):
            self.metadata["vendors"][0]["capabilities"] = capabilities
            with self.subTest(capabilities=capabilities), self.assertRaises(StoryError):
                controller.preflight(store, service, {"basis": store.basis(), "operation_id": "unknown"})
        self.assertEqual(self.calls, [])

    def test_price_schedules_fingerprint_and_expensive_cache_read(self):
        repo, service, store, ledger, controller = self.make()
        payload = {"basis": store.basis(), "operation_id": "price"}
        prices = self.metadata["vendors"][0]["pricing"]
        prices["cache_read_per_million"] = 100
        flight = controller.preflight(store, service, payload)
        expected = __import__("math").ceil((flight["max_input_tokens"] * 100 + flight["max_output_tokens"] * 10) * 1.05)
        self.assertGreaterEqual(flight["reservation_micro_usd"], expected)
        for field in ("long_context", "cache_write_1h", "schedule", "input_per_second"):
            prices[field] = {"threshold": 100, "rate": 1000}
            clean = controller.gateway.catalog(model=self.metadata["model"])[0]
            self.assertIn(field, clean["vendors"][0]["pricing"])
            with self.subTest(field=field), self.assertRaises(StoryError):
                controller.preflight(store, service, payload)
            del prices[field]
        prices["batch"] = {"input_per_million": 1, "output_per_million": 5}
        before = controller.preflight(store, service, payload)
        prices["batch"]["output_per_million"] = 6
        after = controller.preflight(store, service, payload)
        self.assertNotEqual(before["metadata_sha256"], after["metadata_sha256"])
        prices["input"] = 0.000002
        with self.assertRaises(StoryError): controller.preflight(store, service, payload)
        self.assertEqual(self.calls, [])

    def test_invalid_prose_retains_charge_without_saving_draft(self):
        repo, service, store, ledger, controller = self.make()
        for index, kind in enumerate(("tool", "nontext", "length", "content_filter", "refusal", "usage", "route", "overcharge")):
            isolated = ProjectMergeLedger(self.folder / f"content-{index}.db")
            self.addCleanup(isolated.close)
            controller._ledger = isolated
            status, raw, headers = baseline.RuntimeWireTests().response()
            body = json.loads(raw)
            choice = body["choices"][0]
            choice["finish_reason"] = "stop"
            if kind == "tool": choice["message"]["tool_calls"] = [{"id": "inert"}]
            if kind == "nontext": choice["message"]["content"] = [{"text": "inert"}]
            if kind in ("length", "content_filter"): choice["finish_reason"] = kind
            if kind == "refusal": choice["message"]["refusal"] = "Cannot comply"
            if kind == "usage": body["usage"]["total_tokens"] = 999
            if kind == "route": headers["x-merge-vendor"] = "different"
            if kind == "overcharge": body["usage"]["cost"] = 2
            controller.runtime = MergeRuntime(enabled=True, key_supplier=lambda: "SYNTHETIC", transport=lambda *args: (status, json.dumps(body).encode(), headers))
            flight = controller.preflight(store, service, {"basis": store.basis(), "operation_id": kind})
            with self.subTest(kind=kind), self.assertRaises(StoryError):
                controller.confirm(store, service, {"preflight_id": flight["preflight_id"], "operation_id": kind, "confirm": True})
            call = isolated.get(kind)
            self.assertIsNotNone(call["receipt"], kind + " lost reported accounting")
            self.assertFalse(call["receipt"]["output_eligible"])
            if kind not in ("usage", "route", "overcharge"):
                self.assertEqual(call["spent"], 1050)
                self.assertEqual(call["status"], "succeeded")
            else:
                self.assertEqual(call["status"], "uncertain")
                self.assertGreaterEqual(isolated.snapshot()["reserved_micro_usd"], call["reported_charge"])
            self.assertIsNone(store.pending_with_version())

    def test_real_transport_header_failures_retain_reported_charge(self):
        import io
        from email.message import Message
        from serial_story.studio.merge import chat_transport
        repo, service, store, ledger, controller = self.make()
        for kind in ('missing', 'duplicate', 'invalid'):
            with self.subTest(kind=kind):
                isolated = ProjectMergeLedger(self.folder / ('headers-' + kind + '.db'))
                self.addCleanup(isolated.close)
                controller._ledger = isolated
                status, raw, normal_headers = baseline.RuntimeWireTests().response()
                payload = json.loads(raw)
                payload['usage']['cost'] = 2
                headers = Message()
                for name, value in normal_headers.items():
                    if name == 'x-merge-vendor' and kind == 'missing':
                        continue
                    headers[name] = '\x00invalid' if name == 'x-merge-vendor' and kind == 'invalid' else value
                if kind == 'duplicate':
                    headers['x-merge-vendor'] = 'duplicate-vendor'
                class Response(io.BytesIO):
                    pass
                response = Response(json.dumps(payload).encode())
                response.status, response.headers = status, headers
                from unittest.mock import Mock
                opener = Mock()
                opener.open.return_value = response
                controller.runtime = MergeRuntime(enabled=True, transport=chat_transport, key_supplier=lambda: 'SYNTHETIC')
                operation = 'header-' + kind
                flight = controller.preflight(store, service, {'basis': store.basis(), 'operation_id': operation})
                confirmation = {'preflight_id': flight['preflight_id'], 'operation_id': operation, 'confirm': True}
                with patch('urllib.request.build_opener', return_value=opener):
                    with self.assertRaises(StoryError):
                        controller.confirm(store, service, confirmation)
                    call = isolated.get(operation)
                    self.assertIsNotNone(call['receipt'], 'Native transport lost available accounting')
                    self.assertEqual(call['status'], 'uncertain')
                    self.assertEqual(call['reported_charge'], 2_000_050)
                    self.assertGreaterEqual(call['reserved'], call['reported_charge'])
                    self.assertFalse(call['receipt']['accounting_verified'])
                    self.assertEqual(call['receipt']['request_id'], 'synthetic-request')
                    self.assertFalse(call['receipt']['output_eligible'])
                    self.assertIsNone(store.pending_with_version())
                    with self.assertRaises(StoryError):
                        controller.confirm(store, service, confirmation)
                    self.assertEqual(opener.open.call_count, 1, 'Unverified dispatch must not repeat')

    def test_preparation_story_change_and_metadata_expiry_refuse_before_post(self):
        from serial_story.repository import SQLiteRepository
        from serial_story.studio.store import StudioStore
        repo, service, store, ledger, controller = self.make()
        flight = controller.preflight(store, service, {"basis": store.basis(), "operation_id": "prepare"})
        other = SQLiteRepository(self.folder / "story.db")
        self.addCleanup(other.connection.close)
        def prepare_key():
            StudioStore(other).save_settings(2, prompt_template="Changed during preparation")
            return "SYNTHETIC"
        controller.runtime.gateway._key_supplier = prepare_key
        with self.assertRaises(StoryError):
            controller.confirm(store, service, {"preflight_id": flight["preflight_id"], "operation_id": "prepare", "confirm": True})
        self.assertEqual(self.calls, [])
        self.assertEqual(ledger.snapshot()["reserved_micro_usd"], 0)
        controller.runtime.gateway._key_supplier = lambda: "SYNTHETIC"
        now = [10]
        controller.clock = lambda: now[0]
        flight = controller.preflight(store, service, {"basis": store.basis(), "operation_id": "expiry"})
        original = controller.gateway._transport
        def delayed(*args):
            now[0] = 1000
            return original(*args)
        controller.gateway._transport = delayed
        with self.assertRaises(StoryError):
            controller.confirm(store, service, {"preflight_id": flight["preflight_id"], "operation_id": "expiry", "confirm": True})
        self.assertEqual(self.calls, [])
        self.assertEqual(ledger.snapshot()["reserved_micro_usd"], 0)

    def test_story_write_lock_covers_paid_dispatch(self):
        repo, service, store, ledger, controller = self.make()
        attempts = []
        def post(*args):
            other = sqlite3.connect(self.folder / "story.db", timeout=0.01, isolation_level=None)
            try:
                with self.assertRaises(sqlite3.OperationalError):
                    other.execute("UPDATE studio_settings SET version=version+1")
                attempts.append("locked")
            finally: other.close()
            return baseline.RuntimeWireTests().response()
        controller.runtime.transport = post
        flight = controller.preflight(store, service, {"basis": store.basis(), "operation_id": "locked"})
        controller.confirm(store, service, {"preflight_id": flight["preflight_id"], "operation_id": "locked", "confirm": True})
        self.assertEqual(attempts, ["locked"])

    def test_caller_and_key_callback_cannot_change_frozen_wire_identity(self):
        repo, service, store, ledger, controller = self.make()
        payload = {"basis": store.basis(), "operation_id": "copy"}
        frozen = controller.freeze(store, service, payload)
        payload["basis"]["settings_version"] = 999
        self.assertEqual(frozen["payload"]["basis"]["settings_version"], 2)
        request = baseline.RuntimeWireTests().request()
        def key():
            request["model"] = "mutated/route"
            return "SYNTHETIC"
        calls = []
        runtime = MergeRuntime(enabled=True, key_supplier=key, transport=lambda *args: (calls.append(args) or baseline.RuntimeWireTests().response()))
        receipt = runtime.exchange(request)
        self.assertTrue(receipt["accounting_verified"])
        self.assertEqual(receipt["model"], json.loads(calls[0][3])["model"])

    def test_recovery_uses_original_confirmation_not_newest_preflight(self):
        repo, service, store, ledger, controller = self.make()
        now = [10]
        controller.clock = lambda: now[0]
        request = {"basis": store.basis(), "operation_id": "original"}
        first = controller.preflight(store, service, request)
        now[0] = 20
        second = controller.preflight(store, service, request)
        confirmation = {"preflight_id": first["preflight_id"], "operation_id": "original", "confirm": True}
        repo.connection.execute("CREATE TRIGGER failed_persist BEFORE INSERT ON studio_runs BEGIN SELECT RAISE(ABORT,'synthetic'); END")
        with self.assertRaises(sqlite3.Error): controller.confirm(store, service, confirmation)
        self.assertEqual(controller.recovery(store)["calls"][0]["confirmation"], confirmation)
        for index in range(51):
            ledger.reserve(f"other-{index}", f"other-{index}", 1, {"workspace": "different"})
            ledger.succeed(f"other-{index}", 0, {})
        reopened = ProjectMergeLedger(self.folder / "ledger.db")
        self.addCleanup(reopened.close)
        restarted = MergeAuthoring(enabled=True, ledger=reopened, gateway=object(), runtime=object())
        calls = restarted.recovery(store)["calls"]
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["confirmation"], confirmation)
        self.assertNotEqual(calls[0]["confirmation"]["preflight_id"], second["preflight_id"])
        repo.connection.execute("DROP TRIGGER failed_persist")
        restarted.confirm(store, service, calls[0]["confirmation"])
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(ledger.snapshot()["spent_micro_usd"], 1050)

    def test_legacy_read_only_pending_feedback_preserves_bytes(self):
        from serial_story.repository import SQLiteRepository
        from serial_story.studio.store import StudioStore
        from serial_story.studio.server import _workspace
        repo, service, store, ledger, controller = self.make()
        revision = store.save_manual("Synthetic legacy pending prose", store.basis())
        store.add_episode_feedback(revision, "this-revision", "Legacy note", 1, store.basis())
        repo.connection.execute("ALTER TABLE episode_feedback DROP COLUMN source_text_version")
        schema = repo.connection.execute("SELECT sql FROM sqlite_master ORDER BY name").fetchall()
        path = self.folder / "story.db"
        before = path.read_bytes()
        readonly = SQLiteRepository(path, read_only=True)
        try:
            view = _workspace(readonly, StudioStore(readonly, initialize=False), False, False)
            self.assertEqual(view["pending"]["feedback"][0]["source_text_version"], 1)
            self.assertEqual(view["pending"]["feedback"][0]["note"], "Legacy note")
            self.assertEqual([tuple(r) for r in schema], [tuple(r) for r in readonly.connection.execute("SELECT sql FROM sqlite_master ORDER BY name")])
        finally: readonly.connection.close()
        self.assertEqual(path.read_bytes(), before)

    def test_two_actual_stories_share_cap_reopen_and_competing_confirmations(self):
        import threading
        from serial_story.repository import SQLiteRepository
        from serial_story.service import StoryService
        from serial_story.studio.store import StudioStore
        repo, service, store, ledger, controller = self.make()
        second_path = self.folder / "story-two.db"
        other = SQLiteRepository(second_path)
        self.addCleanup(other.connection.close)
        other_service = StoryService(other)
        other_store = StudioStore(other)
        other_service.initialize("Second synthetic story")
        plan = other_store.save_plan({"beats": [{"intention": "Different synthetic intention"}]}, None)
        other_store.approve_plan(plan.id)
        other_store.save_settings(1, provider="merge", model="synthetic/concrete-v1", vendor="synthetic-vendor")
        self.metadata["vendors"][0]["pricing"]["output_per_million"] = 200
        first = controller.preflight(store, service, {"basis": store.basis(), "operation_id": "story-one"})
        second = controller.preflight(other_store, other_service, {"basis": other_store.basis(), "operation_id": "story-two"})
        entered, release = threading.Event(), threading.Event()
        posted, outcomes = [], []
        def worker(path, flight, pause):
            db = SQLiteRepository(path)
            shared = ProjectMergeLedger(self.folder / "ledger.db")
            def post(*args):
                posted.append(path.name)
                if pause:
                    entered.set()
                    if not release.wait(5): raise TimeoutError("synthetic coordination timeout")
                status, raw, headers = baseline.RuntimeWireTests().response()
                body = json.loads(raw)
                body["usage"]["cost"] = 0.4
                return status, json.dumps(body).encode(), headers
            ctl = MergeAuthoring(enabled=True, ledger=shared, gateway=controller.gateway,
                runtime=MergeRuntime(enabled=True, key_supplier=lambda: "SYNTHETIC", transport=post),
                qualification_supplier=synthetic_qualification)
            try:
                ctl.confirm(StudioStore(db), StoryService(db), {"preflight_id": flight["preflight_id"], "operation_id": flight["operation_id"], "confirm": True})
                outcomes.append("success")
            except StoryError: outcomes.append("blocked")
            finally: shared.close(); db.connection.close()
        a = threading.Thread(target=worker, args=(self.folder / "story.db", first, True))
        a.start()
        self.assertTrue(entered.wait(5))
        b = threading.Thread(target=worker, args=(second_path, second, False))
        b.start(); b.join(5)
        release.set(); a.join(5)
        self.assertFalse(a.is_alive() or b.is_alive())
        self.assertEqual(sorted(outcomes), ["blocked", "success"])
        self.assertEqual(posted, ["story.db"])
        worker(second_path, second, False)
        self.assertEqual(posted, ["story.db", "story-two.db"])
        reopened = ProjectMergeLedger(self.folder / "ledger.db")
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.snapshot()["spent_micro_usd"], 800100)
        self.assertEqual(reopened.snapshot()["remaining_micro_usd"], 199900)
        self.assertEqual([c["operation_id"] for c in controller.recovery(store)["calls"]], ["story-one"])
        self.assertEqual([c["operation_id"] for c in controller.recovery(other_store)["calls"]], ["story-two"])
        self.assertEqual(repo.accepted(), [])
        self.assertEqual(other.accepted(), [])
        with self.assertRaises(StoryError): reopened.reserve("third", "third", 200000, {})

    def test_delayed_consent_and_readable_cost_summary(self):
        import subprocess
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(["node", str(root / "tests/studio_merge_review_test.js"), str(root / "serial_story/assets/studio.js"), str(root / "serial_story/assets/studio.html")], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_model_level_reasoning_and_incomplete_qualification_refuse(self):
        repo, service, store, ledger, controller = self.make()
        payload = {"basis": store.basis(), "operation_id": "model-reasoning"}
        self.metadata["reasoning_enabled_by_default"] = True
        with self.assertRaises(StoryError): controller.preflight(store, service, payload)
        del self.metadata["reasoning_enabled_by_default"]
        controller.qualification_supplier = lambda *args: {k: v for k, v in synthetic_qualification(*args).items() if k != "input_strategy"}
        with self.assertRaises(StoryError): controller.preflight(store, service, payload)
        self.assertEqual(self.calls, [])

    def test_expiry_during_reservation_refuses_before_post(self):
        repo, service, store, ledger, controller = self.make()
        now = [10]
        controller.clock = lambda: now[0]
        flight = controller.preflight(store, service, {"basis": store.basis(), "operation_id": "final-expiry"})
        original = ledger.claim_dispatch
        def claim(operation):
            result = original(operation)
            now[0] = 1000
            return result
        ledger.claim_dispatch = claim
        with self.assertRaises(StoryError):
            controller.confirm(store, service, {"preflight_id": flight["preflight_id"], "operation_id": "final-expiry", "confirm": True})
        self.assertEqual(self.calls, [])

    def test_metadata_callback_cannot_rebind_original_action(self):
        repo, service, store, ledger, controller = self.make()
        payload = {"basis": store.basis(), "operation_id": "original-action"}
        original = controller.gateway._transport
        def metadata(*args):
            payload["operation_id"] = "mutated-action"
            return original(*args)
        controller.gateway._transport = metadata
        flight = controller.preflight(store, service, payload)
        self.assertEqual(flight["operation_id"], "original-action")
        confirmation = {"preflight_id": flight["preflight_id"], "operation_id": "original-action", "confirm": True}
        def prepare():
            confirmation["operation_id"] = "mutated-confirmation"
            return "SYNTHETIC"
        controller.runtime.gateway._key_supplier = prepare
        controller.confirm(store, service, confirmation)
        self.assertIsNotNone(ledger.get("original-action"))
        self.assertIsNone(ledger.get("mutated-confirmation"))

    def test_nested_cache_price_schedule_is_not_sanitized_away(self):
        repo, service, store, ledger, controller = self.make()
        self.metadata["vendors"][0]["caching"] = {"cache_write_1h": {"input_per_million": 900}}
        clean = controller.gateway.catalog(model=self.metadata["model"])[0]
        self.assertIn("cache_write_1h", clean["vendors"][0]["caching"])
        with self.assertRaises(StoryError):
            controller.preflight(store, service, {"basis": store.basis(), "operation_id": "nested-prices"})
        self.assertEqual(self.calls, [])
