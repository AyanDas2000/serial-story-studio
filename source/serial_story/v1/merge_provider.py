"""Live generation for the v1 desk through the Merge gateway.

This module opens no connection: the caller injects the transport (see serial_story/live_transport.py). Nothing runs unless a caller builds a `MergeProvider` on purpose (see `run_v1_live.py`). The default
desk provider stays offline. Rules, from docs/research/raw/H-priced-test-2026-10-04.md:

* One model per role. Reasoning is switched off where the route allows it, through the flat
  `reasoning_effort` field (a nested `reasoning` object is accepted by Merge and silently ignored).
* Cache markers go on the message (`cache_control`), exactly where the desk marked a stable block.
* Before every call the worst case (input at the dearest rate plus every allowed output token) is added to
  what was already spent and what is held for calls still open; if that passes the cap the call is not sent.
  The check and the hold happen under one lock shared by every process that uses the same spend log, so two
  calls cannot both pass on the same money. A hold is released only when the call settles with a verified
  charge or is refused before running. An unverified outcome keeps its hold. Merge's own key limit is the backstop.
* Every call, sent or not, appends one line to a spend log. Reply text is never logged. The key is never logged.
* A refusal before inference raises `NotSent` (nothing billed). Anything whose outcome cannot be verified
  raises `ProviderUnavailable`, which the desk records as an unresolved request. No automatic retry.
"""
import json
import math
import os
import re
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .provider import AnswerUnusable, GenerationRequest, GenerationResult, NotSent, ProviderUnavailable

# Statuses that mean Merge refused before running any model. 5xx is not here: a 503 that arrives after a long wait
# may have run the model.
NOT_RUN = {400, 401, 402, 403, 404, 422, 429}

Transport = Callable[[dict[str, Any]], tuple[int, Any, dict[str, str], float]]


@dataclass(frozen=True)
class Route:
    model: str
    vendor: str
    max_tokens: int
    input_per_m: float
    output_per_m: float
    cache_write_per_m: float
    effort: str | None = None


# Prices read from the Merge catalog on 2026-10-04 (USD per million tokens).
SONNET = dict(model='anthropic/claude-sonnet-5-5', vendor='anthropic', input_per_m=2.0, output_per_m=10.0, cache_write_per_m=2.5)
OPUS = dict(model='anthropic/claude-opus-5-5', vendor='anthropic', input_per_m=4.0, output_per_m=20.0, cache_write_per_m=5.0)
LUNA = dict(model='openai/gpt-6-luna', vendor='openai', input_per_m=0.10, output_per_m=0.50, cache_write_per_m=0.125)
ROUTES = {
    # Drafts need headroom: Sonnet spends a few thousand tokens on reasoning before the prose
    # (6000 was hit in practice and the episode was cut off mid-sentence).
    'draft': Route(**SONNET, max_tokens=8192),
    'plan': Route(**OPUS, max_tokens=4000),
    'chat': Route(**OPUS, max_tokens=1800),
    'polish': Route(**SONNET, max_tokens=2500),
    'extract': Route(**LUNA, max_tokens=8000, effort='none'),
}


def role_for(recipe: str) -> str:
    if recipe == 'sequential_draft':
        return 'draft'
    if recipe == 'promotion':
        return 'extract'
    if recipe == 'converse':
        return 'chat'
    if recipe.startswith('propose_'):
        return 'plan'
    if recipe.endswith('_rewrite'):
        return 'polish'
    raise ValueError(f'unknown recipe {recipe}')


EXTRACTION_RULES = (
    'List the claims the passage establishes, as a JSON array. Each item has: "block_id" (the id of the block it comes from), '
    '"kind" (one of event, testimony, belief, knowledge, relationship, promise, summary), "subject" (a short label), '
    '"speaker" (required for testimony), "holder" (required for belief and knowledge), "stance" (asserts, heard, believes, '
    'doubts, knows or unknown), "world_validity" (unknown, true_in_story or false_in_story) and "quote".\n'
    'Rules:\n'
    '- "quote" must be copied character for character from the block: one sentence or clause.\n'
    '- What a character says is testimony, not an event, unless the narration itself confirms it.\n'
    '- What people say, and rumour, is never an event.\n'
    '- Add nothing the text does not establish. If a block establishes nothing, return no item for it.\n'
    '- Return only the JSON array, with no other text.'
)


def _strip_fence(text: str) -> str:
    match = re.match(r'^\s*```(?:json)?\s*(.*?)\s*```\s*$', text, re.S)
    return match.group(1) if match else text.strip()


_META_LINE = re.compile(r"^(?:hmm?|okay|ok|sure|certainly|of course|gladly|here(?:'| i)s|here you go|done|"
                        r'the (?:tightened|revised|rewritten|updated|edited)|revised version|rewritten passage)\b', re.I)


def load_env_key(path: Path, name: str = 'MERGE_GATEWAY_API_KEY') -> str:
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line.startswith(name + '='):
            return line.split('=', 1)[1].strip().strip('"').strip("'")
    raise ProviderUnavailable(f'{name} is not set in {path.name}.')


def find_key(path: Path, environ: dict, name: str = 'MERGE_GATEWAY_API_KEY') -> str:
    """The key from the environment file if there is one, else from the environment. Never returns an empty key."""
    key = ''
    if path.exists():
        try:
            key = load_env_key(path, name)
        except ProviderUnavailable:
            key = ''
    key = key or str(environ.get(name, '')).strip()
    if not key:
        raise ProviderUnavailable(f'No key found. Put {name}=your-key on one line in a file named {path.name}, '
                                  f'or set {name} in your environment.')
    return key


class MergeProvider:
    def __init__(self, *, transport: Transport, spend_log: Path, cap_usd: float, routes: dict[str, Route] | None = None,
                 clock: Callable[[], datetime] | None = None):
        if not 0 < cap_usd <= 5:
            raise ValueError('The spend cap must be above 0 and at most 5 USD.')
        self.transport, self.spend_log, self.cap_usd = transport, Path(spend_log), cap_usd
        self.routes = routes or ROUTES
        self._thread_lock = threading.Lock()
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    # ---- spend ---------------------------------------------------------
    @staticmethod
    def _rows(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]

    @property
    def _holds(self) -> Path:
        return self.spend_log.with_name(self.spend_log.name + '.holds')

    def _tally(self) -> tuple[float, float]:
        """(settled dollars, dollars held for calls that have not settled)."""
        settled, closed = 0.0, set()
        for row in self._rows(self.spend_log):
            call_id, cost, fee = row.get('call_id'), row.get('cost_usd'), row.get('merge_fee_usd')
            if call_id is None:
                settled += float(cost or 0) + float(fee or 0)
            elif isinstance(cost, (int, float)) and isinstance(fee, (int, float)) and cost >= 0 and fee >= 0:
                settled += cost + fee
                closed.add(call_id)
            elif str(row.get('outcome', '')).startswith('not_sent'):
                closed.add(call_id)
        held = sum(float(h['reserve_usd']) for h in self._rows(self._holds) if h['call_id'] not in closed)
        return settled, held

    def spent_usd(self) -> float:
        """Everything that counts against the cap: settled charges plus holds."""
        return sum(self._tally())

    def budget(self) -> dict[str, float]:
        settled, held = self._tally()
        return {'cap_usd': self.cap_usd, 'spent_usd': round(settled, 4), 'held_usd': round(held, 4),
                'left_usd': round(max(self.cap_usd - settled - held, 0), 4)}

    @contextmanager
    def _exclusive(self):
        """One writer at a time across threads and processes that share this spend log."""
        self.spend_log.parent.mkdir(parents=True, exist_ok=True)
        with self._thread_lock:
            with open(self.spend_log.with_name(self.spend_log.name + '.lock'), 'a+b') as handle:
                locked = False
                for _ in range(100):
                    try:
                        if os.name == 'nt':
                            import msvcrt
                            handle.seek(0)
                            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                        else:
                            import fcntl
                            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                        locked = True
                        break
                    except OSError:
                        time.sleep(0.05)
                if not locked:
                    raise NotSent('The spend log is busy. Nothing was sent.')
                try:
                    yield
                finally:
                    if os.name == 'nt':
                        import msvcrt
                        handle.seek(0)
                        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def recent(self, limit: int = 30) -> list[dict[str, Any]]:
        if not self.spend_log.exists():
            return []
        keep = ('at', 'recipe', 'role', 'model', 'outcome', 'seconds', 'prompt_tokens', 'cached_tokens', 'cache_write_tokens', 'completion_tokens', 'cost_usd')
        rows = [json.loads(line) for line in self.spend_log.read_text(encoding='utf-8').splitlines() if line.strip()]
        return [{k: r.get(k) for k in keep} for r in rows[-limit:]][::-1]

    def _log(self, **row: Any) -> None:
        self.spend_log.parent.mkdir(parents=True, exist_ok=True)
        row = {'at': self.clock().isoformat(timespec='seconds'), **row}
        with self.spend_log.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + '\n')

    @staticmethod
    def worst_case_usd(route: Route, messages: list[dict[str, Any]]) -> float:
        size = sum(len(str(m['content']).encode('utf-8')) for m in messages)
        tokens_in = math.ceil(size / 3) + 200
        return (tokens_in * max(route.input_per_m, route.cache_write_per_m) + route.max_tokens * route.output_per_m) / 1_000_000

    # ---- request building ----------------------------------------------
    def _messages(self, request: GenerationRequest) -> list[dict[str, Any]]:
        recipe, params = request.recipe, request.params
        if recipe == 'sequential_draft':
            messages = params.get('messages')
            if not messages:
                raise NotSent('This draft has no frozen messages; it was made by an older desk.')
            return [{'role': m['role'], 'content': m['content'], **({'cache_control': {'type': 'ephemeral'}} if m.get('cache') else {})}
                    for m in messages]
        if recipe == 'promotion':
            blocks = '\n\n'.join(f'BLOCK {b["block_id"]}\n{b["text"]}' for b in params['blocks'])
            return [{'role': 'user', 'content': EXTRACTION_RULES + '\n\nPASSAGE\n' + blocks}]
        if recipe == 'converse':
            if params.get('messages'):
                return [{'role': x['role'], 'content': x['content']} for x in params['messages']]
            return [{'role': 'system', 'content': 'You are a story editor and thinking partner. Reply in plain prose, usually under 150 words, and say when you are guessing.'},
                    {'role': 'user', 'content': request.prompt}]
        if recipe.startswith('propose_'):
            return [{'role': 'user', 'content': 'Here is the current story direction as JSON:\n' + params.get('basis', '') +
                     '\n\nWrite a stronger story spine in two to four plain sentences: where the story goes and what it is about. '
                     'Return only the spine text.'}]
        if recipe.endswith('_rewrite'):
            return [{'role': 'user', 'content': f'Instruction: {request.prompt}\n\nPassage:\n{params["block_text"]}\n\n'
                     'Rewrite only this passage to follow the instruction. Keep every name, fact and event unless the instruction '
                     'says otherwise. Your whole reply is the rewritten passage and nothing else: no introduction, no commentary, '
                     'no "here it is", no labels, no repetition of the original passage, no notes).'}]
        raise ValueError(f'unknown recipe {recipe}')

    # ---- the exchange --------------------------------------------------
    @staticmethod
    def _clean_rewrite(text: str, original: str) -> str:
        """A rewrite answer must be the passage alone. Drop preamble chatter and any echo of the original."""
        cleaned = text.strip()
        base = original.strip()
        if base and base in cleaned:
            after = cleaned.rsplit(base, 1)[1].strip()
            before = cleaned.split(base, 1)[0].strip()
            cleaned = after or before
        lines, dropped = cleaned.splitlines(), 0
        while lines and dropped < 3:
            line = lines[0].strip()
            if not line:
                lines.pop(0)
                continue
            if line.startswith(('"', "'", '“')) or not (_META_LINE.match(line) or (line.endswith(':') and len(line.split()) <= 10)):
                break
            lines.pop(0)
            dropped += 1
        cleaned = '\n'.join(lines).strip()
        if not cleaned or cleaned == base:
            raise AnswerUnusable('The rewrite came back empty or unchanged; nothing was offered to apply.')
        return cleaned

    def generate(self, request: GenerationRequest) -> GenerationResult:
        role = role_for(request.recipe)
        route = self.routes[role]
        messages = self._messages(request)
        reserve = self.worst_case_usd(route, messages)
        call_id = uuid.uuid4().hex[:16]
        with self._exclusive():
            spent = self.spent_usd()
            if spent + reserve > self.cap_usd:
                self._log(recipe=request.recipe, role=role, model=route.model, outcome='not_sent_cap', reserve_usd=round(reserve, 6),
                          spent_before_usd=round(spent, 6), cap_usd=self.cap_usd)
                raise NotSent(f'The spend cap of ${self.cap_usd:.2f} would be passed (spent or held ${spent:.4f}, this call could cost up to ${reserve:.4f}).')
            with self._holds.open('a', encoding='utf-8') as handle:
                handle.write(json.dumps({'call_id': call_id, 'reserve_usd': round(reserve, 6), 'recipe': request.recipe}) + '\n')
        payload: dict[str, Any] = {'model': route.model, 'vendor': route.vendor, 'messages': messages, 'max_tokens': route.max_tokens,
                                   'stream': False, 'include_routing_metadata': True}
        if route.effort:
            payload['reasoning_effort'] = route.effort
        try:
            status, body, headers, seconds = self.transport(payload)
        except Exception as problem:
            self._log(call_id=call_id, recipe=request.recipe, role=role, model=route.model, outcome='unverified',
                      error_code=type(problem).__name__, reserve_usd=round(reserve, 6))
            raise ProviderUnavailable('The connection failed after the request was prepared; the outcome is unverified.') from problem
        base = dict(call_id=call_id, recipe=request.recipe, role=role, model=route.model, vendor=route.vendor, http_status=status,
                    seconds=round(seconds, 1), reserve_usd=round(reserve, 6))
        if status != 200 or not isinstance(body, dict):
            code = body.get('error', {}).get('code') if isinstance(body, dict) and isinstance(body.get('error'), dict) else None
            self._log(**base, outcome='not_sent_refused' if status in NOT_RUN else 'unverified', error_code=code)
            if status in NOT_RUN:
                raise NotSent(f'Merge refused the request before running it (HTTP {status}{", " + code if code else ""}).')
            raise ProviderUnavailable(f'Merge returned HTTP {status}; the outcome is unverified.')
        usage, routing = body.get('usage') or {}, body.get('routing') if isinstance(body.get('routing'), dict) else {}
        details = usage.get('prompt_tokens_details') or {}
        cost, fee = usage.get('cost'), routing.get('merge_fee_usd')
        choice = (body.get('choices') or [{}])[0]
        message = choice.get('message') or {}
        text = message.get('content') if isinstance(message.get('content'), str) else ''
        record = dict(base, request_id=headers.get('x-request-id'), finish_reason=choice.get('finish_reason'),
                      prompt_tokens=usage.get('prompt_tokens'), completion_tokens=usage.get('completion_tokens'),
                      cached_tokens=details.get('cached_tokens'), cache_write_tokens=details.get('cache_write_tokens'),
                      cost_usd=cost, merge_fee_usd=fee, effort_requested=route.effort,
                      effort_applied=routing.get('reasoning_effort_applied'), model_used=routing.get('model_used'),
                      vendor_used=routing.get('vendor_used'))
        if not isinstance(cost, (int, float)) or not isinstance(fee, (int, float)) or cost < 0 or fee < 0:
            self._log(**record, outcome='unverified_cost')
            raise ProviderUnavailable('Merge answered but did not report the cost; the charge is unverified.')
        if routing.get('model_used') != route.model or routing.get('vendor_used') != route.vendor:
            self._log(**record, outcome='route_mismatch')
            raise ProviderUnavailable('Merge served a different model or vendor than requested; the answer was discarded.')
        if choice.get('finish_reason') != 'stop' or not text.strip() or message.get('tool_calls') or message.get('refusal'):
            self._log(**record, outcome='unusable_answer')
            raise AnswerUnusable(f'The answer was not complete (finish reason: {choice.get("finish_reason")}). It was billed and discarded; trying again is safe.')
        self._log(**record, outcome='ok')
        if request.recipe == 'promotion':
            text = _strip_fence(text)
        if request.recipe.endswith('_rewrite'):
            try:
                text = self._clean_rewrite(text, str(request.params.get('block_text', '')))
            except AnswerUnusable as problem:
                self._log(call_id=call_id, recipe=request.recipe, role=role, model=route.model, outcome='unusable_rewrite', detail=str(problem))
                raise
        return GenerationResult(text, 'complete', math.ceil((cost + fee) * 1_000_000))
