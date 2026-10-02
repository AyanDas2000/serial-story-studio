"""Generation provider boundary for the v1 desk.

The desk only calls `GenerationProvider.generate`. `ScriptedProvider` is a
deterministic offline stand-in: no network, no credentials, no charges. A live
route would implement the same protocol and be injected into `Desk`.
"""
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol


@dataclass(frozen=True)
class GenerationRequest:
    recipe: str
    prompt: str
    key: str
    variant: int = 0
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GenerationResult:
    text: str
    completeness: str = 'complete'
    charge_micro_usd: int = 0


class ProviderUnavailable(Exception):
    """The exchange produced no verified outcome; the request stays unresolved."""


class GenerationProvider(Protocol):
    def generate(self, request: GenerationRequest) -> GenerationResult: ...


OPENINGS = ['The hearing room smelled of', 'Rain worked at the shutters while', 'Nobody had swept the gallery since',
            'Leena kept the recorder under', 'Darin arrived before the clerks, and', 'The ledger office closed early because']
MIDDLES = ['wet paper and lamp oil', 'the witness rehearsed her answer', 'the last tribunal recess',
           'a fold of grey wool', 'he counted the empty benches', 'someone had filed a complaint']
TURNS = ['Leena pressed play and lost the name of a street she had walked for years.',
         'The witness repeated the sentence in a voice that was not her own.',
         'Darin wrote the phrase down twice and underlined neither copy.',
         'Somewhere below, a door to the archive stood open.',
         'The record said one thing; three people remembered another.',
         'Leena could not recall what she had eaten that morning, and did not ask.',
         'The courier\'s name appeared once, in a hand nobody claimed.',
         'Darin noticed the ink on the dispatch was older than the fire.']
CLOSERS = ['She left before the bell.', 'He kept the page.', 'Nobody corrected the clerk.',
           'The recorder was warm in her pocket.', 'The archive door was locked by dusk.']
POLISH = {'kept': 'held', 'stood': 'waited', 'noticed': 'saw', 'quiet': 'still', 'older': 'earlier',
          'walked': 'crossed', 'room': 'chamber', 'wrote': 'copied', 'left': 'went out', 'warm': 'heavy'}


def _seed(*parts: object) -> bytes:
    return hashlib.sha256('\x1f'.join(map(str, parts)).encode()).digest()


class ScriptedProvider:
    """Deterministic, bounded, varied output keyed by request; records every call."""

    def __init__(self, *, fail_recipes: tuple[str, ...] = (), during_exchange: Callable[[GenerationRequest], None] | None = None):
        self.calls: list[dict[str, Any]] = []
        self.fail_recipes = set(fail_recipes)
        self.during_exchange = during_exchange

    def generate(self, request: GenerationRequest) -> GenerationResult:
        self.calls.append({'recipe': request.recipe, 'key': request.key, 'prompt': request.prompt,
                           'variant': request.variant, 'params': dict(request.params)})
        if self.during_exchange is not None:
            self.during_exchange(request)
        if request.recipe in self.fail_recipes:
            raise ProviderUnavailable(f'scripted failure for {request.recipe}')
        if request.recipe == 'sequential_draft':
            return GenerationResult(self.draft_text(request.key, request.params.get('ordinal', 1), request.variant))
        if request.recipe == 'polish_rewrite':
            return GenerationResult(self.polish(request.params['block_text'], request.variant))
        if request.recipe == 'propose_skeleton':
            return GenerationResult(f"Working proposal {_seed(request.key).hex()[:6]}: " + request.params.get('basis', ''))
        if request.recipe == 'promotion':
            return GenerationResult(json.dumps(self.claims(request.params['blocks'])))
        if request.recipe == 'converse':
            return GenerationResult('One reading: ' + TURNS[_seed(request.key)[0] % len(TURNS)])
        raise ValueError(f'unknown recipe {request.recipe}')

    def draft_text(self, key: str, ordinal: int, variant: int = 0) -> str:
        seed = _seed(key, ordinal, variant)
        paragraphs = []
        count = 4 + seed[0] % 3
        for p in range(count):
            b = seed[(p * 5) % 32:] + seed
            sentences = [f'{OPENINGS[(b[0] + p) % len(OPENINGS)]} {MIDDLES[(b[1] + p) % len(MIDDLES)]}.']
            for s in range(3 + b[2] % 3):
                sentences.append(TURNS[(b[3 + s] + p + s) % len(TURNS)])
            sentences.append(CLOSERS[(b[8] + p) % len(CLOSERS)])
            paragraphs.append(f'[E{ordinal}.{p + 1}] ' + ' '.join(sentences))
        return '\n\n'.join(paragraphs)

    @staticmethod
    def claims(blocks: list[dict[str, str]]) -> list[dict[str, Any]]:
        """Exact-span readings; one deliberately misquoted item exercises import rejection."""
        out = []
        for block in blocks:
            text = block['text']
            end = text.find('. ')
            end = len(text) if end < 0 else end + 1
            out.append({'kind': 'summary', 'subject': 'scene', 'block_id': block['block_id'], 'start': 0, 'end': end, 'quote': text[:end]})
            at = text.find('The witness repeated')
            if at >= 0:
                stop = text.find('.', at) + 1
                out.append({'kind': 'testimony', 'subject': 'witness sentence', 'speaker': 'witness', 'block_id': block['block_id'],
                            'start': at, 'end': stop, 'quote': text[at:stop]})
        if blocks:
            out.append({'kind': 'event', 'subject': 'invented', 'block_id': blocks[0]['block_id'], 'start': 0, 'end': 3, 'quote': 'not in text'})
        return out

    @staticmethod
    def polish(text: str, variant: int = 0) -> str:
        words = text.split(' ')
        changed = [POLISH.get(w, w) for w in words]
        out = ' '.join(changed)
        if out == text or variant:
            out = out.rstrip('.') + (', and the room went quiet.' if not variant else f', said once more ({variant}).')
        return out
