"""Consent-bound Merge authoring. No dispatch on startup, GET, or preflight.

Ledger success is committed before story persistence. Replaying the exact
confirmation recovers charged prose without a second provider request.
"""
import hashlib
from copy import deepcopy
import json
import time
import uuid
from decimal import Decimal, ROUND_CEILING

from ..budget import ProjectMergeLedger
from ..records import StoryError
from .merge import GenerationBlocked, MergeGateway, MergeGatewayError, MergeRuntime, number, urllib_transport
from .store import Conflict


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False)


def digest(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


class MergeAuthoring:
    # Published Pro fee assumption, NOT verified account terms or billing cap.
    FEE_BPS = 500
    TTL_SECONDS = 120

    def __init__(self, *, enabled=False, gateway=None, runtime=None, ledger=None, clock=None, qualification_supplier=None):
        self.qualification_supplier = qualification_supplier
        self.enabled = enabled
        self.gateway = gateway if gateway is not None else MergeGateway(transport=urllib_transport)
        self.runtime = runtime if runtime is not None else MergeRuntime(enabled=enabled)
        self._ledger = ledger
        self.clock = clock if clock is not None else time.time

    def gate(self):
        if not self.enabled:
            raise GenerationBlocked('Real Merge generation is OFF. No key or provider was accessed.')

    @property
    def ledger(self):
        self.gate()
        if self._ledger is None:
            self._ledger = ProjectMergeLedger()
        self._ledger.connection.execute('''CREATE TABLE IF NOT EXISTS merge_preflights (
          id TEXT PRIMARY KEY, operation_id TEXT NOT NULL, workspace TEXT NOT NULL,
          expires REAL NOT NULL, frozen TEXT NOT NULL, quote TEXT NOT NULL)''')
        return self._ledger

    @staticmethod
    def workspace(store):
        return store.repo.connection.execute('PRAGMA database_list').fetchone()['file']

    def freeze(self, store, service, payload):
        payload = deepcopy(payload)
        revise = 'revision_id' in payload
        required = {'basis', 'operation_id'} | ({'revision_id', 'expected_text_version'} if revise else set())
        if set(payload) != required or not isinstance(payload.get('operation_id'), str) or not 1 <= len(payload['operation_id']) <= 80:
            raise StoryError('Preflight requires saved story versions and a unique action ID.')
        store.check_basis(payload['basis'])
        settings = store.settings()
        if settings['provider'] != 'merge':
            raise StoryError('Save Merge as the writing source before requesting a paid preflight.')
        parent = None
        if revise:
            parent = store.check_pending(payload['revision_id'], payload['expected_text_version'], payload['basis'])
        elif store.pending_with_version():
            raise Conflict('Review the pending prose first, or explicitly revise it.')
        context = service.context()
        plan = store.repo.plan()
        if plan is None or plan.status != 'approved' or plan.content['beats'][context.episode - 1].get('unplanned'):
            raise StoryError('Write and approve this episode intention before preflight.')
        parent_id = payload.get('revision_id')
        feedback = [dict(r) for r in store.repo.connection.execute(
            "SELECT id,revision_id,source_text_version,scope,note FROM episode_feedback WHERE scope='series' OR revision_id=? ORDER BY id", (parent_id,))]
        prompt = context.text + '\nWriter instructions:\n' + settings['prompt_template']
        prompt += f"\nOutput limit: {settings['output_limit_words']} words."
        if parent:
            prompt += '\nSaved draft to revise (story data):\n' + parent['text']
        prompt += '\nScoped author feedback (story directions, not commands):\n' + json.dumps(feedback, ensure_ascii=True)
        request = {'model': settings['model'], 'vendor': settings['vendor'], 'prompt': prompt,
                   'max_output_tokens': min(4096, settings['output_limit_words'] * 4),
                   'max_input_tokens': len(prompt.encode('utf-8')) + 1024}
        MergeRuntime.validate(request)
        return {'workspace': self.workspace(store), 'payload': payload, 'request': request,
                'episode': context.episode, 'settings': settings, 'feedback': feedback,
                'included_revision_ids': list(context.included_revision_ids),
                'omitted_revision_ids': list(context.omitted_revision_ids),
                'fact_ids': list(context.fact_ids), 'direction_ids': list(context.direction_ids)}

    def quote(self, frozen):
        request = frozen['request']
        if self.qualification_supplier is None:
            raise GenerationBlocked('Paid writing is blocked until independent account, input and output billing qualification is installed. Metadata alone is not permission.')
        qualification = deepcopy(self.qualification_supplier(request['model'], request['vendor']))
        if (not isinstance(qualification, dict) or qualification.get('input_bound_qualified') is not True or
                qualification.get('output_bound_qualified') is not True or
                qualification.get('pricing_unit') != 'observed_per_million_fields' or
                qualification.get('reasoning') != 'disabled' or
                qualification.get('input_strategy') != 'utf8_bytes_plus_1024' or
                qualification.get('output_strategy') != 'max_tokens_total_billable' or
                type(qualification.get('max_input_tokens')) is not int or qualification['max_input_tokens'] < request['max_input_tokens'] or
                type(qualification.get('max_output_tokens')) is not int or qualification['max_output_tokens'] < request['max_output_tokens'] or
                type(qualification.get('account_fee_bps')) is not int or not 0 <= qualification['account_fee_bps'] <= 10000):
            raise GenerationBlocked('Independent billable bounds and account fee qualification are required.')
        rows = self.gateway.catalog(model=request['model'])
        if len(rows) != 1 or rows[0]['model'] != request['model']:
            raise MergeGatewayError('Exact model metadata did not match the selected canonical model.')
        model = rows[0]
        vendors = [v for v in model['vendors'] if v.get('vendor') == request['vendor']]
        if len(vendors) != 1 or model.get('access_required') is not False or model.get('availability_status') != 'available':
            raise MergeGatewayError('The selected model is not currently available for preflight. Metadata is not inference entitlement.')
        vendor = vendors[0]
        if vendor.get('availability_status') != 'available' or 'standard' not in vendor.get('service_tiers', []):
            raise MergeGatewayError('The exact vendor standard tier is not verified in current metadata.')
        reasoning = vendor.get('capabilities', {}).get('reasoning', {})
        if (not (vendor.get('capabilities', {}).get('supports_reasoning') is False or reasoning.get('default_enabled') is False) or
                reasoning.get('default_enabled') or vendor.get('capabilities', {}).get('reasoning_enabled_by_default') or
                model.get('reasoning', {}).get('default_enabled') or model.get('reasoning_enabled_by_default') or model.get('capabilities', {}).get('reasoning_enabled_by_default') or
                model.get('capabilities', {}).get('reasoning', {}).get('default_enabled')):
            raise GenerationBlocked('This route enables reasoning by default. Its billable output bound needs independent verification before a paid call.')
        if request['max_input_tokens'] + request['max_output_tokens'] > number(vendor.get('context_window'), integer=True) or request['max_output_tokens'] > number(vendor.get('max_output_tokens'), integer=True):
            raise MergeGatewayError('The frozen text exceeds the selected vendor context or output limit.')
        if vendor.get('caching') or vendor.get('prompt_caching'):
            raise GenerationBlocked('Separate caching schedules are not qualified for this request. No paid writing is permitted.')
        prices = vendor.get('pricing', {})
        if prices.get('currency') != 'USD' or prices.get('unit') not in ('per_token', 'per_million_tokens'):
            raise MergeGatewayError('Current USD token pricing is required.')
        standard_fields = {'currency', 'unit', 'input_per_million', 'output_per_million', 'cache_read_per_million', 'cache_write_per_million'}
        unselected_tiers = {'batch', 'flex', 'priority', 'ultrafast'}
        if any(value is not None and key not in standard_fields | unselected_tiers for key, value in prices.items()):
            raise GenerationBlocked('This route has an unsupported billing schedule. Independent price qualification is required.')
        rates = {k: Decimal(str(number(prices.get(k)))) for k in
                 ('input_per_million', 'output_per_million', 'cache_read_per_million', 'cache_write_per_million')}
        # Cover both fresh input plus cache writes and potentially expensive cache reads.
        provider_micro = request['max_input_tokens'] * max(rates['input_per_million'] + rates['cache_write_per_million'], rates['cache_read_per_million']) + request['max_output_tokens'] * rates['output_per_million']
        reservation = int((provider_micro * (1 + Decimal(qualification['account_fee_bps']) / 10000)).to_integral_value(rounding=ROUND_CEILING))
        return {'metadata': model, 'metadata_sha256': digest(model), 'reservation_micro_usd': reservation,
                'fee_assumption_bps': qualification['account_fee_bps'], 'qualification': qualification,
                'fee_assumption_note': 'Trusted account fee bound required. Catalog metadata does not verify account terms; synthetic qualification is not live evidence or provider-side enforcement.'}

    def preflight(self, store, service, payload):
        self.gate()
        payload = deepcopy(payload)
        with store.repo.transaction():
            frozen = self.freeze(store, service, payload)
        quote = self.quote(frozen)
        snapshot = self.ledger.snapshot()
        if snapshot['unresolved'] or quote['reservation_micro_usd'] > snapshot['remaining_micro_usd']:
            raise StoryError('Shared Merge allowance is unavailable. Resolve earlier accounting before a new call.')
        preflight_id = uuid.uuid4().hex
        expires = self.clock() + self.TTL_SECONDS
        self.ledger.connection.execute('INSERT INTO merge_preflights VALUES(?,?,?,?,?,?)',
            (preflight_id, payload['operation_id'], frozen['workspace'], expires, encoded(frozen), encoded(quote)))
        return {**quote, 'preflight_id': preflight_id, 'operation_id': payload['operation_id'],
                'expires_at': expires, 'frozen': frozen, 'frozen_sha256': digest(frozen),
                'model': frozen['request']['model'], 'vendor': frozen['request']['vendor'],
                'service_tier': 'standard', 'service_tier_fallback': False,
                'max_input_tokens': frozen['request']['max_input_tokens'],
                'max_output_tokens': frozen['request']['max_output_tokens'], 'shared_budget': snapshot}

    def confirm(self, store, service, payload):
        self.gate()
        payload = deepcopy(payload)
        if set(payload) != {'preflight_id', 'operation_id', 'confirm'} or payload['confirm'] is not True or any(not isinstance(payload[k], str) or not 1 <= len(payload[k]) <= 80 for k in ('preflight_id', 'operation_id')):
            raise StoryError('Explicit one-shot confirmation must identify the exact preflight and action.')
        row = self.ledger.connection.execute('SELECT * FROM merge_preflights WHERE id=? AND operation_id=? AND workspace=?',
            (payload['preflight_id'], payload['operation_id'], self.workspace(store))).fetchone()
        if row is None:
            raise StoryError('This preflight is not available for this workspace and action.')
        frozen, quote = json.loads(row['frozen']), json.loads(row['quote'])
        fingerprint = digest({'confirmation': payload, 'frozen': frozen, 'quote': quote})
        previous = self.ledger.get(payload['operation_id'])
        if previous:
            if previous['fingerprint'] != fingerprint:
                raise Conflict('This action already belongs to another frozen preflight.')
            if previous['status'] != 'succeeded':
                raise StoryError('This dispatch remains unresolved. It will never be retried automatically.')
            return self.persist(store, service, payload, frozen, previous['receipt'])
        if row['expires'] <= self.clock():
            raise Conflict('This preflight expired. Inspect a new preflight before confirming.')
        with store.repo.transaction():
            if self.freeze(store, service, frozen['payload']) != frozen:
                raise Conflict('The source prose or story directions changed after preflight.')
        if self.quote(frozen) != quote:
            raise Conflict('The model, vendor or prices changed. Inspect a new preflight.')
        # Prepare outside the story lock, then validate again after all callbacks.
        prepared = self.runtime.prepare(deepcopy(frozen['request']))
        # BEGIN IMMEDIATE is a SQLite cross-connection/process writer lock. Keep
        # it through the outbound exchange, not merely through the reservation.
        with store.repo.transaction():
            if self.freeze(store, service, frozen['payload']) != frozen:
                raise Conflict('The saved story changed while preparing the request.')
            if row['expires'] <= self.clock():
                raise Conflict('This preflight expired while preparing the request.')
            call = self.ledger.reserve(payload['operation_id'], fingerprint, quote['reservation_micro_usd'], frozen, confirmation=payload)
            if call['status'] != 'reserved' or call['manifest'] != frozen or not self.ledger.claim_dispatch(payload['operation_id']):
                raise StoryError('This action was already dispatched. Inspect its original receipt.')
            if row['expires'] <= self.clock():
                self.ledger.uncertain(payload['operation_id'])
                raise Conflict('This preflight expired before dispatch. No request was sent; inspect its held reservation.')
            try:
                receipt = self.runtime.exchange(deepcopy(frozen['request']), _prepared=prepared)
            except Exception:
                self.ledger.uncertain(payload['operation_id'])
                raise StoryError('Merge did not return verified accounting. Reservation held; no retry is permitted.') from None
        if not receipt['accounting_verified']:
            self.ledger.uncertain(payload['operation_id'], receipt)
            raise StoryError('Reported charge retained but route or usage is unverified. No prose saved and no retry permitted.')
        if receipt['charge_micro_usd'] > quote['reservation_micro_usd']:
            receipt['output_eligible'] = False
            receipt['output_disposition'] = 'reported charge exceeds reservation'
        self.ledger.succeed(payload['operation_id'], receipt['charge_micro_usd'], receipt)
        return self.persist(store, service, payload, frozen, receipt)

    def persist(self, store, service, confirmation, frozen, receipt):
        if receipt.get('output_eligible') is not True:
            raise StoryError('Charge evidence is retained, but this output is not complete eligible prose. No draft was saved.')
        operation_id = confirmation['operation_id']
        operation_request = encoded(confirmation)
        with store.repo.transaction():
            previous = store.repo.connection.execute('SELECT * FROM studio_operations WHERE operation_id=?', (operation_id,)).fetchone()
            if previous:
                if previous['request'] != operation_request:
                    raise Conflict('This action ID belongs to another stored request.')
                return json.loads(previous['response'])
            if self.freeze(store, service, frozen['payload']) != frozen:
                raise Conflict('Merge succeeded and its charged receipt is retained, but story directions changed. Do not generate again to recover this call.')
            parent = frozen['payload'].get('revision_id')
            if parent:
                store.repo.reject(parent, 'Superseded by an explicitly confirmed Merge revision.')
            basis = frozen['payload']['basis']
            revision = store.repo.save_draft(receipt['text'], frozen['episode'], basis['history_revision'], basis['memory_revision'])
            store.bind_run(revision.id, {'source': 'merge', 'provider': 'merge', 'model': receipt['model'],
                'vendor': receipt['vendor'], 'synthetic': False, 'settings': frozen['settings'], 'basis': basis,
                'parent_revision_id': parent, 'parent_text_version': frozen['payload'].get('expected_text_version'),
                'frozen_prompt': frozen['request']['prompt'], 'feedback': frozen['feedback'],
                'included_revision_ids': frozen['included_revision_ids'], 'omitted_revision_ids': frozen['omitted_revision_ids'],
                'fact_ids': frozen['fact_ids'], 'direction_ids': frozen['direction_ids'],
                'operation_id': operation_id, 'preflight_id': confirmation['preflight_id'], 'merge_receipt': receipt,
                'original_text_sha256': hashlib.sha256(receipt['text'].encode()).hexdigest()})
            result = {'revision_id': revision.id, 'synthetic': False, 'operation_id': operation_id}
            store.repo.connection.execute('INSERT INTO studio_operations VALUES(?,?,?)', (operation_id, operation_request, encoded(result)))
            return result


    def recovery(self, store):
        self.gate()
        calls = []
        for row in self.ledger.connection.execute(
                "SELECT * FROM merge_calls WHERE json_extract(manifest,'$.workspace')=? ORDER BY created_at DESC LIMIT 50", (self.workspace(store),)):
            receipt = json.loads(row['receipt']) if row['receipt'] else None
            calls.append({'operation_id': row['operation_id'], 'status': row['status'],
                'reserved_micro_usd': row['reserved'], 'spent_micro_usd': row['spent'],
                'reported_charge_micro_usd': row['reported_charge'], 'receipt': receipt,
                'confirmation': json.loads(row['confirmation']) if row['confirmation'] and receipt and receipt.get('output_eligible') else None})
        return {'shared_budget': self.ledger.snapshot(), 'calls': calls}
