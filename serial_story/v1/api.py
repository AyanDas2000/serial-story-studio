"""HTTP command surface for the v1 desk.

Every command opens the story through `Desk` and calls one desk method; this
module only validates request shapes and shapes responses. It holds no story
rules of its own and never constructs a provider: the server injects one.
"""
from pathlib import Path
from typing import Any, Callable

from ..records import StoryError
from .desk import Desk, Refused
from .provider import GenerationProvider

CONCURRENCY_CODES = {'stale_pointer', 'overlap', 'operation_reused'}


def _text(value: Any, label: str, *, limit: int = 20000) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise StoryError(f'{label} must be non-empty text.')
    return value


def _int(value: Any, label: str) -> int:
    if type(value) is not int or value < 0:
        raise StoryError(f'{label} must be a whole number.')
    return value


def _fields(section: dict[str, Any], required: set[str], optional: set[str] = frozenset()) -> dict[str, Any]:
    if not isinstance(section, dict) or not required <= set(section) <= required | optional:
        raise StoryError('This request does not match the command. Reload the desk and retry.')
    return section


class V1Api:
    def __init__(self, path: Path, provider: GenerationProvider):
        self.path = path
        self.provider = provider

    def _open(self) -> Desk:
        return Desk.open(self.path, provider=self.provider)

    def state(self) -> dict[str, Any]:
        provider = {'kind': 'scripted' if type(self.provider).__name__ == 'ScriptedProvider' else 'injected', 'live': False}
        if not self.path.exists():
            return {'story': None, 'provider': provider}
        desk = self._open()
        try:
            return {**desk.snapshot(), 'provider': provider}
        finally:
            desk.close()

    def context(self, boundary: int) -> dict[str, Any]:
        desk = self._open()
        try:
            return desk.prepare_context(boundary=_int(boundary, 'Boundary'))
        finally:
            desk.close()

    def command(self, name: str, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        _fields(body, {'payload'}, {'expected'})
        payload, expected = body['payload'], body.get('expected', {})
        if not isinstance(payload, dict) or not isinstance(expected, dict):
            raise StoryError('This request does not match the command. Reload the desk and retry.')
        if name == 'create_story':
            _fields(payload, set())
            _fields(expected, set())
            Desk.create(self.path, provider=self.provider).close()
            return 200, {'created': True}
        desk = self._open()
        try:
            return 200, COMMANDS[name](desk, payload, expected)
        except Refused as refusal:
            status = 409 if refusal.code in CONCURRENCY_CODES else 400
            return status, {'code': refusal.code, 'message': str(refusal), 'detail': refusal.detail}
        finally:
            desk.close()


def _save_direction(desk: Desk, payload, expected):
    _fields(payload, {'layer', 'content'})
    _fields(expected, set())
    if not isinstance(payload['content'], dict):
        raise StoryError('Direction content must be an object of named fields.')
    return {'revision_id': desk.save_direction(_text(payload['layer'], 'Layer'), payload['content'])}


def _adopt(desk: Desk, payload, expected):
    _fields(payload, {'revision_id'})
    _fields(expected, {'governing'})
    governing = expected['governing']
    if governing is not None:
        _text(governing, 'Expected direction')
    return {'event_id': desk.adopt(_text(payload['revision_id'], 'Revision'), expected_governing=governing)}


def _converse(desk: Desk, payload, expected):
    _fields(payload, {'target', 'text'})
    return desk.converse(target=_text(payload['target'], 'Target'), text=_text(payload['text'], 'Message'))


def _commission_arc(desk: Desk, payload, expected):
    _fields(payload, {'slots'}, {'progression'})
    slots = payload['slots']
    if not isinstance(slots, list) or len(slots) != 2:
        raise StoryError('Choose the first and last episode slot.')
    first, last = (_int(s, 'Slot') for s in slots)
    if not 1 <= first <= last:
        raise StoryError('Choose slots in order, starting at 1.')
    progression = payload.get('progression', 'provisional_chain')
    if progression not in ('provisional_chain', 'review_each'):
        raise StoryError('Choose linked drafting or review each draft.')
    return desk.commission_arc(slots=(first, last), progression=progression)


def _resume(desk: Desk, payload, expected):
    _fields(payload, {'commission_id'})
    return desk.resume_commission(_text(payload['commission_id'], 'Commission'))


def _redraft(desk: Desk, payload, expected):
    _fields(payload, {'ordinal'})
    return {'revision_id': desk.redraft(_int(payload['ordinal'], 'Episode'))}


def _blocks(value) -> list[tuple[str | None, str]]:
    if not isinstance(value, list) or not value:
        raise StoryError('Send the episode as a list of paragraphs.')
    out = []
    for item in value:
        _fields(item, {'block_id', 'text'})
        block_id = item['block_id']
        if block_id is not None:
            _text(block_id, 'Paragraph')
        out.append((block_id, _text(item['text'], 'Paragraph text')))
    return out


def _save_revision(desk: Desk, payload, expected):
    _fields(payload, {'ordinal', 'base_revision_id', 'blocks'})
    _fields(expected, {'selection_cas'})
    return desk.save_revision(_int(payload['ordinal'], 'Episode'), base_revision_id=_text(payload['base_revision_id'], 'Revision'),
                              blocks=_blocks(payload['blocks']), expected_cas=_int(expected['selection_cas'], 'Version'))


def _request_rewrite(desk: Desk, payload, expected):
    _fields(payload, {'ordinal', 'block_id', 'intent', 'reason'})
    _fields(expected, {'block_sha256'})
    if payload['intent'] not in ('polish', 'story_change'):
        raise StoryError('Choose a polish or a story change.')
    if payload['intent'] != 'polish':
        raise StoryError('Story-change rewrites are not available in this desk yet.')
    candidate_id = desk.request_rewrite(_int(payload['ordinal'], 'Episode'), block_id=_text(payload['block_id'], 'Paragraph'),
                                        expected_sha256=_text(expected['block_sha256'], 'Paragraph version'),
                                        intent=payload['intent'], reason=_text(payload['reason'], 'Reason', limit=500))
    candidate = next(c for c in desk.snapshot(history_limit=0)['candidates'] if c['candidate_id'] == candidate_id)
    return candidate


def _apply_candidate(desk: Desk, payload, expected):
    _fields(payload, {'candidate_id'})
    _fields(expected, {'selection_cas'})
    return desk.apply_candidate(_text(payload['candidate_id'], 'Candidate'), expected_cas=_int(expected['selection_cas'], 'Version'))


def _revert(desk: Desk, payload, expected):
    _fields(payload, {'event_id'})
    return desk.revert_event(_text(payload['event_id'], 'History entry'))


def _redo(desk: Desk, payload, expected):
    _fields(payload, {'event_id'})
    return desk.redo_event(_text(payload['event_id'], 'History entry'))


def _revalidate(desk: Desk, payload, expected):
    _fields(payload, {'ordinal'})
    return {'revalidated': desk.revalidate(_int(payload['ordinal'], 'Episode'))}


def _accept_prefix(desk: Desk, payload, expected):
    _fields(payload, {'episodes'})
    _fields(expected, {'canon_seq'})
    episodes = payload['episodes']
    if not isinstance(episodes, list) or not episodes:
        raise StoryError('Choose the episodes to accept.')
    group = []
    for item in episodes:
        _fields(item, {'ordinal', 'revision_id', 'sha256'})
        group.append((_int(item['ordinal'], 'Episode'), _text(item['revision_id'], 'Revision'), _text(item['sha256'], 'Version')))
    return desk.accept_prefix(group, expected_canon_seq=_int(expected['canon_seq'], 'Accepted history'))


def _read_provisional(desk: Desk, payload, expected):
    _fields(payload, {'ordinal'})
    return {'imported': desk.read_provisional(_int(payload['ordinal'], 'Episode'))}


def _update_memory(desk: Desk, payload, expected):
    _fields(payload, set())
    return desk.update_memory()


def _interpret(desk: Desk, payload, expected):
    _fields(payload, {'claim_id', 'kind', 'world_validity', 'note'}, {'speaker', 'holder'})
    return {'claim_id': desk.interpret(_text(payload['claim_id'], 'Reading'), kind=_text(payload['kind'], 'Kind'),
                                       speaker=payload.get('speaker'), holder=payload.get('holder'),
                                       world_validity=_text(payload['world_validity'], 'Validity'), note=str(payload['note']))}


def _resolve_uncertain(desk: Desk, payload, expected):
    _fields(payload, {'job_id', 'reason'})
    desk.resolve_uncertain(_text(payload['job_id'], 'Request'), _text(payload['reason'], 'Reason', limit=500))
    return {'resolved': payload['job_id']}


COMMANDS: dict[str, Callable[[Desk, dict, dict], dict[str, Any]]] = {
    'save_direction': _save_direction,
    'adopt': _adopt,
    'converse': _converse,
    'commission_arc': _commission_arc,
    'resume_commission': _resume,
    'redraft': _redraft,
    'save_revision': _save_revision,
    'request_rewrite': _request_rewrite,
    'apply_candidate': _apply_candidate,
    'revert_event': _revert,
    'redo_event': _redo,
    'revalidate': _revalidate,
    'accept_prefix': _accept_prefix,
    'read_provisional': _read_provisional,
    'update_memory': _update_memory,
    'interpret': _interpret,
    'resolve_uncertain': _resolve_uncertain,
}
NAMES = frozenset(COMMANDS) | {'create_story'}
