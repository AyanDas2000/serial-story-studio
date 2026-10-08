"""A shelf of series. Each series is a folder with its own database; nothing is shared between series.

The shelf only lists, names and opens series. It holds no story rules: every story action still goes
through that series' own `V1Api`, which opens that series' own file.

A series has one writer, chosen when it is created and kept in its `meta.json`: `practice` (the scripted
writer, free) or `live` (real models, with its own spend limit and its own spend log in the series folder).
A shelf can only create or open live series when its launcher passed a `live` builder; every other desk,
including the trial zip, refuses them and never runs a live series on the scripted writer.
"""
import json
import re
import shutil
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, NamedTuple

from ..records import StoryError
from .api import V1Api, claim_database
from .provider import GenerationProvider

SLUG = re.compile(r'[a-z0-9][a-z0-9-]{0,47}')
MAX_SERIES = 50
TITLE_MAX = 80
SAMPLE_TITLE = 'The Court Recorder'
SAMPLE_MARKER = '.sample-offered'


class Live(NamedTuple):
    """How a launcher builds the live writer for one series: `build(series_folder, cap_usd)`."""
    build: Callable[[Path, float], GenerationProvider]
    max_cap: float = 5.0
    default_cap: float = 3.0


def clean_title(value) -> str:
    if not isinstance(value, str):
        raise StoryError('Give the series a name.')
    title = ' '.join(value.split())
    if not title:
        raise StoryError('Give the series a name.')
    if len(title) > TITLE_MAX or any(ord(c) < 32 for c in title):
        raise StoryError(f'A series name is at most {TITLE_MAX} characters, on one line.')
    return title


def _slugify(title: str) -> str:
    slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')[:40].strip('-')
    return slug or 'series'


def _write_json(path: Path, data: dict) -> None:
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=True), encoding='utf-8')
    temp.replace(path)


class Shelf:
    def __init__(self, root: Path, provider_factory: Callable[[], GenerationProvider], sample: Path | None = None,
                 live: Live | None = None):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._provider_factory = provider_factory
        self._live = live
        self._desks: dict[str, V1Api] = {}
        self._leases: dict[str, object] = {}
        self._lock = threading.Lock()
        if sample is not None:
            self._offer_sample(Path(sample))

    def _folder(self, slug: str) -> Path | None:
        if not isinstance(slug, str) or not SLUG.fullmatch(slug):
            return None
        folder = self.root / slug
        return folder if (folder / 'meta.json').is_file() else None

    def _meta(self, slug: str) -> dict:
        folder = self._folder(slug)
        if folder is None:
            raise StoryError('That series is not on this shelf.')
        try:
            meta = json.loads((folder / 'meta.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            meta = {}
        return meta if isinstance(meta, dict) else {}

    def slugs(self) -> list[str]:
        return sorted(p.parent.name for p in self.root.glob('*/meta.json') if SLUG.fullmatch(p.parent.name))

    def _offer_sample(self, sample: Path) -> None:
        marker = self.root / SAMPLE_MARKER
        if marker.exists():
            return
        if not self.slugs() and sample.is_file():
            slug = _slugify(SAMPLE_TITLE)
            folder = self.root / slug
            folder.mkdir()
            shutil.copyfile(sample, folder / 'story.db')
            _write_json(folder / 'meta.json', {'title': SAMPLE_TITLE, 'sample': True,
                                               'created': datetime.now(timezone.utc).isoformat(timespec='seconds')})
        marker.write_text('The sample was offered once. Delete this file to be offered it again.\n', encoding='utf-8')

    def capabilities(self) -> dict:
        if self._live is None:
            return {'live': False}
        return {'live': True, 'max_cap': self._live.max_cap, 'default_cap': self._live.default_cap}

    def create(self, title, writer: str = 'practice', cap_usd=None) -> str:
        title = clean_title(title)
        if writer not in ('practice', 'live'):
            raise StoryError('Choose a practice writer or a live writer.')
        meta_extra: dict = {'writer': 'practice'}
        if writer == 'live':
            if self._live is None:
                raise StoryError('This desk runs the practice writer only.')
            cap = self._live.default_cap if cap_usd is None else cap_usd
            if isinstance(cap, bool) or not isinstance(cap, (int, float)) or not 0 < cap <= self._live.max_cap:
                raise StoryError(f'Set a spend limit above 0 and at most ${self._live.max_cap:g}.')
            meta_extra = {'writer': 'live', 'cap_usd': round(float(cap), 2)}
        with self._lock:
            taken = set(self.slugs())
            if len(taken) >= MAX_SERIES:
                raise StoryError(f'This shelf holds at most {MAX_SERIES} series.')
            base = _slugify(title)
            slug, n = base, 2
            while slug in taken or (self.root / slug).exists():
                suffix = f'-{n}'
                slug, n = base[:48 - len(suffix)] + suffix, n + 1
            folder = self.root / slug
            folder.mkdir()
            _write_json(folder / 'meta.json', {'title': title, 'sample': False, **meta_extra,
                                               'created': datetime.now(timezone.utc).isoformat(timespec='seconds')})
        return slug

    def desk(self, slug: str) -> V1Api | None:
        folder = self._folder(slug)
        if folder is None:
            return None
        with self._lock:
            if slug not in self._desks:
                meta = self._meta(slug)
                if meta.get('writer') == 'live':
                    if self._live is None:
                        return None
                    provider = self._live.build(folder, float(meta['cap_usd']))
                else:
                    provider = self._provider_factory()
                db = folder / 'story.db'
                self._leases[slug] = claim_database(db, provider)
                self._desks[slug] = V1Api(db, provider)
            return self._desks[slug]

    def close(self) -> None:
        with self._lock:
            for lease in self._leases.values():
                if lease is not None:
                    lease.close()
            self._leases.clear()
            self._desks.clear()

    def title(self, slug: str) -> str:
        return str(self._meta(slug).get('title') or slug)

    def summary(self, slug: str) -> dict:
        meta = self._meta(slug)
        live = meta.get('writer') == 'live'
        desk = self.desk(slug)
        try:
            state = desk.state() if desk is not None else {'story': None}
        except (StoryError, OSError, sqlite3.Error):
            state = {'story': None}
        money = state.get('provider') or {}
        governing = state.get('governing') or {}
        arc = (governing.get('arc') or {}).get('content') or {}
        skeleton = (governing.get('skeleton') or {}).get('content') or {}
        files = [p for p in (self._folder(slug) or self.root).glob('story.db*') if p.is_file()]
        touched = max((p.stat().st_mtime for p in files), default=0)
        premise = str(skeleton.get('premise') or '')
        return {
            'slug': slug,
            'title': str(meta.get('title') or slug),
            'sample': bool(meta.get('sample')),
            'writer': 'live' if live else 'practice',
            'available': desk is not None,
            'cap_usd': money.get('cap_usd') if live else None,
            'spent_usd': money.get('spent_usd') if live else None,
            'started': state.get('story') is not None,
            'planned': len(arc.get('intentions') or []),
            'approved': len(state.get('canon') or []),
            'facts': len((state.get('memory') or {}).get('accepted') or []),
            'premise': premise[:160],
            'touched': datetime.fromtimestamp(touched, timezone.utc).isoformat(timespec='seconds') if touched else '',
        }

    def listing(self) -> list[dict]:
        rows = [self.summary(slug) for slug in self.slugs()]
        return sorted(rows, key=lambda r: r['touched'], reverse=True)
