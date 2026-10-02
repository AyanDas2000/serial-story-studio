"""Merge metadata, legacy offline contract and guarded authenticated runtime.

Runtime calls require the separate consent and project ledger integration in
studio.authoring. No retry, redirects or fallback. No live inference verified.
"""
import json
from copy import deepcopy
import math
import os
from typing import Any, Callable
from urllib.parse import urlencode
from ..records import StoryError

OFFICIAL_ORIGIN = 'https://api-gateway.merge.dev'
MAX_RESPONSE = 2 * 1024 * 1024
MAX_PAGES = 20
MAX_MODELS = 5000
REDIRECT_STATUSES = (301, 302, 303, 307, 308)
Transport = Callable[[str, str, dict[str, str], bytes | None], tuple[int, bytes]]

class MergeGatewayError(StoryError):
    pass

class GenerationBlocked(MergeGatewayError):
    pass


def urllib_transport(method: str, url: str, headers: dict[str, str], body: bytes | None = None) -> tuple[int, bytes]:
    """Runtime transport permits metadata GET only, including bounded errors."""
    if method != 'GET' or not url.startswith(OFFICIAL_ORIGIN + '/v1/models?') or body is not None:
        raise GenerationBlocked('The runtime transport permits only model metadata GET requests.')
    import urllib.error
    import urllib.request
    class NoRedirects(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, http_headers, newurl):
            return None
    request = urllib.request.Request(url, method=method, headers=dict(headers))
    try:
        with urllib.request.build_opener(NoRedirects).open(request, timeout=15) as response:
            return response.status, response.read(MAX_RESPONSE + 1)
    except urllib.error.HTTPError as problem:
        return problem.code, problem.read(MAX_RESPONSE + 1)
    except (OSError, ValueError):
        raise MergeGatewayError('Merge could not be reached. No automatic retry was made.') from None


def text(value: Any, limit: int = 512) -> str:
    if not isinstance(value, str) or not value or len(value) > limit or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise MergeGatewayError('The catalog contains an invalid text field.')
    return value


def number(value: Any, *, integer: bool = False) -> int | float:
    if type(value) not in (int, float) or (integer and type(value) is not int):
        raise MergeGatewayError('The catalog contains an invalid price or limit.')
    try:
        valid = math.isfinite(value) and 0 <= value <= 10 ** 12
    except OverflowError:
        valid = False
    if not valid:
        raise MergeGatewayError('The catalog contains an invalid price or limit.')
    return value


TEXT_FIELDS = {'model', 'display_name', 'provider', 'vendor', 'id', 'name', 'availability_status',
               'availability', 'access_reason', 'unit', 'currency', 'price_unit', 'pricing_unit', 'output_style'}
BOOL_FIELDS = {'access_required', 'available', 'streaming', 'supports_streaming', 'enabled',
               'supported', 'zero_data_retention', 'reasoning_enabled_by_default', 'supports_tool_calling',
               'supports_tool_choice', 'supports_structured_outputs', 'supports_reasoning',
               'configurable', 'disable_supported', 'default_enabled'}
LIMIT_FIELDS = {'context_window', 'context_length', 'context_limit', 'max_context_tokens',
                'max_input_tokens', 'max_output_tokens', 'output_limit', 'output_token_limit'}
PRICE_FIELDS = {'input', 'output', 'cache_read', 'cache_write', 'input_price', 'output_price',
                'cache_read_price', 'cache_write_price', 'input_per_million', 'output_per_million',
                'cache_read_per_million', 'cache_write_per_million', 'input_cost', 'output_cost',
                'price', 'amount', 'input_tokens', 'output_tokens', 'cache_read_input_tokens',
                'cache_creation_input_tokens'}
NESTED_FIELDS = {'pricing', 'caching', 'capabilities', 'limits', 'context', 'reasoning', 'prompt_caching'}


def safe_fields(row: Any, depth: int = 0, section: str | None = None) -> dict[str, Any]:
    if not isinstance(row, dict) or len(row) > 100 or depth > 3:
        raise MergeGatewayError('The catalog contains invalid vendor metadata.')
    result = {}
    for key, value in row.items():
        if value is None:
            if section in ("pricing", "caching", "prompt_caching"):
                result[key] = None
            continue
        if key in TEXT_FIELDS:
            result[key] = text(value)
            if key == 'currency' and (len(value) != 3 or not value.isascii() or not value.isupper()):
                raise MergeGatewayError('The catalog contains an invalid currency.')
        elif key in BOOL_FIELDS:
            if type(value) is not bool:
                raise MergeGatewayError('The catalog contains an invalid availability flag.')
            result[key] = value
        elif key in LIMIT_FIELDS:
            result[key] = number(value, integer=True)
        elif ((section == 'capabilities' and key in ('input', 'output'))
              or (section == 'reasoning' and key in ('controls', 'effort_values'))):
            if not isinstance(value, list) or len(value) > 10:
                raise MergeGatewayError('The catalog contains invalid capability values.')
            result[key] = [text(item, 64) for item in value]
        elif key in PRICE_FIELDS:
            result[key] = safe_fields(value, depth + 1) if isinstance(value, dict) else number(value)
        elif key in NESTED_FIELDS:
            result[key] = safe_fields(value, depth + 1, key)
        elif key in ('input_modalities', 'output_modalities', 'service_tiers'):
            if not isinstance(value, list) or len(value) > 10:
                raise MergeGatewayError('The catalog contains invalid modalities.')
            result[key] = [text(item, 32) for item in value]
        elif section in ('pricing', 'caching', 'prompt_caching'):
            # Preserve the complete bounded JSON price snapshot, including unsupported schedules.
            result[key] = deepcopy(value)
        # Unknown data is inert and excluded, never instructions or executable content.
    return result


def clean_model(row: Any) -> dict[str, Any]:
    result = safe_fields(row)
    result['model'] = text(row.get('model'), 200)
    vendors = row.get('vendors', [])
    if isinstance(vendors, dict):
        vendors = [{'vendor': name, **value} for name, value in vendors.items() if isinstance(value, dict)]
    if not isinstance(vendors, list) or len(vendors) > 50:
        raise MergeGatewayError('The catalog contains invalid vendors.')
    result['vendors'] = [safe_fields(v) for v in vendors]
    return result


def decode(status: int, body: bytes) -> Any:
    if status in REDIRECT_STATUSES:
        raise MergeGatewayError('Merge redirected the request; redirects are not followed.')
    if status in (401, 403):
        raise MergeGatewayError('Merge refused access. Stop and ask the owner to check the configured credential scope.')
    if status == 429:
        raise MergeGatewayError('Merge quota was reached. Stop; no retry or fallback was made.')
    if status != 200:
        raise MergeGatewayError(f'Merge returned status {status}. No retry was made.')
    if not isinstance(body, bytes) or len(body) > MAX_RESPONSE:
        raise MergeGatewayError('Merge returned too much response data.')
    try:
        def unique_object(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError('Ambiguous JSON object')
                result[key] = value
            return result
        return json.loads(body.decode('utf-8'), object_pairs_hook=unique_object, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, UnicodeDecodeError, RecursionError):
        raise MergeGatewayError('Merge returned unreadable response data.') from None


class MergeGateway:
    def __init__(self, transport: Transport | None = None, *, key_supplier: Callable[[], str | None] | None = None):
        self._transport = transport
        self._key_supplier = key_supplier if key_supplier is not None else lambda: os.environ.get('MERGE_GATEWAY_API_KEY')

    def _headers(self) -> dict[str, str]:
        try:
            key = self._key_supplier()
        except Exception:
            raise MergeGatewayError('Merge authentication could not be resolved. Nothing was sent.') from None
        if not isinstance(key, str) or not key or any(ord(c) < 32 for c in key):
            raise MergeGatewayError('Merge is not connected. The owner must configure MERGE_GATEWAY_API_KEY before enabling the catalog at startup.')
        return {'Authorization': f'Bearer {key}', 'Accept': 'application/json'}

    def catalog(self, *, model: str | None = None) -> list[dict[str, Any]]:
        if self._transport is None:
            raise MergeGatewayError('No catalog transport is configured.')
        headers = self._headers()
        query = {'limit': 500}
        if model is not None:
            query['model'] = text(model, 200)
        result, cursors, models = [], set(), set()
        for page in range(MAX_PAGES):
            payload = decode(*self._transport('GET', OFFICIAL_ORIGIN + '/v1/models?' + urlencode(query), headers, None))
            if model is not None and isinstance(payload, dict) and 'model' in payload:
                rows, more = [payload], False
            else:
                if not isinstance(payload, dict) or not isinstance(payload.get('data'), list) or type(payload.get('has_more')) is not bool:
                    raise MergeGatewayError('Merge returned an invalid paginated catalog.')
                rows, more = payload['data'], payload['has_more']
            for row in rows:
                cleaned = clean_model(row)
                if cleaned['model'] in models:
                    raise MergeGatewayError('Merge repeated a model across catalog pages. Listing is incomplete.')
                models.add(cleaned['model'])
                result.append(cleaned)
                if len(result) > MAX_MODELS:
                    raise MergeGatewayError('The catalog exceeded the safe listing limit. Listing is incomplete.')
            if not more:
                return result
            cursor = text(payload.get('next_cursor'), 1000)
            if cursor in cursors:
                raise MergeGatewayError('Merge repeated a pagination cursor. Listing is incomplete.')
            cursors.add(cursor)
            query['cursor'] = cursor
        raise MergeGatewayError('The catalog exceeded the safe page limit. Listing is incomplete.')

    def generate(self, request: Any) -> None:
        raise GenerationBlocked('Real Merge generation is OFF. Current model/vendor pricing, context/output preflight and project-shared reserve/settle/uncertain ledger integration must be verified before adding explicit paid startup enablement.')


class MergeChatContract:
    """Planned non-streaming wire boundary, exercised only with injected transports.

    NOT connected to runtime: a caller here has no key lookup or real transport.
    Vendor routing semantics and pricing usage must be verified by the owner
    before this contract can become the runtime provider adapter.
    """
    @staticmethod
    def exchange(request: dict[str, Any], *, transport: Transport) -> dict[str, Any]:
        if not isinstance(request, dict) or set(request) != {'model', 'vendor', 'prompt', 'max_output_tokens'}:
            raise MergeGatewayError('A chat request needs exact model, vendor, prompt and output-token limit.')
        model, vendor = text(request['model'], 200), text(request['vendor'], 200)
        prompt = request['prompt']
        if not isinstance(prompt, str) or not prompt or len(prompt) > 48000 or '\x00' in prompt:
            raise MergeGatewayError('The chat prompt exceeds the request limit.')
        limit = number(request['max_output_tokens'], integer=True)
        if not 1 <= limit <= 4096:
            raise MergeGatewayError('The chat output limit must be 1 to 4096 tokens.')
        payload = {'model': model, 'vendor': vendor, 'messages': [{'role': 'user', 'content': prompt}],
                   'max_tokens': limit, 'stream': False}
        response = decode(*transport('POST', OFFICIAL_ORIGIN + '/v1/chat/completions',
                                    {'Content-Type': 'application/json', 'Accept': 'application/json'},
                                    json.dumps(payload, allow_nan=False).encode()))
        try:
            choices = response['choices']
            if not isinstance(choices, list) or len(choices) != 1:
                raise ValueError()
            content = choices[0]['message']['content']
            if not isinstance(content, str) or not content.strip() or len(content) > 200000:
                raise ValueError()
            usage = response['usage']
            safe_usage = {k: number(usage[k], integer=True) for k in ('prompt_tokens', 'completion_tokens', 'total_tokens')}
            if safe_usage['completion_tokens'] > limit or safe_usage['total_tokens'] != safe_usage['prompt_tokens'] + safe_usage['completion_tokens']:
                raise ValueError()
            return {'text': content, 'usage': safe_usage, 'model': model, 'vendor': vendor,
                    'cost': None, 'budget_settled': False}
        except (KeyError, TypeError, ValueError):
            raise MergeGatewayError('Merge returned invalid bounded chat content or usage. No settlement may be assumed.') from None


def chat_transport(method, url, headers, body):
    """One authenticated non-streaming POST. Fixed origin, no redirects/retries.

    Only three bounded routing headers leave this boundary. Authorization and
    arbitrary response headers are never retained. Body/error data is bounded.
    """
    if method != 'POST' or url != OFFICIAL_ORIGIN + '/v1/chat/completions' or not isinstance(body, bytes) or len(body) > 262144:
        raise GenerationBlocked('Invalid runtime Merge request. Nothing was sent.')
    import urllib.error
    import urllib.request
    class NoRedirects(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    request = urllib.request.Request(url, method=method, headers=headers, data=body)
    try:
        with urllib.request.build_opener(NoRedirects).open(request, timeout=30) as response:
            selected = {}
            raw = response.read(MAX_RESPONSE + 1)
            for name in ('x-merge-model', 'x-merge-vendor', 'x-request-id'):
                values = response.headers.get_all(name, [])
                if len(values) != 1:
                    continue
                try:
                    selected[name] = text(values[0], 200)
                except MergeGatewayError:
                    # Invalid routing does not erase available charge evidence.
                    # The runtime will mark accounting unverified and refuse prose.
                    continue
            return response.status, raw, selected
    except urllib.error.HTTPError as problem:
        # Do not collect error headers or echo upstream error bodies.
        return problem.code, problem.read(MAX_RESPONSE + 1), {}
    except (OSError, ValueError):
        raise MergeGatewayError('Merge could not complete the call. Usage is uncertain; no retry was made.') from None


class MergeRuntime:
    """Callable runtime adapter; consent and durable reservation belong to authoring."""
    def __init__(self, *, enabled=False, transport=None, key_supplier=None):
        self.enabled = enabled
        self.transport = transport if transport is not None else chat_transport
        self.gateway = MergeGateway(key_supplier=key_supplier)

    @staticmethod
    def validate(request):
        if not isinstance(request, dict) or set(request) != {'model', 'vendor', 'prompt', 'max_output_tokens', 'max_input_tokens'}:
            raise MergeGatewayError('Merge needs one concrete model, one vendor and bounded text.')
        model, vendor = text(request['model'], 200), text(request['vendor'], 200)
        if '/' not in model or any(c in model for c in ':@') or model.endswith(('/latest', '-latest')):
            raise MergeGatewayError('Choose a concrete canonical model, not an alias or routing policy.')
        prompt = request['prompt']
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 48000 or '\x00' in prompt:
            raise MergeGatewayError('The Merge prompt exceeds the text limit.')
        output = number(request['max_output_tokens'], integer=True)
        input_limit = number(request['max_input_tokens'], integer=True)
        if not 1 <= output <= 4096 or not 1 <= input_limit <= 200000:
            raise MergeGatewayError('The Merge token limits are outside the allowed range.')
        payload = {'model': model, 'vendor': vendor, 'messages': [{'role': 'user', 'content': prompt}],
                   'max_tokens': output, 'stream': False, 'service_tier': 'standard',
                   'service_tier_fallback': False, 'include_routing_metadata': True}
        body = json.dumps(payload, ensure_ascii=True, allow_nan=False).encode()
        if len(body) > 262144:
            raise MergeGatewayError('The encoded Merge request is too large.')
        return body

    def prepare(self, request):
        if not self.enabled:
            raise GenerationBlocked('Real Merge generation is OFF. No key or provider was accessed.')
        request = deepcopy(request)
        body = self.validate(request)
        headers = self.gateway._headers()
        headers['Content-Type'] = 'application/json'
        return body, headers

    def exchange(self, request, *, _prepared=None):
        if not self.enabled:
            raise GenerationBlocked('Real Merge generation is OFF. No key or provider was accessed.')
        request = deepcopy(request)
        body, headers = self.prepare(request) if _prepared is None else _prepared
        try:
            status, raw, routing_headers = self.transport('POST', OFFICIAL_ORIGIN + '/v1/chat/completions', headers, body)
            response = decode(status, raw)
            # Accounting evidence is extracted independently of prose eligibility.
            usage = response.get('usage', {})
            provider_cost = number(usage['cost'])
            fee = number(response['routing']['merge_fee_usd'])
            from decimal import Decimal, ROUND_CEILING
            charge = int(((Decimal(str(provider_cost)) + Decimal(str(fee))) * 1_000_000).to_integral_value(rounding=ROUND_CEILING))
            selected, safe_usage, verified = {}, {}, False
            for name in ('x-merge-model', 'x-merge-vendor', 'x-request-id'):
                try:
                    selected[name] = text(routing_headers.get(name), 200)
                except (AttributeError, MergeGatewayError):
                    continue
            try:
                safe_usage = {name: number(usage[name], integer=True) for name in ('prompt_tokens', 'completion_tokens', 'total_tokens')}
                verified = (selected.get('x-merge-model') == request['model'] and selected.get('x-merge-vendor') == request['vendor'] and
                            'x-request-id' in selected and
                            safe_usage['prompt_tokens'] <= request['max_input_tokens'] and
                            safe_usage['completion_tokens'] <= request['max_output_tokens'] and
                            safe_usage['total_tokens'] == safe_usage['prompt_tokens'] + safe_usage['completion_tokens'])
            except (KeyError, TypeError, MergeGatewayError):
                pass
            eligible, content, disposition = False, None, 'unverified accounting'
            try:
                choices = response['choices']
                if not isinstance(choices, list) or len(choices) != 1:
                    raise ValueError()
                choice = choices[0]
                message = choice['message']
                candidate = message['content']
                eligible = (verified and choice.get('finish_reason') == 'stop' and
                            not message.get('refusal') and not message.get('tool_calls') and not message.get('function_call') and
                            isinstance(candidate, str) and bool(candidate.strip()) and len(candidate) <= 200000)
                if eligible:
                    content, disposition = candidate, 'complete prose'
                else:
                    disposition = 'rejected incomplete, refused, tool or nontext output' if verified else disposition
            except (KeyError, TypeError, ValueError):
                disposition = 'rejected malformed output' if verified else disposition
            return {'text': content, 'usage': safe_usage, 'model': request['model'], 'vendor': request['vendor'],
                    'request_id': selected.get('x-request-id'), 'provider_cost_usd': provider_cost,
                    'merge_fee_usd': fee, 'charge_micro_usd': charge, 'response_headers': selected,
                    'accounting_verified': verified, 'output_eligible': eligible, 'output_disposition': disposition}
        except Exception:
            # Even an injected transport must not leak a key or upstream body.
            raise MergeGatewayError('Merge returned an unverified call or charge. Usage is uncertain; no retry was made.') from None
