"""V1 writing desk: authority, linked drafts, block rewrites, undo, acceptance, memory.

Contract: docs/v1/01-04. Opening a story never runs DDL; only `Desk.create`
(the explicit migration) does. Every provider exchange happens outside any
SQLite transaction; results are always stored and eligibility is decided after.
"""
import hashlib
import json
import re
import sqlite3
import unicodedata
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from ..records import StoryError
from .provider import AnswerUnusable, GenerationProvider, GenerationRequest, NotSent, ProviderUnavailable

SCHEMA_VERSION = 'v1_0002'

LENGTH_DDL = ('CREATE TABLE IF NOT EXISTS v1_length (version INTEGER PRIMARY KEY AUTOINCREMENT, '
              'low INTEGER NOT NULL, target INTEGER NOT NULL, high INTEGER NOT NULL)')

TITLE_DDL = ('CREATE TABLE IF NOT EXISTS v1_title (artifact_id TEXT PRIMARY KEY, '
             'title TEXT NOT NULL, revision_id TEXT NOT NULL)')

SCHEMA = """
CREATE TABLE v1_meta (id INTEGER PRIMARY KEY CHECK(id=1), schema_version TEXT NOT NULL,
  story_id TEXT NOT NULL, canon_seq INTEGER NOT NULL DEFAULT 0);
CREATE TABLE v1_artifact (artifact_id TEXT PRIMARY KEY,
  kind TEXT NOT NULL CHECK(kind IN ('skeleton','arc','episode','style')), ordinal INTEGER,
  UNIQUE(kind, ordinal));
CREATE TABLE v1_revision (revision_id TEXT PRIMARY KEY, artifact_id TEXT NOT NULL REFERENCES v1_artifact,
  parent_id TEXT REFERENCES v1_revision, seq INTEGER NOT NULL, content_sha256 TEXT NOT NULL,
  content TEXT NOT NULL, origin TEXT NOT NULL CHECK(origin IN ('human','generated','imported')),
  job_id TEXT, reason TEXT NOT NULL DEFAULT '', UNIQUE(artifact_id, seq));
CREATE TABLE v1_block (revision_id TEXT NOT NULL REFERENCES v1_revision, block_id TEXT NOT NULL,
  ordinal INTEGER NOT NULL, text TEXT NOT NULL, sha256 TEXT NOT NULL,
  PRIMARY KEY(revision_id, block_id), UNIQUE(revision_id, ordinal));
CREATE TABLE v1_selection (artifact_id TEXT PRIMARY KEY REFERENCES v1_artifact,
  revision_id TEXT NOT NULL REFERENCES v1_revision, cas INTEGER NOT NULL,
  selected_by TEXT NOT NULL CHECK(selected_by IN ('author','commission')), event_id TEXT);
CREATE TABLE v1_governing (scope_kind TEXT PRIMARY KEY, revision_id TEXT NOT NULL REFERENCES v1_revision,
  cas INTEGER NOT NULL);
CREATE TABLE v1_message (message_id TEXT PRIMARY KEY, seq INTEGER NOT NULL, target_revision_id TEXT,
  sender TEXT NOT NULL CHECK(sender IN ('author','assistant')), content TEXT NOT NULL);
CREATE TABLE v1_commission (commission_id TEXT PRIMARY KEY, skeleton_revision TEXT NOT NULL,
  arc_revision TEXT NOT NULL, first_slot INTEGER NOT NULL, last_slot INTEGER NOT NULL,
  progression TEXT NOT NULL CHECK(progression IN ('provisional_chain','review_each')),
  status TEXT NOT NULL CHECK(status IN ('running','paused','stopped','complete')), pause_reason TEXT);
CREATE TABLE v1_job (job_id TEXT PRIMARY KEY, recipe TEXT NOT NULL, commission_id TEXT,
  target_artifact_id TEXT, request_sha256 TEXT NOT NULL, prompt TEXT NOT NULL,
  frozen_selection_cas INTEGER, basis TEXT NOT NULL,
  state TEXT NOT NULL CHECK(state IN ('frozen','sent','imported','uncertain','resolved')));
CREATE TABLE v1_predecessor (job_id TEXT NOT NULL REFERENCES v1_job, position INTEGER NOT NULL,
  revision_id TEXT NOT NULL, sha256 TEXT NOT NULL, PRIMARY KEY(job_id, position));
CREATE TABLE v1_result (job_id TEXT PRIMARY KEY REFERENCES v1_job, output_revision_id TEXT NOT NULL,
  eligibility TEXT NOT NULL CHECK(eligibility IN ('selected','detached')), detached_reason TEXT);
CREATE TABLE v1_rewrite (candidate_id TEXT PRIMARY KEY, artifact_id TEXT NOT NULL, base_revision_id TEXT NOT NULL,
  block_id TEXT NOT NULL, before_sha256 TEXT NOT NULL, replacement TEXT NOT NULL,
  context TEXT NOT NULL, intent TEXT NOT NULL CHECK(intent IN ('polish','story_change')), reason TEXT NOT NULL,
  disposition TEXT NOT NULL CHECK(disposition IN ('open','applied','kept','discarded')));
CREATE TABLE v1_event (seq INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL UNIQUE,
  action TEXT NOT NULL, actor TEXT NOT NULL, artifact_id TEXT, revision_before TEXT, revision_after TEXT,
  before_images TEXT NOT NULL DEFAULT '[]', after_images TEXT NOT NULL DEFAULT '[]',
  revert_of TEXT, payload TEXT NOT NULL DEFAULT '{}');
CREATE TABLE v1_impact (impact_id TEXT PRIMARY KEY, artifact_id TEXT NOT NULL, upstream_artifact_id TEXT NOT NULL,
  upstream_revision_id TEXT NOT NULL, cause_event TEXT NOT NULL,
  state TEXT NOT NULL CHECK(state IN ('open','revalidated','repaired','superseded')));
CREATE TABLE v1_canon (ordinal INTEGER PRIMARY KEY, artifact_id TEXT NOT NULL, revision_id TEXT NOT NULL,
  sha256 TEXT NOT NULL, text TEXT NOT NULL, acceptance_id TEXT NOT NULL);
CREATE TABLE v1_acceptance (acceptance_id TEXT PRIMARY KEY, prior_seq INTEGER NOT NULL, new_seq INTEGER NOT NULL,
  revisions TEXT NOT NULL, warnings TEXT NOT NULL);
CREATE TABLE v1_outbox (task_id TEXT PRIMARY KEY, revision_id TEXT NOT NULL, sha256 TEXT NOT NULL,
  state TEXT NOT NULL CHECK(state IN ('awaiting_authority','imported','obsolete')), UNIQUE(revision_id, sha256));
CREATE TABLE v1_claim (claim_id TEXT PRIMARY KEY, kind TEXT NOT NULL, subject TEXT NOT NULL,
  speaker TEXT, holder TEXT, stance TEXT NOT NULL DEFAULT 'asserts', world_validity TEXT NOT NULL DEFAULT 'unknown',
  narrative_ordinal INTEGER NOT NULL, revision_id TEXT NOT NULL, block_id TEXT NOT NULL,
  start INTEGER NOT NULL, "end" INTEGER NOT NULL, quote TEXT NOT NULL,
  standing TEXT NOT NULL CHECK(standing IN ('accepted_derived')),
  prior_claim_id TEXT REFERENCES v1_claim, note TEXT NOT NULL DEFAULT '',
  anchor TEXT NOT NULL DEFAULT 'exact' CHECK(anchor IN ('exact','loose','ambiguous')), extraction_id TEXT);
CREATE TABLE v1_claim_preview (claim_id TEXT PRIMARY KEY, kind TEXT NOT NULL, subject TEXT NOT NULL,
  speaker TEXT, holder TEXT, stance TEXT NOT NULL, world_validity TEXT NOT NULL,
  narrative_ordinal INTEGER NOT NULL, revision_id TEXT NOT NULL, content_sha256 TEXT NOT NULL, block_id TEXT NOT NULL,
  start INTEGER NOT NULL, "end" INTEGER NOT NULL, quote TEXT NOT NULL,
  anchor TEXT NOT NULL CHECK(anchor IN ('exact','loose','ambiguous')), extraction_id TEXT NOT NULL);
CREATE TABLE v1_extraction (extraction_id TEXT PRIMARY KEY, revision_id TEXT NOT NULL, content_sha256 TEXT NOT NULL,
  mode TEXT NOT NULL CHECK(mode IN ('preview','accepted')), outcome TEXT NOT NULL CHECK(outcome IN ('read','unreadable')),
  returned INTEGER NOT NULL, anchored_exact INTEGER NOT NULL, anchored_loose INTEGER NOT NULL,
  anchored_ambiguous INTEGER NOT NULL, duplicates INTEGER NOT NULL, quarantined INTEGER NOT NULL,
  source_extraction_id TEXT);
CREATE UNIQUE INDEX v1_preview_once ON v1_extraction(revision_id, content_sha256) WHERE mode='preview' AND outcome='read';
CREATE TABLE v1_claim_quarantine (quarantine_id TEXT PRIMARY KEY, extraction_id TEXT NOT NULL REFERENCES v1_extraction,
  revision_id TEXT NOT NULL, reason TEXT NOT NULL, raw TEXT NOT NULL);
CREATE TABLE v1_secret (secret_id TEXT PRIMARY KEY, label TEXT NOT NULL, body TEXT NOT NULL,
  reveal_ordinal INTEGER CHECK(reveal_ordinal IS NULL OR reveal_ordinal >= 1),
  status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','retired')));
CREATE TABLE v1_secret_canary (secret_id TEXT NOT NULL REFERENCES v1_secret, term TEXT NOT NULL, PRIMARY KEY(secret_id, term));
CREATE TABLE v1_style_sheet (version INTEGER PRIMARY KEY AUTOINCREMENT, body TEXT NOT NULL, avoid TEXT NOT NULL DEFAULT '[]');
CREATE TABLE v1_job_style (job_id TEXT PRIMARY KEY, version INTEGER NOT NULL REFERENCES v1_style_sheet);
CREATE TABLE v1_job_messages (job_id TEXT PRIMARY KEY, messages TEXT NOT NULL);
""" + LENGTH_DDL + """;
""" + TITLE_DDL + """;
CREATE TRIGGER v1_style_sheet_immutable BEFORE UPDATE ON v1_style_sheet BEGIN SELECT RAISE(ABORT, 'style sheet versions are immutable'); END;
CREATE TRIGGER v1_style_sheet_kept BEFORE DELETE ON v1_style_sheet BEGIN SELECT RAISE(ABORT, 'style sheet versions are immutable'); END;
CREATE TABLE v1_style (style_id TEXT PRIMARY KEY, note TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('proposed','adopted','retired')), needs_reaffirm INTEGER NOT NULL DEFAULT 0);
CREATE TABLE v1_style_evidence (style_id TEXT NOT NULL REFERENCES v1_style, position INTEGER NOT NULL,
  evidence_kind TEXT NOT NULL CHECK(evidence_kind IN ('human_edit','explicit_feedback','chosen_example')),
  event_id TEXT, message_id TEXT, before_text TEXT NOT NULL, after_text TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('active','withdrawn')), PRIMARY KEY(style_id, position));
CREATE TRIGGER v1_revision_immutable BEFORE UPDATE ON v1_revision BEGIN SELECT RAISE(ABORT, 'revisions are immutable'); END;
CREATE TRIGGER v1_revision_kept BEFORE DELETE ON v1_revision BEGIN SELECT RAISE(ABORT, 'revisions are immutable'); END;
CREATE TRIGGER v1_block_immutable BEFORE UPDATE ON v1_block BEGIN SELECT RAISE(ABORT, 'blocks are immutable'); END;
CREATE TRIGGER v1_canon_immutable BEFORE UPDATE ON v1_canon BEGIN SELECT RAISE(ABORT, 'accepted text changes only through a change set'); END;
CREATE TRIGGER v1_canon_kept BEFORE DELETE ON v1_canon BEGIN SELECT RAISE(ABORT, 'accepted text changes only through a change set'); END;
CREATE TRIGGER v1_event_append_only BEFORE UPDATE ON v1_event BEGIN SELECT RAISE(ABORT, 'history is append-only'); END;
CREATE INDEX v1_predecessor_revision ON v1_predecessor(revision_id);
CREATE TRIGGER v1_claim_immutable BEFORE UPDATE ON v1_claim BEGIN SELECT RAISE(ABORT, 'claims are immutable; add a correcting claim'); END;
CREATE TRIGGER v1_claim_kept BEFORE DELETE ON v1_claim BEGIN SELECT RAISE(ABORT, 'claims are immutable; add a correcting claim'); END;
CREATE TRIGGER v1_quarantine_append_only BEFORE UPDATE ON v1_claim_quarantine BEGIN SELECT RAISE(ABORT, 'quarantine is append-only'); END;
CREATE INDEX v1_claim_scope ON v1_claim(narrative_ordinal, standing);
CREATE UNIQUE INDEX v1_claim_one_successor ON v1_claim(prior_claim_id) WHERE prior_claim_id IS NOT NULL;
"""

CLAIM_KINDS = frozenset({'event', 'testimony', 'belief', 'knowledge', 'reader_reveal', 'relationship', 'promise', 'summary'})
STANCES = frozenset({'asserts', 'heard', 'believes', 'doubts', 'knows', 'unknown'})
VALIDITIES = frozenset({'unknown', 'true_in_story', 'false_in_story'})
_FOLD = {0x2018: "'", 0x2019: "'", 0x201c: '"', 0x201d: '"', 0x2013: '-', 0x2014: '-', 0xa0: ' '}


def _fold(text: str) -> tuple[str, list[int]]:
    """Whitespace and quote-mark normal form, with the source index of every folded character."""
    out: list[str] = []
    index: list[int] = []
    in_space = False
    for i, ch in enumerate(text):
        if ch.isspace() or ch == '\u00a0':
            if not in_space:
                out.append(' ')
                index.append(i)
            in_space = True
            continue
        in_space = False
        if ch == '\u2026':
            out.extend('...')
            index.extend([i, i, i])
        else:
            out.append(_FOLD.get(ord(ch), ch))
            index.append(i)
    return ''.join(out), index


def _anchor(blocks: list[dict[str, Any]], claim: dict[str, Any]) -> tuple[str, int, int, str] | None:
    """Find where a model's quote sits in the accepted blocks. Positions come from here, never from the model."""
    quote = claim.get('quote')
    if not isinstance(quote, str) or not quote.strip():
        return None
    given, start, end = claim.get('block_id'), claim.get('start'), claim.get('end')
    for b in blocks:
        if (b['block_id'] == given and type(start) is int and type(end) is int
                and 0 <= start < end <= len(b['text']) and b['text'][start:end] == quote):
            return b['block_id'], start, end, 'exact'
    order = [b for b in blocks if b['block_id'] == given] + [b for b in blocks if b['block_id'] != given]
    for b in order:
        count = b['text'].count(quote)
        if count:
            at = b['text'].find(quote)
            return b['block_id'], at, at + len(quote), 'exact' if count == 1 else 'ambiguous'
    needle, _ = _fold(quote.strip())
    for b in order:
        folded, index = _fold(b['text'])
        count = folded.count(needle)
        if needle and count:
            at = folded.find(needle)
            return b['block_id'], index[at], index[at + len(needle) - 1] + 1, 'loose' if count == 1 else 'ambiguous'
    return None


_TAG = re.compile(r'<[^>]{0,200}>')


def _scrub(text: str) -> str:
    """Normal form for secret matching: compatibility forms, invisible characters, markup, quotes, case."""
    text = unicodedata.normalize('NFKC', text)
    text = ''.join(ch for ch in text if unicodedata.category(ch) != 'Cf')
    return _fold(_TAG.sub('', text))[0].casefold()


def _claim_problem(claim: Any) -> str | None:
    if not isinstance(claim, dict):
        return 'not_an_object'
    kind = claim.get('kind')
    if not isinstance(kind, str) or kind not in CLAIM_KINDS:
        return 'invalid_kind'
    for field in ('subject', 'speaker', 'holder', 'stance', 'world_validity', 'block_id'):
        if claim.get(field) is not None and not isinstance(claim[field], str):
            return 'invalid_field'
    if (claim.get('stance') or 'asserts') not in STANCES or (claim.get('world_validity') or 'unknown') not in VALIDITIES:
        return 'invalid_field'
    if kind == 'testimony' and not claim.get('speaker'):
        return 'testimony_needs_speaker'
    if kind in ('belief', 'knowledge') and not claim.get('holder'):
        return 'holder_required'
    return None


_CORRECTION_PROBLEMS = {
    'invalid_kind': 'That kind of statement is not one the desk knows.',
    'invalid_field': 'One of the correction fields is not valid text from the lists the desk offers.',
    'testimony_needs_speaker': 'Testimony needs a speaker.',
    'holder_required': 'A belief or knowledge needs someone who holds it.',
}


class Refused(StoryError):
    def __init__(self, code: str, message: str, **detail: Any):
        super().__init__(message)
        self.code = code
        self.detail = detail


def sha(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def split_blocks(text: str) -> list[str]:
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    return [p.strip('\n') for p in text.split('\n\n') if p.strip()]


def new_id(prefix: str) -> str:
    return f'{prefix}-{uuid.uuid4().hex[:12]}'


# Owner decision: minimum, target, maximum words. Advisory at acceptance; never a refusal there.
# The band is what the writer is told. A draft past the maximum is kept and flagged for the author; only a draft
# more than a fifth past it (WORD_HARD_MAX) is kept whole but not selected automatically.
WORD_BAND = (550, 700, 900)
WORD_HARD_MAX = WORD_BAND[2] * 6 // 5
# The author may set their own band for a series; these are the bounds on it.
LENGTH_BOUNDS = (100, 3000)


def hard_limit(high: int) -> int:
    """A draft more than a fifth past the maximum is set aside rather than used."""
    return high * 6 // 5


_NAME_STOP = frozenset("Mrs Miss Sir Lady Lord Sergeant Captain Doctor Monday Tuesday Wednesday Thursday Friday Saturday Sunday January February March April May June "
    "July August September October November December God".split())
_SEGMENT = re.compile(r'(?<=[.!?])["\u201d\u2019\']?\s+|["\u201c\u201d]|\n+')


CHAT_SYSTEM = (
    'You are a story editor and thinking partner for the author of a serial story. Talk it through with them: give your own view, '
    'point out where an idea strains against the story so far, and end with one question when that would help. '
    'Reply in plain prose, usually under 150 words, with no markdown, bullets or bold. Do not state as fact anything the context does not establish; say when you are guessing. '
    'You only suggest; the author decides what changes.')


def seen_words(text: str) -> set[str]:
    """Every word in the text, lower case, without a trailing possessive, for comparing against new names."""
    return {re.sub(r"['\u2019]s$", '', w).lower() for w in re.findall(r"[A-Za-z][A-Za-z'\u2019-]*", text)}


def proper_names(text: str) -> set[str]:
    """Capitalised words inside sentences: a plain, model-free way to spot a name the draft introduces.

    The first word of every sentence or line of dialogue is skipped, since it is capitalised anyway."""
    names: set[str] = set()
    for segment in _SEGMENT.split(text):
        for word in re.findall(r"[A-Za-z][A-Za-z'\u2019-]*", segment)[1:]:
            word = re.sub(r"['\u2019]s$", '', word)
            if len(word) >= 3 and word[0].isupper() and not word.isupper() and word not in _NAME_STOP:
                names.add(word)
    return names


def length_warning(ordinal: int, words: int, band: tuple[int, int, int] = WORD_BAND) -> dict[str, Any] | None:
    low, _, high = band
    if low <= words <= high:
        return None
    return {'ordinal': ordinal, 'words': words, 'band': list(band)}


def split_title(text: str) -> tuple[str | None, str]:
    """A draft may open with one `Title: …` line. Returns (title, prose); (None, text) when absent or malformed."""
    match = re.match(r'^Title:\s*(.+?)\s*\n+', text)
    if not match:
        return None, text
    title = match.group(1).strip().strip('"').strip()
    if not 1 <= len(title) <= 80 or '\n' in title:
        return None, text
    return title, text[match.end():]


def draft_messages(*, ordinal: int, spine: str, purpose: str, intention: str,
                   predecessors: list[tuple[int, str]], voice_notes: list[str],
                   style_sheet: dict[str, Any] | None = None, accepted: int = 0, premise: str = '',
                   band: tuple[int, int, int] = WORD_BAND) -> list[dict[str, Any]]:
    """The `sequential_draft` contract as messages, ordered so a repeated prefix can be reused.

    What stays the same from one episode to the next comes first (fixed rules, spine, arc purpose, voice notes,
    style sheet, accepted episodes). What changes comes last: unaccepted drafts, then this episode's number, job
    and the output rules. `cache` marks the end of a block that stays identical: the system block, and the last
    of the first `accepted` earlier episodes (accepted episodes never change), and the last earlier episode (a
    draft that is later rewritten only costs a cache miss, never a wrong answer). The output
    rules come last so predecessor prose, which can be thousands of characters, is never the final thing read."""
    low, target, high = band
    if predecessors:
        intro = ('Earlier episodes follow, one per message, in story order. This is canon to stay consistent with, not a '
                 'template to copy form from, and it ranks below the spine and arc. Keep its facts, names and events; '
                 'ignore its layout.')
    else:
        intro = 'None yet. This is the first episode.'
    voice = ["Apply these only where they do not conflict with anything above; they never override the spine, "
             "the arc or this episode's job."] + [f'- {note}' for note in voice_notes] if voice_notes else ['None adopted.']
    system = '\n\n'.join([
        'You write one episode at a time of a serial story. Write only the episode you are asked for, as narrative prose and nothing else.',
        f'LENGTH\nEvery episode: aim for {target} words and stay within {low} to {high}. The author reads each episode. '
        f'A draft a little over {high} words is kept and flagged for them; a draft far over is set aside and the author decides whether to use it or ask for a new one. '
        f'Running past {high} words is worse than running short.',
        'CONTINUITY AND GROUNDING\n'
        '- The earlier episodes are canon. Never contradict a name, age, number, date, place, object, relationship, injury or promise '
        'from them or from the direction. If the direction and an earlier episode disagree, follow the direction.\n'
        "- Add background only when this episode's job needs it. Keep it small. Do not settle any question the plan leaves open, "
        'and do not invent a culprit, a motive or a proof.\n'
        '- Keep track of who knows what. A character may act only on what they have seen, been told, or could plainly infer in this story. '
        'Do not let a character know something only because you do.\n'
        '- When a character relies on a document, a witness or a measurement, show where it came from in the scene. '
        'Do not claim support that no one in the story has given.\n'
        '- When you repeat a number, date, count or time from earlier, copy it exactly. Do not add new precise figures unless the episode needs them.\n'
        '- A new place, office or company name is allowed only when this episode needs it. Give it once, with a concrete detail, '
        'and use the exact earlier name whenever one exists.\n'
        '- If you are not sure of a fact, leave it vague or leave it out. Prefer a detail already in the story to a new one.',
        'PRECEDENCE\nThe spine and arc outrank the established story data and the voice notes. '
        'If sections conflict, follow this order: 1. the governing spine, 2. the arc purpose, '
        "3. this episode's job, 4. the established story data, 5. the adopted voice notes.",
        *([f"AUTHOR'S PREMISE (the people and situation the spine builds on; do not restate)\n{premise}"] if premise else []),
        f"AUTHOR'S GOVERNING SPINE (do not restate)\n{spine}",
        f'ARC PURPOSE\n{purpose}',
        'ADOPTED VOICE NOTES (lower priority than the spine and arc)\n' + '\n'.join(voice),
        *([f"AUTHOR'S STYLE SHEET (lower priority than the spine, the arc and this episode's job)\n{style_sheet['body']}"
           + (f"\nNever use: {'; '.join(style_sheet['avoid'])}" if style_sheet['avoid'] else '')] if style_sheet else []),
        'ESTABLISHED STORY DATA (reference only; do not imitate its formatting)\n' + intro,
    ])
    messages = [{'role': 'system', 'content': system, 'cache': True}]
    for position, (n, text) in enumerate(predecessors, 1):
        messages.append({'role': 'user', 'content': f'[Episode {n} begins]\n{text}\n[Episode {n} ends]', 'cache': position == len(predecessors) or position == accepted})
    messages.append({'role': 'user', 'cache': False, 'content': '\n\n'.join([
        f'Write episode {ordinal} now.',
        f"THIS EPISODE'S JOB (episode {ordinal})\n{intention}",
        '\n'.join([
            'OUTPUT RULES',
            f'- Form: continuous narrative prose for episode {ordinal} only. No headings, no markdown, no screenplay '
            'or script format, no stage directions, no speaker labels, no sound cues, no preamble, '
            'no notes or commentary. Dialogue sits inside the prose in quotation marks.',
            '- Title: begin your reply with exactly one line of the form `Title: ` followed by two to six words that name '
            'this episode (plain words, no quotes, no trailing punctuation). Then a blank line, then the episode.',
            f'- Length: aim for {target} words; stay within {low} to {high} words. '
            f'Running past {high} words is worse than running short.',
            '- Characters: Do not introduce a named character who does not already appear in the established story data '
            'or the direction above. When the established story data names a person, use that exact name. '
            'Unnamed minor figures are allowed.',
            '- Grounding: follow CONTINUITY AND GROUNDING above. Contradict nothing already established, and show where each piece of evidence comes from.',
            '- Ending: end on a turn (a decision, a discovery, a reversal), not a summary or a moral.',
            '- Return the Title line and the episode text, nothing else.',
        ])])})
    return messages


def draft_prompt(**fields: Any) -> str:
    """The same contract as one string: the stored, hashed record of what was sent."""
    return '\n\n'.join(m['content'] for m in draft_messages(**fields))


class Desk:
    def __init__(self, connection: sqlite3.Connection, provider: GenerationProvider):
        self.connection = connection
        self.provider = provider

    @staticmethod
    def _connect(path: Path) -> sqlite3.Connection:
        connection = sqlite3.connect(path, timeout=5, autocommit=sqlite3.LEGACY_TRANSACTION_CONTROL, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys=ON')
        return connection

    @classmethod
    def create(cls, path: Path, *, provider: GenerationProvider) -> 'Desk':
        """Explicit migration: the only place v1 DDL runs."""
        if path.exists():
            raise StoryError('Refusing to create a v1 story over an existing database.')
        connection = cls._connect(path)
        connection.executescript('BEGIN IMMEDIATE;' + SCHEMA + 'COMMIT;')
        connection.execute('INSERT INTO v1_meta(id,schema_version,story_id) VALUES(1,?,?)', (SCHEMA_VERSION, new_id('story')))
        return cls(connection, provider)

    @classmethod
    def open(cls, path: Path, *, provider: GenerationProvider) -> 'Desk':
        if not path.exists():
            raise StoryError('No story database at this path.')
        connection = cls._connect(path)
        if connection.execute("SELECT 1 FROM sqlite_master WHERE name='v1_meta'").fetchone() is None:
            connection.close()
            raise StoryError('This story has not been migrated to the v1 desk.')
        meta = connection.execute('SELECT schema_version FROM v1_meta WHERE id=1').fetchone()
        if meta is None or meta['schema_version'] != SCHEMA_VERSION:
            connection.close()
            raise StoryError('This story was made by an older v1 desk and cannot be opened. Start a new story.')
        connection.execute(LENGTH_DDL)  # added after the first stories were made; nothing else about them changes
        connection.execute(TITLE_DDL)  # episode titles, added later still; old stories simply have none until redrafted
        return cls(connection, provider)

    def close(self) -> None:
        self.connection.close()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        self.connection.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.connection.execute('COMMIT')
        except BaseException:
            self.connection.execute('ROLLBACK')
            raise

    def _one(self, sql: str, *args: Any) -> sqlite3.Row | None:
        return self.connection.execute(sql, args).fetchone()

    # ---- artifacts, revisions, events ---------------------------------
    def _artifact(self, kind: str, ordinal: int | None = None) -> str:
        row = self._one('SELECT artifact_id FROM v1_artifact WHERE kind=? AND ordinal IS ?', kind, ordinal)
        if row:
            return row['artifact_id']
        artifact_id = new_id('ep' if kind == 'episode' else kind[:2])
        self.connection.execute('INSERT INTO v1_artifact VALUES(?,?,?)', (artifact_id, kind, ordinal))
        return artifact_id

    def _insert_revision(self, artifact_id: str, content: str, *, origin: str, parent_id: str | None = None,
                         job_id: str | None = None, reason: str = '', blocks: list[tuple[str, str]] | None = None) -> str:
        seq = self._one('SELECT coalesce(max(seq),0)+1 FROM v1_revision WHERE artifact_id=?', artifact_id)[0]
        revision_id = new_id('rv')
        if blocks is not None:
            content = '\n\n'.join(text for _, text in blocks)
        self.connection.execute('INSERT INTO v1_revision VALUES(?,?,?,?,?,?,?,?,?)',
                                (revision_id, artifact_id, parent_id, seq, sha(content), content, origin, job_id, reason))
        kind = self._one('SELECT kind FROM v1_artifact WHERE artifact_id=?', artifact_id)['kind']
        if kind == 'episode':
            if blocks is None:
                blocks = [(new_id('b'), text) for text in split_blocks(content)]
            for ordinal, (block_id, text) in enumerate(blocks):
                self.connection.execute('INSERT INTO v1_block VALUES(?,?,?,?,?)', (revision_id, block_id, ordinal, text, sha(text)))
        return revision_id

    def _event(self, action: str, *, actor: str = 'author', artifact_id: str | None = None,
               before: str | None = None, after: str | None = None, before_images: list | None = None,
               after_images: list | None = None, revert_of: str | None = None, payload: dict | None = None) -> str:
        event_id = new_id('ev')
        self.connection.execute(
            'INSERT INTO v1_event(event_id,action,actor,artifact_id,revision_before,revision_after,before_images,after_images,revert_of,payload) VALUES(?,?,?,?,?,?,?,?,?,?)',
            (event_id, action, actor, artifact_id, before, after, json.dumps(before_images or []),
             json.dumps(after_images or []), revert_of, json.dumps(payload or {}, sort_keys=True)))
        return event_id

    def revision(self, revision_id: str) -> dict[str, Any]:
        row = self._one('SELECT * FROM v1_revision WHERE revision_id=?', revision_id)
        if row is None:
            raise Refused('not_found', 'Unknown revision.')
        blocks = [dict(r) for r in self.connection.execute(
            'SELECT block_id,ordinal,text,sha256 FROM v1_block WHERE revision_id=? ORDER BY ordinal', (revision_id,))]
        return {'revision_id': row['revision_id'], 'artifact_id': row['artifact_id'], 'parent_id': row['parent_id'],
                'text': row['content'], 'sha256': row['content_sha256'], 'origin': row['origin'],
                'blocks': blocks, 'job_id': row['job_id']}

    def artifacts(self, kind: str) -> list[dict[str, Any]]:
        return [dict(r) for r in self.connection.execute('SELECT * FROM v1_artifact WHERE kind=? ORDER BY ordinal', (kind,))]

    def history(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self.connection.execute('SELECT * FROM v1_event ORDER BY seq')]

    # ---- direction ------------------------------------------------------
    def save_direction(self, layer: str, content: dict[str, Any], *, origin: str = 'human') -> str:
        if layer not in ('skeleton', 'arc'):
            raise Refused('invalid_layer', 'Direction layers are skeleton and arc.')
        self._check_private_boxes(content)
        with self.transaction():
            artifact_id = self._artifact(layer)
            head = self._one('SELECT revision_id FROM v1_revision WHERE artifact_id=? ORDER BY seq DESC LIMIT 1', artifact_id)
            revision_id = self._insert_revision(artifact_id, json.dumps(content, sort_keys=True), origin=origin,
                                                parent_id=head['revision_id'] if head else None)
            self._event('save', artifact_id=artifact_id, after=revision_id)
        return revision_id

    @staticmethod
    def _check_private_boxes(content: dict[str, Any]) -> None:
        """The second box. `private` and `private_intentions` are the author's own notes: `draft_prompt` is only ever
        given `spine`, `purpose` and one `intentions` entry, so nothing here can reach the drafter."""
        if 'private' in content and not isinstance(content['private'], str):
            raise Refused('invalid_direction', 'Private notes must be text.')
        if 'private_intentions' in content:
            notes, plans = content['private_intentions'], content.get('intentions')
            if (not isinstance(notes, list) or not all(isinstance(n, str) for n in notes)
                    or (isinstance(plans, list) and len(notes) != len(plans))):
                raise Refused('invalid_direction', 'Give one private note (it may be empty) for each episode plan.')

    def governing(self, layer: str) -> dict[str, Any] | None:
        row = self._one('SELECT g.revision_id, g.cas, r.content FROM v1_governing g JOIN v1_revision r USING(revision_id) WHERE scope_kind=?', layer)
        return None if row is None else {'revision_id': row['revision_id'], 'cas': row['cas'], 'content': json.loads(row['content'])}

    def adopt(self, revision_id: str, *, expected_governing: str | None) -> str:
        with self.transaction():
            row = self._one('SELECT r.revision_id, a.kind, r.content FROM v1_revision r JOIN v1_artifact a USING(artifact_id) WHERE revision_id=?', revision_id)
            if row is None or row['kind'] not in ('skeleton', 'arc'):
                raise Refused('not_found', 'Adopt a saved skeleton or arc revision.')
            current = self.governing(row['kind'])
            current_id = current['revision_id'] if current else None
            if current_id != expected_governing:
                raise Refused('stale_pointer', 'The governing direction changed. Compare before adopting.', current=current_id)
            if row['kind'] == 'arc':
                approved = self._one('SELECT coalesce(max(ordinal),0) FROM v1_canon')[0]
                planned = len(json.loads(row['content'])['intentions'])
                if planned < approved:
                    raise Refused('plan_below_approved',
                                  f'{approved} episodes are already approved. The plan needs at least {approved} episodes.',
                                  approved=approved, planned=planned)
            if current is None:
                self.connection.execute('INSERT INTO v1_governing VALUES(?,?,1)', (row['kind'], revision_id))
            else:
                self.connection.execute('UPDATE v1_governing SET revision_id=?, cas=cas+1 WHERE scope_kind=?', (revision_id, row['kind']))
            if row['kind'] == 'arc':
                for ordinal, _ in enumerate(json.loads(row['content'])['intentions'], 1):
                    self._artifact('episode', ordinal)
            return self._event('adopt', artifact_id=row['kind'], before=current_id, after=revision_id)

    def _frontier(self) -> int:
        """The first episode that is not approved yet."""
        return self._one('SELECT coalesce(max(ordinal),0)+1 FROM v1_canon')[0]

    def _refuse_secret_in_message(self, text: str, ordinal: int) -> None:
        hits = self.secret_hits(text, ordinal)
        if hits:
            raise Refused('secret_in_message', 'That text names protected material '
                          f'({", ".join(h["label"] for h in hits)}). Nothing was sent.', secrets=[h['secret_id'] for h in hits])

    CHAT_EPISODE_WORDS = 6000
    CHAT_STORY_WORDS = 8000

    def chat_context(self, target: str) -> tuple[list[dict[str, str]], list[str], int]:
        """What a chat message carries besides the author's words, chosen by the scope. Public fields only.

        Returns the model messages (without the author's text), a plain-language label per part, and the
        episode number used for the secret check."""
        skeleton, arc = self.governing('skeleton'), self.governing('arc')
        parts: list[str] = []
        labels: list[str] = []
        ordinal = self._frontier()
        plan = arc['content'] if arc else {}
        # The storyline is in every chat, so the editor never talks about a different story. Before the author adopts a
        # direction, the latest saved one is used.
        direction, adopted = (skeleton['content'], True) if skeleton else (self._saved_direction('skeleton'), False)
        if direction.get('premise') or direction.get('spine'):
            parts.append('PREMISE\n' + str(direction.get('premise', '')) + '\n\nSPINE\n' + str(direction.get('spine', '')))
            labels.append('premise and spine' if adopted else 'premise and spine (saved, not adopted yet)')
        if target in ('story', 'arc') and plan:
            lines = '\n'.join(f'{n}. {text}' for n, text in enumerate(plan.get('intentions', []), 1))
            parts.append('PLAN PURPOSE\n' + str(plan.get('purpose', '')) + '\n\nEPISODES, ONE LINE EACH\n' + lines)
            labels.append('the plan, one line per episode')
        if target == 'story':
            rows = self.connection.execute('SELECT ordinal, text FROM v1_canon ORDER BY ordinal').fetchall()
            kept, total = [], 0
            for row in reversed(rows):
                words = len(row['text'].split())
                if kept and total + words > self.CHAT_STORY_WORDS:
                    break
                kept.insert(0, row)
                total += words
            if kept:
                parts.append('APPROVED EPISODES\n\n' + '\n\n'.join(f'[Episode {r["ordinal"]}]\n{r["text"]}' for r in kept))
                first, last = kept[0]['ordinal'], kept[-1]['ordinal']
                labels.append(f'approved {"episode " + str(first) if first == last else "episodes " + str(first) + " to " + str(last)} ({total} words)')
        if target.startswith('episode:') and plan:
            try:
                n = int(target.split(':', 1)[1])
            except ValueError:
                n = 0
            intentions = plan.get('intentions', [])
            if 1 <= n <= len(intentions):
                ordinal = n
                parts.append(f"THIS EPISODE'S JOB (episode {n})\n{intentions[n - 1]}")
                canon = self._one('SELECT text FROM v1_canon WHERE ordinal=?', n)
                chosen = None if canon else self.selection(n)
                body = canon['text'] if canon else (self.revision(chosen['revision_id'])['text'] if chosen else '')
                if body:
                    words = body.split()
                    shown = ' '.join(words[:self.CHAT_EPISODE_WORDS]) if len(words) > self.CHAT_EPISODE_WORDS else body
                    parts.append(f'EPISODE {n}, {"approved" if canon else "current draft"}\n{shown}')
                    labels.append(f'episode {n}, {"approved" if canon else "current draft"} ({len(words)} words)')
                else:
                    labels.append(f'episode {n} job (no draft yet)')
        messages = [{'role': 'system', 'content': CHAT_SYSTEM}]
        if parts:
            messages.append({'role': 'user', 'content': 'CONTEXT FROM THE AUTHOR (public fields only)\n\n' + '\n\n'.join(parts)})
        return messages, labels, ordinal

    def _saved_direction(self, layer: str) -> dict[str, Any]:
        row = self._one("SELECT r.content FROM v1_revision r JOIN v1_artifact a USING(artifact_id) WHERE a.kind=? ORDER BY r.seq DESC LIMIT 1", layer)
        return json.loads(row['content']) if row else {}

    CHAT_HISTORY_MESSAGES = 8

    def _chat_history(self) -> list[dict[str, str]]:
        """The last few turns of the conversation, oldest first, as alternating user and assistant messages."""
        rows = self.connection.execute('SELECT sender, content FROM v1_message ORDER BY seq DESC LIMIT ?', (self.CHAT_HISTORY_MESSAGES,)).fetchall()
        turns: list[dict[str, str]] = []
        for row in reversed(rows):
            role = 'user' if row['sender'] == 'author' else 'assistant'
            if turns and turns[-1]['role'] == role:
                turns[-1]['content'] += '\n\n' + row['content']
            else:
                turns.append({'role': role, 'content': row['content']})
        while turns and turns[0]['role'] != 'user':
            turns.pop(0)
        return turns

    def converse(self, *, target: str, text: str) -> dict[str, Any]:
        """Conversation is stored and answered; it never moves a pointer."""
        messages, labels, ordinal = self.chat_context(target)
        history = self._chat_history()
        self._refuse_secret_in_message(text + '\n' + '\n'.join(m['content'] for m in messages + history), ordinal)
        messages = messages + history + [{'role': 'user', 'content': text}]
        with self.transaction():
            seq = self._one('SELECT coalesce(max(seq),0)+1 FROM v1_message')[0]
            asked = new_id('msg')
            self.connection.execute('INSERT INTO v1_message VALUES(?,?,?,?,?)', (asked, seq, target, 'author', text))
        reply = self.provider.generate(GenerationRequest('converse', text, key=sha(target + text),
                                                         params={'messages': messages, 'context': labels})).text
        with self.transaction():
            answered = new_id('msg')
            self.connection.execute('INSERT INTO v1_message VALUES(?,?,?,?,?)', (answered, seq + 1, target, 'assistant', reply))
        return {'question': asked, 'reply': answered, 'text': reply, 'read': labels}

    def propose(self, layer: str) -> str:
        """A model proposal is saved as a working revision only."""
        current = self.governing(layer)
        basis = json.dumps(current['content'], sort_keys=True) if current else ''
        result = self.provider.generate(GenerationRequest(f'propose_{layer}', basis, key=sha(basis), params={'basis': basis}))
        content = dict(current['content']) if current else {}
        content['spine'] = result.text
        return self.save_direction(layer, content, origin='generated')

    # ---- selection and linked drafts -----------------------------------
    def _episode_artifact(self, ordinal: int) -> str:
        row = self._one("SELECT artifact_id FROM v1_artifact WHERE kind='episode' AND ordinal=?", ordinal)
        if row is None:
            raise Refused('not_found', f'No episode slot {ordinal} in the adopted arc.')
        return row['artifact_id']

    def selection(self, ordinal: int) -> dict[str, Any] | None:
        row = self._one('SELECT s.*, r.content_sha256 FROM v1_selection s JOIN v1_revision r USING(revision_id) WHERE s.artifact_id=?',
                        self._episode_artifact(ordinal))
        return None if row is None else {'artifact_id': row['artifact_id'], 'revision_id': row['revision_id'],
                                         'sha256': row['content_sha256'], 'cas': row['cas'], 'selected_by': row['selected_by']}

    def _set_selection(self, artifact_id: str, revision_id: str, *, by: str, event_id: str) -> None:
        if self._one('SELECT 1 FROM v1_selection WHERE artifact_id=?', artifact_id):
            self.connection.execute('UPDATE v1_selection SET revision_id=?, cas=cas+1, selected_by=?, event_id=? WHERE artifact_id=?',
                                    (revision_id, by, event_id, artifact_id))
        else:
            self.connection.execute('INSERT INTO v1_selection VALUES(?,?,1,?,?)', (artifact_id, revision_id, by, event_id))

    def job_for(self, revision_id: str) -> dict[str, Any]:
        row = self._one('SELECT j.* FROM v1_job j JOIN v1_result r USING(job_id) WHERE r.output_revision_id=?', revision_id)
        if row is None:
            raise Refused('not_found', 'No job produced this revision.')
        preds = [(r['revision_id'], r['sha256']) for r in self.connection.execute(
            'SELECT revision_id, sha256 FROM v1_predecessor WHERE job_id=? ORDER BY position', (row['job_id'],))]
        result = self._one('SELECT * FROM v1_result WHERE job_id=?', row['job_id'])
        return {'job_id': row['job_id'], 'predecessors': preds, 'state': row['state'],
                'eligibility': result['eligibility'], 'detached_reason': result['detached_reason']}

    def _predecessor_basis(self, ordinal: int) -> list[tuple[str, str]] | None:
        """Exact current revisions of every earlier slot: canon if accepted, else the selection."""
        basis = []
        for n in range(1, ordinal):
            canon = self._one('SELECT revision_id, sha256 FROM v1_canon WHERE ordinal=?', n)
            if canon:
                basis.append((canon['revision_id'], canon['sha256']))
                continue
            sel = self.selection(n)
            if sel is None:
                return None
            basis.append((sel['revision_id'], sel['sha256']))
        return basis

    def _blocking_reason(self, before_ordinal: int) -> tuple[str, str] | None:
        if self._one("SELECT 1 FROM v1_job WHERE state='uncertain'"):
            return 'accounting_uncertain', 'An earlier request has no verified outcome. Resolve it before continuing.'
        open_impact = self._one("SELECT a.ordinal FROM v1_impact i JOIN v1_artifact a USING(artifact_id) WHERE i.state='open' AND a.ordinal<=? ORDER BY a.ordinal LIMIT 1",
                                before_ordinal)
        if open_impact:
            return 'open_conflict', f'Episode {open_impact["ordinal"]} is flagged by an upstream change. Revalidate or repair it first.'
        return None

    def _freeze_draft(self, commission_id: str, ordinal: int) -> str | None:
        artifact_id = self._episode_artifact(ordinal)
        basis = self._predecessor_basis(ordinal)
        if basis is None:
            return None
        skeleton, arc = self.governing('skeleton'), self.governing('arc')
        if ordinal > len(arc['content']['intentions']):
            raise Refused('invalid_slots', f'The plan has {len(arc["content"]["intentions"])} episodes. Episode {ordinal} is not in it.')
        accepted = 0
        while accepted < len(basis) and self._one('SELECT 1 FROM v1_canon WHERE ordinal=?', accepted + 1):
            accepted += 1
        messages = draft_messages(
            ordinal=ordinal, spine=skeleton['content']['spine'], purpose=arc['content']['purpose'],
            premise=skeleton['content'].get('premise', ''),
            intention=arc['content']['intentions'][ordinal - 1],
            predecessors=[(n, self.revision(revision_id)['text']) for n, (revision_id, _) in enumerate(basis, 1)],
            voice_notes=[r['note'] for r in self.connection.execute("SELECT note FROM v1_style WHERE status='adopted' ORDER BY style_id")],
            style_sheet=self.style_sheet(), accepted=accepted, band=self.word_band())
        prompt = '\n\n'.join(m['content'] for m in messages)
        hits = self.secret_hits(prompt, ordinal)
        if hits:
            raise Refused('secret_in_input', 'Protected material would reach the drafter for episode '
                          f'{ordinal} ({", ".join(h["label"] for h in hits)}). Nothing was sent.',
                          secrets=[h['secret_id'] for h in hits])
        sel = self._one('SELECT cas FROM v1_selection WHERE artifact_id=?', artifact_id)
        job_id = new_id('job')
        frozen_basis = {'skeleton': skeleton['revision_id'], 'arc': arc['revision_id'], 'predecessors': basis}
        self.connection.execute('INSERT INTO v1_job VALUES(?,?,?,?,?,?,?,?,?)',
                                (job_id, 'sequential_draft', commission_id, artifact_id, sha(prompt), prompt,
                                 sel['cas'] if sel else 0, json.dumps(frozen_basis), 'frozen'))
        for position, (revision_id, digest) in enumerate(basis):
            self.connection.execute('INSERT INTO v1_predecessor VALUES(?,?,?,?)', (job_id, position, revision_id, digest))
        sheet = self.style_sheet()
        if sheet is not None:
            self.connection.execute('INSERT INTO v1_job_style VALUES(?,?)', (job_id, sheet['version']))
        self.connection.execute('INSERT INTO v1_job_messages VALUES(?,?)', (job_id, json.dumps(messages)))
        return job_id

    def job_messages(self, job_id: str) -> list[dict[str, Any]]:
        """The exact messages frozen for a draft request, with cache markers."""
        return json.loads(self._one('SELECT messages FROM v1_job_messages WHERE job_id=?', job_id)['messages'])

    def draft_inspection(self, ordinal: int) -> dict[str, Any]:
        """What the writer was shown for the latest draft request of this episode, read from the frozen messages."""
        job = self._one('SELECT job_id, state, request_sha256 FROM v1_job WHERE target_artifact_id=? ORDER BY rowid DESC LIMIT 1',
                        self._episode_artifact(ordinal))
        if job is None:
            return {'ordinal': ordinal, 'job': None, 'parts': []}
        parts = []
        for message in self.job_messages(job['job_id']):
            text = message['content']
            heading = re.match(r'\[Episode (\d+) begins\]', text)
            if message['role'] == 'system':
                parts.append({'kind': 'direction', 'label': 'Rules and direction', 'text': text, 'cached': bool(message.get('cache'))})
            elif heading:
                parts.append({'kind': 'episode', 'label': f'Episode {heading.group(1)}, in full', 'words': len(text.split()),
                              'cached': bool(message.get('cache'))})
            else:
                parts.append({'kind': 'job', 'label': "This episode's job and output rules", 'text': text, 'cached': bool(message.get('cache'))})
        return {'ordinal': ordinal, 'job': job['job_id'], 'state': job['state'], 'fingerprint': job['request_sha256'], 'parts': parts}

    def _basis_current(self, job: sqlite3.Row, ordinal: int, *, check_selection: bool = True) -> str | None:
        frozen = json.loads(job['basis'])
        if self.governing('skeleton')['revision_id'] != frozen['skeleton'] or self.governing('arc')['revision_id'] != frozen['arc']:
            return 'direction_changed'
        if [list(p) for p in (self._predecessor_basis(ordinal) or [])] != frozen['predecessors']:
            return 'predecessor_changed'
        sel = self._one('SELECT cas FROM v1_selection WHERE artifact_id=?', job['target_artifact_id'])
        if check_selection and (sel['cas'] if sel else 0) != job['frozen_selection_cas']:
            return 'selection_changed'
        return None

    def commission_arc(self, *, slots: tuple[int, int], progression: str = 'provisional_chain') -> dict[str, Any]:
        if self.governing('skeleton') is None or self.governing('arc') is None:
            raise Refused('direction_missing', 'Adopt a skeleton and an arc before drafting through the arc.')
        first, last = slots
        planned = len(self.governing('arc')['content']['intentions'])
        if last > planned:
            raise Refused('invalid_slots', f'The plan has {planned} episodes. Choose episodes from 1 to {planned}.',
                          planned=planned)
        blocked = self._blocking_reason(first)
        if blocked:
            raise Refused(*blocked)
        with self.transaction():
            for n in range(first, last + 1):
                self._episode_artifact(n)
            commission_id = new_id('cm')
            self.connection.execute('INSERT INTO v1_commission VALUES(?,?,?,?,?,?,?,NULL)',
                                    (commission_id, self.governing('skeleton')['revision_id'], self.governing('arc')['revision_id'],
                                     first, last, progression, 'running'))
            self._event('commission_start', payload={'commission_id': commission_id, 'slots': [first, last]})
        return self._run_commission(commission_id)

    def resume_commission(self, commission_id: str) -> dict[str, Any]:
        row = self._one('SELECT * FROM v1_commission WHERE commission_id=?', commission_id)
        if row is None:
            raise Refused('not_found', 'No such drafting run.')
        if row['status'] in ('complete', 'stopped'):
            raise Refused('commission_closed', 'That drafting run is finished. Start a new one to draft those episodes again.')
        blocked = self._blocking_reason(row['last_slot'])
        if blocked:
            raise Refused(*blocked)
        with self.transaction():
            self.connection.execute("UPDATE v1_commission SET status='running', pause_reason=NULL WHERE commission_id=?", (commission_id,))
            self._event('commission_resume', payload={'commission_id': commission_id})
        return self._run_commission(commission_id)

    def commission(self, commission_id: str) -> dict[str, Any]:
        return dict(self._one('SELECT * FROM v1_commission WHERE commission_id=?', commission_id))

    def _pause(self, commission_id: str, reason: str) -> None:
        self.connection.execute("UPDATE v1_commission SET status='paused', pause_reason=? WHERE commission_id=? AND status='running'", (reason, commission_id))
        self._event('commission_pause', actor=f'commission:{commission_id}', payload={'reason': reason})

    def _run_commission(self, commission_id: str) -> dict[str, Any]:
        row = self._one('SELECT * FROM v1_commission WHERE commission_id=?', commission_id)
        actor = f'commission:{commission_id}'
        for ordinal in range(row['first_slot'], row['last_slot'] + 1):
            artifact_id = self._episode_artifact(ordinal)
            held = self._one('SELECT selected_by FROM v1_selection WHERE artifact_id=?', artifact_id)
            if held is not None and held['selected_by'] == 'author':
                continue  # The author has taken this episode over; a resumed run never overwrites their words.
            done = self._one("SELECT 1 FROM v1_job j JOIN v1_result r USING(job_id) WHERE j.commission_id=? AND j.target_artifact_id=? AND r.eligibility='selected' AND r.output_revision_id=(SELECT revision_id FROM v1_selection WHERE artifact_id=?)",
                             commission_id, artifact_id, artifact_id)
            if done and self._one("SELECT 1 FROM v1_impact WHERE artifact_id=? AND state='open'", artifact_id) is None:
                # Choosing this draft moved the selection on, so only the direction and the earlier episodes decide
                # whether it is still the right answer. Asking again would replace words the author may have read.
                if self._basis_current(self._one("SELECT j.* FROM v1_job j JOIN v1_result r USING(job_id) WHERE r.output_revision_id=(SELECT revision_id FROM v1_selection WHERE artifact_id=?)", artifact_id), ordinal,
                                       check_selection=False) is None:
                    continue
            if self._one('SELECT 1 FROM v1_canon WHERE ordinal=?', ordinal):
                continue
            with self.transaction():
                blocked = self._blocking_reason(ordinal - 1)
                if blocked:
                    self._pause(commission_id, blocked[0])
                    return self.commission(commission_id)
                try:
                    job_id = self._freeze_draft(commission_id, ordinal)
                except Refused as stopped:
                    if stopped.code != 'secret_in_input':
                        raise
                    self._pause(commission_id, 'secret_in_input')
                    return self.commission(commission_id)
                if job_id is None:
                    self._pause(commission_id, 'waiting_predecessor')
                    return self.commission(commission_id)
                self._event('job_frozen', actor=actor, artifact_id=artifact_id, payload={'job_id': job_id})
                self.connection.execute("UPDATE v1_job SET state='sent' WHERE job_id=?", (job_id,))
            job = self._one('SELECT * FROM v1_job WHERE job_id=?', job_id)
            # Exchange: no transaction is open here, so other writers may proceed.
            request = GenerationRequest('sequential_draft', job['prompt'], key=job['request_sha256'],
                                       params={'ordinal': ordinal, 'messages': self.job_messages(job_id)})
            try:
                result = self.provider.generate(request)
            except NotSent:
                with self.transaction():
                    self.connection.execute("UPDATE v1_job SET state='resolved' WHERE job_id=?", (job_id,))
                    self._event('not_sent', actor=actor, artifact_id=artifact_id, payload={'job_id': job_id})
                    self._pause(commission_id, 'not_sent')
                return self.commission(commission_id)
            except AnswerUnusable as problem:
                # Billed and discarded; nothing is uncertain, so the author can simply resume.
                with self.transaction():
                    self.connection.execute("UPDATE v1_job SET state='resolved' WHERE job_id=?", (job_id,))
                    self._event('answer_unusable', actor=actor, artifact_id=artifact_id,
                                payload={'job_id': job_id, 'detail': str(problem)})
                    self._pause(commission_id, 'unusable_answer')
                return self.commission(commission_id)
            except ProviderUnavailable:
                with self.transaction():
                    self.connection.execute("UPDATE v1_job SET state='uncertain' WHERE job_id=?", (job_id,))
                    self._pause(commission_id, 'accounting_uncertain')
                return self.commission(commission_id)
            title, text = split_title(result.text)
            with self.transaction():
                output = self._insert_revision(artifact_id, text, origin='generated', job_id=job_id, reason='commission draft')
                if title:
                    self.connection.execute(
                        'INSERT INTO v1_title(artifact_id,title,revision_id) VALUES(?,?,?) '
                        'ON CONFLICT(artifact_id) DO UPDATE SET title=excluded.title, revision_id=excluded.revision_id',
                        (artifact_id, title, output))
                self.connection.execute("UPDATE v1_job SET state='imported' WHERE job_id=?", (job_id,))
                status = self._one('SELECT status FROM v1_commission WHERE commission_id=?', commission_id)['status']
                approved_meanwhile = 'target_accepted' if self._one('SELECT 1 FROM v1_canon WHERE ordinal=?', ordinal) else None
                changed = approved_meanwhile or self._basis_current(job, ordinal) or (None if status == 'running' else 'commission_' + status)
                over_length = len(text.split()) > hard_limit(self.word_band()[2])
                incomplete = result.completeness != 'complete'
                if changed is None and not over_length and not incomplete and row['progression'] == 'provisional_chain':
                    prior = self._one('SELECT revision_id FROM v1_selection WHERE artifact_id=?', artifact_id)
                    event_id = self._event('select', actor=actor, artifact_id=artifact_id,
                                           before=prior['revision_id'] if prior else None, after=output)
                    self._set_selection(artifact_id, output, by='commission', event_id=event_id)
                    self.connection.execute('INSERT INTO v1_result VALUES(?,?,?,NULL)', (job_id, output, 'selected'))
                    self.connection.execute("UPDATE v1_impact SET state='superseded' WHERE artifact_id=? AND state='open'", (artifact_id,))
                else:
                    reason = changed or ('incomplete' if incomplete else 'over_length' if over_length else 'review_each')
                    self.connection.execute('INSERT INTO v1_result VALUES(?,?,?,?)', (job_id, output, 'detached', reason))
                    self._event('result_detached', actor=actor, artifact_id=artifact_id, after=output, payload={'reason': reason})
                    if changed:
                        self._pause(commission_id, 'target_accepted' if approved_meanwhile else 'basis_changed')
                    elif incomplete:
                        self._pause(commission_id, 'incomplete')
                    elif over_length:
                        self._pause(commission_id, 'over_length')
                    return self.commission(commission_id)
        with self.transaction():
            self.connection.execute("UPDATE v1_commission SET status='complete' WHERE commission_id=?", (commission_id,))
        return self.commission(commission_id)

    def resolve_uncertain(self, job_id: str, reason: str) -> None:
        with self.transaction():
            changed = self.connection.execute("UPDATE v1_job SET state='resolved' WHERE job_id=? AND state='uncertain'", (job_id,))
            if changed.rowcount != 1:
                raise Refused('not_found', 'Only an unresolved request can be resolved.')
            self._event('resolve_uncertain', payload={'job_id': job_id, 'reason': reason})

    def recover_orphans(self) -> list[str]:
        """Settle requests left 'sent' by a process that died mid-exchange.

        Only the process that owns the database may call this: a live exchange in another
        process also looks 'sent'. The outcome of an orphan is unknown, so it is never retried.
        """
        with self.transaction():
            orphans = self.connection.execute("SELECT job_id, commission_id FROM v1_job WHERE state='sent'").fetchall()
            for job in orphans:
                self.connection.execute("UPDATE v1_job SET state='uncertain' WHERE job_id=?", (job['job_id'],))
                self._event('orphan_recovered', payload={'job_id': job['job_id']})
            for commission in self.connection.execute("SELECT commission_id FROM v1_commission WHERE status='running'").fetchall():
                lost = any(job['commission_id'] == commission['commission_id'] for job in orphans)
                self._pause(commission['commission_id'], 'accounting_uncertain' if lost else 'interrupted')
        return [job['job_id'] for job in orphans]

    def uncertain_jobs(self) -> list[str]:
        return [r['job_id'] for r in self.connection.execute("SELECT job_id FROM v1_job WHERE state='uncertain'")]

    def redraft(self, ordinal: int) -> str:
        """Single requested draft: stored as a detached alternative, never auto-selected."""
        blocked = self._blocking_reason(ordinal - 1)
        if blocked:
            raise Refused(*blocked)
        artifact_id = self._episode_artifact(ordinal)
        with self.transaction():
            job_id = self._freeze_draft(None, ordinal)
            if job_id is None:
                raise Refused('basis_changed', 'An earlier episode has no selected draft.')
            self.connection.execute("UPDATE v1_job SET state='sent' WHERE job_id=?", (job_id,))
        job = self._one('SELECT * FROM v1_job WHERE job_id=?', job_id)
        variant = self._one('SELECT count(*) FROM v1_revision WHERE artifact_id=?', artifact_id)[0]
        try:
            result = self.provider.generate(GenerationRequest('sequential_draft', job['prompt'], key=job['request_sha256'],
                                                              variant=variant, params={'ordinal': ordinal, 'messages': self.job_messages(job_id)}))
        except NotSent:
            with self.transaction():
                self.connection.execute("UPDATE v1_job SET state='resolved' WHERE job_id=?", (job_id,))
                self._event('not_sent', artifact_id=artifact_id, payload={'job_id': job_id})
            raise
        except AnswerUnusable:
            with self.transaction():
                self.connection.execute("UPDATE v1_job SET state='resolved' WHERE job_id=?", (job_id,))
                self._event('answer_unusable', artifact_id=artifact_id, payload={'job_id': job_id})
            raise Refused('unusable_answer', "The writer's answer was cut off or unusable. It was billed and discarded; asking again is safe.")
        except ProviderUnavailable:
            with self.transaction():
                self.connection.execute("UPDATE v1_job SET state='uncertain' WHERE job_id=?", (job_id,))
            raise Refused('accounting_uncertain', 'The request has no verified outcome. It will not be retried.')
        title, text = split_title(result.text)
        with self.transaction():
            output = self._insert_revision(artifact_id, text, origin='generated', job_id=job_id, reason='requested alternative')
            if title:
                self.connection.execute(
                    'INSERT INTO v1_title(artifact_id,title,revision_id) VALUES(?,?,?) '
                    'ON CONFLICT(artifact_id) DO UPDATE SET title=excluded.title, revision_id=excluded.revision_id',
                    (artifact_id, title, output))
            self.connection.execute("UPDATE v1_job SET state='imported' WHERE job_id=?", (job_id,))
            self.connection.execute('INSERT INTO v1_result VALUES(?,?,?,?)', (job_id, output, 'detached', 'author_request'))
            self._event('result_imported', artifact_id=artifact_id, after=output)
        return output

    def canon(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self.connection.execute('SELECT * FROM v1_canon ORDER BY ordinal')]

    # ---- saving, impact, rewrites, undo -------------------------------
    def _downstream(self, artifact_id: str, revision_id: str) -> list[tuple[int, str]]:
        """Later episodes whose current selection was drafted from `revision_id`."""
        ordinal = self._one('SELECT ordinal FROM v1_artifact WHERE artifact_id=?', artifact_id)['ordinal']
        rows = self.connection.execute(
            """SELECT a.ordinal, a.artifact_id, s.revision_id AS selected FROM v1_selection s JOIN v1_artifact a USING(artifact_id)
               WHERE a.ordinal > ? ORDER BY a.ordinal""", (ordinal,)).fetchall()
        flagged = []
        for r in rows:
            # A hand edit keeps the dependencies of the draft it came from.
            job = self._effective_job(r['selected'])
            drafted_from = job is not None and self._one(
                'SELECT 1 FROM v1_predecessor WHERE job_id=? AND revision_id=?', job, revision_id) is not None
            flagged_by = self._one(
                'SELECT 1 FROM v1_impact WHERE artifact_id=? AND upstream_artifact_id=? AND upstream_revision_id=?',
                r['artifact_id'], artifact_id, revision_id) is not None
            if drafted_from or flagged_by:
                flagged.append((r['ordinal'], r['artifact_id']))
        return flagged

    def _effective_job(self, revision_id: str | None) -> str | None:
        """The draft request behind a revision, following hand edits back to the generated text they started from."""
        seen: set[str] = set()
        while revision_id and revision_id not in seen:
            seen.add(revision_id)
            row = self._one('SELECT job_id, parent_id FROM v1_revision WHERE revision_id=?', revision_id)
            if row is None:
                return None
            if row['job_id']:
                return row['job_id']
            revision_id = row['parent_id']
        return None

    def impact_preview(self, ordinal: int) -> list[int]:
        sel = self.selection(ordinal)
        return [] if sel is None else [n for n, _ in self._downstream(sel['artifact_id'], sel['revision_id'])]

    def _save(self, artifact_id: str, base_revision_id: str, blocks: list[tuple[str | None, str]], *, expected_cas: int,
              action: str, actor: str = 'author', revert_of: str | None = None, payload: dict | None = None,
              restoring: frozenset[str] = frozenset()) -> dict[str, Any]:
        sel = self._one('SELECT * FROM v1_selection WHERE artifact_id=?', artifact_id)
        if sel is None or sel['cas'] != expected_cas or sel['revision_id'] != base_revision_id:
            raise Refused('stale_pointer', 'This episode changed since you opened it. Compare before saving.',
                          current=None if sel is None else sel['revision_id'])
        if self._one("SELECT 1 FROM v1_canon WHERE artifact_id=?", artifact_id):
            raise Refused('accepted', 'Accepted text changes only through a staged change set.')
        base = {b['block_id']: b for b in self.revision(base_revision_id)['blocks']}
        base_order = list(base)
        seen, final, before_images, after_images = set(), [], [], []
        for block_id, text in blocks:
            if block_id is not None and ((block_id not in base and block_id not in restoring) or block_id in seen):
                raise Refused('ambiguous_block', 'A submitted block does not belong to the base revision.')
            block_id = block_id or new_id('b')
            seen.add(block_id)
            final.append((block_id, text))
        final_order = [bid for bid, _ in final]
        # Each image remembers the block before it, so undo can put a deleted paragraph back where it was.
        before_of = lambda order, bid: (order[order.index(bid) - 1] if order.index(bid) > 0 else None)
        for block_id, text in final:
            prior = base.get(block_id)
            if prior is None or prior['text'] != text:
                before_images.append({'block_id': block_id, 'text': None if prior is None else prior['text'],
                                      'prev': before_of(base_order, block_id) if prior is not None else None})
                after_images.append({'block_id': block_id, 'text': text, 'prev': before_of(final_order, block_id)})
        for block_id, prior in base.items():
            if block_id not in seen:
                before_images.append({'block_id': block_id, 'text': prior['text'], 'prev': before_of(base_order, block_id)})
                after_images.append({'block_id': block_id, 'text': None, 'prev': None})
        revision_id = self._insert_revision(artifact_id, '', origin='human', parent_id=base_revision_id, blocks=final, reason=action)
        event_id = self._event(action, actor=actor, artifact_id=artifact_id, before=base_revision_id, after=revision_id,
                               before_images=before_images, after_images=after_images, revert_of=revert_of, payload=payload)
        self._set_selection(artifact_id, revision_id, by='author', event_id=event_id)
        flagged = self._flag_downstream(artifact_id, base_revision_id, revision_id, event_id)
        return {'revision_id': revision_id, 'event_id': event_id, 'flagged': flagged}

    def _flag_downstream(self, artifact_id: str, old_revision_id: str, new_revision_id: str, event_id: str) -> list[int]:
        flagged = []
        for ordinal, downstream in self._downstream(artifact_id, old_revision_id):
            self.connection.execute('INSERT INTO v1_impact VALUES(?,?,?,?,?,?)',
                                    (new_id('im'), downstream, artifact_id, new_revision_id, event_id, 'open'))
            flagged.append(ordinal)
        for row in self.connection.execute("SELECT commission_id FROM v1_commission WHERE status='running'").fetchall():
            if flagged:
                self._pause(row['commission_id'], 'basis_changed')
        return flagged

    def use_draft(self, ordinal: int, revision_id: str, *, expected_cas: int) -> dict[str, Any]:
        """The author takes a set-aside draft of this episode as its draft. It can then be edited like any draft.

        Only a draft this desk set aside for this episode qualifies, and never once the episode is approved."""
        artifact_id = self._episode_artifact(ordinal)
        with self.transaction():
            if self._one('SELECT 1 FROM v1_canon WHERE artifact_id=?', artifact_id):
                raise Refused('accepted', 'Approved text changes only through a staged change set.')
            aside = self._one(
                "SELECT 1 FROM v1_result r JOIN v1_job j USING(job_id) WHERE j.target_artifact_id=? AND r.output_revision_id=? AND r.eligibility='detached'",
                artifact_id, revision_id)
            if aside is None:
                raise Refused('not_found', 'That is not a set-aside draft of this episode.')
            sel = self._one('SELECT * FROM v1_selection WHERE artifact_id=?', artifact_id)
            if (sel['cas'] if sel else 0) != expected_cas:
                raise Refused('stale_pointer', 'This episode changed since you opened it. Compare before using a draft.',
                              current=None if sel is None else sel['revision_id'])
            if sel is not None and sel['revision_id'] == revision_id:
                return {'revision_id': revision_id, 'event_id': None, 'flagged': []}
            event_id = self._event('use_draft', actor='author', artifact_id=artifact_id,
                                   before=sel['revision_id'] if sel else None, after=revision_id)
            self._set_selection(artifact_id, revision_id, by='author', event_id=event_id)
            flagged = self._flag_downstream(artifact_id, sel['revision_id'], revision_id, event_id) if sel else []
        return {'revision_id': revision_id, 'event_id': event_id, 'flagged': flagged}

    def save_revision(self, ordinal: int, *, base_revision_id: str, blocks: list[tuple[str | None, str]], expected_cas: int) -> dict[str, Any]:
        with self.transaction():
            return self._save(self._episode_artifact(ordinal), base_revision_id, blocks, expected_cas=expected_cas, action='save')

    def revalidate(self, ordinal: int) -> int:
        """Author attestation that the downstream text still fits the current upstream."""
        artifact_id = self._episode_artifact(ordinal)
        with self.transaction():
            changed = self.connection.execute("UPDATE v1_impact SET state='revalidated' WHERE artifact_id=? AND state='open'", (artifact_id,)).rowcount
            if changed:
                self._event('revalidate', artifact_id=artifact_id, payload={'impacts': changed})
        return changed

    PLOT_WORDS = ('plot', 'motive', 'knowledge', 'knows', 'contradiction', 'reveal', 'dies', 'alive')

    def request_rewrite(self, ordinal: int, *, block_id: str, expected_sha256: str, intent: str, reason: str) -> str:
        if intent == 'polish' and any(w in reason.lower() for w in self.PLOT_WORDS):
            raise Refused('polish_refused', 'This reason changes the story; request a story rewrite instead.')
        sel = self.selection(ordinal)
        if sel is None:
            raise Refused('not_found', 'Select a draft before rewriting it.')
        blocks = self.revision(sel['revision_id'])['blocks']
        index = next((i for i, b in enumerate(blocks) if b['block_id'] == block_id), None)
        if index is None or blocks[index]['sha256'] != expected_sha256:
            raise Refused('invalid_range', 'The passage you selected is not in the current text.')
        self._refuse_secret_in_message(reason + '\n' + blocks[index]['text'], ordinal)
        context = [{'block_id': b['block_id'], 'sha256': b['sha256']} for b in blocks[max(0, index - 1):index + 2]]
        variant = self._one('SELECT count(*) FROM v1_rewrite WHERE base_revision_id=? AND block_id=?', sel['revision_id'], block_id)[0]
        result = self.provider.generate(GenerationRequest(f'{intent}_rewrite', reason, key=expected_sha256, variant=variant,
                                                          params={'block_text': blocks[index]['text']}))
        candidate_id = new_id('cd')
        with self.transaction():
            self.connection.execute('INSERT INTO v1_rewrite VALUES(?,?,?,?,?,?,?,?,?,?)',
                                    (candidate_id, sel['artifact_id'], sel['revision_id'], block_id, expected_sha256, result.text,
                                     json.dumps(context), intent, reason, 'open'))
        return candidate_id

    def apply_candidate(self, candidate_id: str, *, expected_cas: int) -> dict[str, Any]:
        with self.transaction():
            cand = self._one("SELECT * FROM v1_rewrite WHERE candidate_id=?", candidate_id)
            if cand is None or cand['disposition'] != 'open':
                raise Refused('not_found', 'This candidate is no longer open.')
            sel = self._one('SELECT * FROM v1_selection WHERE artifact_id=?', cand['artifact_id'])
            current = {b['block_id']: b for b in self.revision(sel['revision_id'])['blocks']}
            for item in json.loads(cand['context']):
                if current.get(item['block_id'], {}).get('sha256') != item['sha256']:
                    base_text = next(b['text'] for b in self.revision(cand['base_revision_id'])['blocks'] if b['block_id'] == cand['block_id'])
                    now = current.get(cand['block_id'], {}).get('text')
                    raise Refused('overlap', 'The passage changed after this rewrite was requested.',
                                  before=base_text, ai=cand['replacement'], now=now)
            blocks = [(b['block_id'], cand['replacement'] if b['block_id'] == cand['block_id'] else b['text'])
                      for b in self.revision(sel['revision_id'])['blocks']]
            saved = self._save(cand['artifact_id'], sel['revision_id'], blocks, expected_cas=expected_cas,
                               action='rewrite_apply', payload={'candidate_id': candidate_id})
            self.connection.execute("UPDATE v1_rewrite SET disposition='applied' WHERE candidate_id=?", (candidate_id,))
            return saved

    def _reapply(self, event: sqlite3.Row, *, expect: str, restore: str, action: str, revert_of: str) -> dict[str, Any]:
        """Swap block images if, and only if, every touched block still shows `expect`."""
        images = {i['block_id']: i['text'] for i in json.loads(event[expect])}
        target_items = json.loads(event[restore])
        target = {i['block_id']: i['text'] for i in target_items}
        target_prev = {i['block_id']: i.get('prev', '\0') for i in target_items}
        sel = self._one('SELECT * FROM v1_selection WHERE artifact_id=?', event['artifact_id'])
        current = self.revision(sel['revision_id'])['blocks']
        present = {b['block_id']: b['text'] for b in current}
        for block_id, text in images.items():
            if present.get(block_id) != text:
                raise Refused('overlap', 'That passage changed since; undo would overwrite newer words.',
                              block_id=block_id, now=present.get(block_id), expected=text)
        blocks = [(b['block_id'], target.get(b['block_id'], b['text'])) for b in current if target.get(b['block_id'], b['text']) is not None]
        restoring = set()
        for bid, text in target.items():
            if bid in present or text is None:
                continue
            restoring.add(bid)
            prev = target_prev.get(bid, '\0')
            at = next((i for i, (x, _) in enumerate(blocks) if x == prev), None)
            # prev None means first; a missing or unknown neighbour (older events) puts it last.
            position = 0 if prev is None else (at + 1 if at is not None else len(blocks))
            blocks.insert(position, (bid, text))
        return self._save(event['artifact_id'], sel['revision_id'], blocks, expected_cas=sel['cas'], action=action, revert_of=revert_of,
                          restoring=frozenset(restoring))

    def revert_event(self, event_id: str) -> dict[str, Any]:
        with self.transaction():
            event = self._one('SELECT * FROM v1_event WHERE event_id=?', event_id)
            if event is None:
                raise Refused('not_found', 'Unknown history event.')
            if event['action'] == 'adopt':
                current = self.governing(event['artifact_id'])
                if current is None or current['revision_id'] != event['revision_after']:
                    raise Refused('stale_pointer', 'Direction changed since this adoption.')
                if event['revision_before'] is None:
                    self.connection.execute('DELETE FROM v1_governing WHERE scope_kind=?', (event['artifact_id'],))
                else:
                    self.connection.execute('UPDATE v1_governing SET revision_id=?, cas=cas+1 WHERE scope_kind=?',
                                            (event['revision_before'], event['artifact_id']))
                return {'event_id': self._event('revert', artifact_id=event['artifact_id'], revert_of=event_id,
                                                before=event['revision_after'], after=event['revision_before'])}
            if event['action'] not in ('save', 'rewrite_apply', 'revert', 'redo'):
                raise Refused('not_revertible', 'This event is not undone here; accepted text uses a change set.')
            saved = self._reapply(event, expect='after_images', restore='before_images', action='revert', revert_of=event_id)
            for row in self.connection.execute("SELECT style_id FROM v1_style_evidence WHERE event_id=? AND status='active'", (event_id,)).fetchall():
                self.connection.execute("UPDATE v1_style_evidence SET status='withdrawn' WHERE event_id=?", (event_id,))
                self.connection.execute('UPDATE v1_style SET needs_reaffirm=1 WHERE style_id=?', (row['style_id'],))
            return saved

    def redo_event(self, event_id: str) -> dict[str, Any]:
        """Redo reuses the stored after-images; no provider call."""
        with self.transaction():
            event = self._one('SELECT * FROM v1_event WHERE event_id=?', event_id)
            if event is None or self._one("SELECT 1 FROM v1_event WHERE revert_of=? AND action='revert'", event_id) is None:
                raise Refused('not_found', 'Only an undone event can be redone.')
            return self._reapply(event, expect='before_images', restore='after_images', action='redo', revert_of=event_id)

    # ---- acceptance -----------------------------------------------------
    def accept_prefix(self, episodes: list[tuple[int, str, str]], *, expected_canon_seq: int) -> dict[str, Any]:
        with self.transaction():
            seq = self._one('SELECT canon_seq FROM v1_meta WHERE id=1')[0]
            if seq != expected_canon_seq:
                raise Refused('stale_pointer', 'Accepted history changed. Reload before accepting.', current=seq)
            cursor = self._one('SELECT coalesce(max(ordinal),0) FROM v1_canon')[0]
            ordinals = [n for n, _, _ in episodes]
            if not episodes or ordinals != list(range(cursor + 1, cursor + 1 + len(episodes))):
                raise Refused('prefix_invalid', 'Accept episodes in order, starting right after the accepted text.')
            listed: dict[int, str] = {}
            warnings = []
            for n, revision_id, digest in episodes:
                sel = self.selection(n)
                if sel is None or sel['revision_id'] != revision_id or sel['sha256'] != digest:
                    raise Refused('prefix_invalid', f'Episode {n} is not the current selected text.')
                if self._one("SELECT 1 FROM v1_impact WHERE artifact_id=? AND state='open'", sel['artifact_id']):
                    raise Refused('open_conflict', f'Episode {n} is flagged by an upstream change.')
                job = self._effective_job(revision_id)
                for p in self.connection.execute('SELECT * FROM v1_predecessor WHERE job_id=? ORDER BY position', (job,)).fetchall() if job else []:
                    upstream_ordinal = p['position'] + 1
                    current = listed.get(upstream_ordinal) or self._one('SELECT revision_id FROM v1_canon WHERE ordinal=?', upstream_ordinal)['revision_id']
                    if p['revision_id'] != current and self._one(
                            "SELECT 1 FROM v1_impact WHERE artifact_id=? AND upstream_revision_id=? AND state='revalidated'",
                            sel['artifact_id'], current) is None:
                        raise Refused('prefix_invalid', f'Episode {n} was drafted from an older episode {upstream_ordinal}.')
                listed[n] = revision_id
                warning = length_warning(n, len(self.revision(revision_id)['text'].split()))
                if warning:
                    warnings.append(warning)
            acceptance_id = new_id('ac')
            for n, revision_id, digest in episodes:
                text = self.revision(revision_id)['text']
                self.connection.execute('INSERT INTO v1_canon VALUES(?,?,?,?,?,?)',
                                        (n, self._episode_artifact(n), revision_id, digest, text, acceptance_id))
                self.connection.execute("INSERT INTO v1_outbox VALUES(?,?,?,'awaiting_authority')", (new_id('ob'), revision_id, digest))
            self.connection.execute('INSERT INTO v1_acceptance VALUES(?,?,?,?,?)',
                                    (acceptance_id, seq, seq + 1, json.dumps(episodes), json.dumps(warnings)))
            self.connection.execute('UPDATE v1_meta SET canon_seq=canon_seq+1 WHERE id=1')
            self._event('accept', payload={'acceptance_id': acceptance_id, 'episodes': episodes})
        return {'acceptance_id': acceptance_id, 'canon_seq': seq + 1, 'warnings': warnings}

    # ---- memory ---------------------------------------------------------
    def _extract(self, revision_id: str, ordinal: int, mode: str, *, task_id: str | None = None) -> int:
        """One model reading of a revision. Every returned item is kept, counted or quarantined; none vanishes.

        The model supplies a quote; positions are found here. A preview goes to its own table and
        never into the ledger. Returns the number of claims kept.
        """
        revision = self.revision(revision_id)
        blocks = revision['blocks']
        digest = self._one('SELECT content_sha256 FROM v1_revision WHERE revision_id=?', revision_id)[0]
        raw = self.provider.generate(GenerationRequest('promotion', revision_id, key=revision_id,
                                                       params={'blocks': [{'block_id': b['block_id'], 'text': b['text']} for b in blocks]})).text
        extraction_id = new_id('ex')
        try:
            items = json.loads(raw)
            if not isinstance(items, list):
                raise ValueError('not a list')
        except ValueError:
            with self.transaction():
                self.connection.execute('INSERT INTO v1_extraction VALUES(?,?,?,?,?,0,0,0,0,0,0,NULL)',
                                        (extraction_id, revision_id, digest, mode, 'unreadable'))
                self.connection.execute('INSERT INTO v1_claim_quarantine VALUES(?,?,?,?,?)',
                                        (new_id('qa'), extraction_id, revision_id, 'unreadable_output', str(raw)[:4000]))
            raise Refused('unreadable_extraction', 'The memory reading was not a list of claims. Nothing was saved; try again.',
                          extraction_id=extraction_id)
        kept: list[tuple[dict[str, Any], str, int, int, str]] = []
        quarantined: list[tuple[str, Any]] = []
        seen: set[tuple[Any, ...]] = set()
        counts = {'exact': 0, 'loose': 0, 'ambiguous': 0, 'duplicates': 0}
        for item in items:
            problem = _claim_problem(item)
            where = None if problem else _anchor(blocks, item)
            if problem is None and where is None:
                problem = 'quote_not_found'
            if problem:
                quarantined.append((problem, item))
                continue
            block_id, start, end, anchor = where
            key = (block_id, start, end, item['kind'], item.get('subject', ''), item.get('speaker'), item.get('holder'))
            if key in seen:
                counts['duplicates'] += 1
                continue
            seen.add(key)
            counts[anchor] += 1
            kept.append((item, block_id, start, end, anchor))
        by_id = {b['block_id']: b['text'] for b in blocks}
        with self.transaction():
            # Another Save may have imported this task while the model was reading. The write lock is held now, so check again.
            if task_id is not None and self._one("SELECT 1 FROM v1_outbox WHERE task_id=? AND state='awaiting_authority'", task_id) is None:
                return 0
            if mode == 'preview' and self._preview_for(revision_id, digest) is not None:
                return 0
            self.connection.execute('INSERT INTO v1_extraction VALUES(?,?,?,?,?,?,?,?,?,?,?,NULL)',
                                    (extraction_id, revision_id, digest, mode, 'read', len(items), counts['exact'], counts['loose'],
                                     counts['ambiguous'], counts['duplicates'], len(quarantined)))
            for item, block_id, start, end, anchor in kept:
                row = (new_id('cl'), item['kind'], item.get('subject') or '', item.get('speaker'), item.get('holder'),
                       item.get('stance') or 'asserts', item.get('world_validity') or 'unknown', ordinal, revision_id)
                quote = by_id[block_id][start:end]
                if mode == 'preview':
                    self.connection.execute('INSERT INTO v1_claim_preview VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                                            row + (digest, block_id, start, end, quote, anchor, extraction_id))
                else:
                    self.connection.execute(
                        'INSERT INTO v1_claim(claim_id,kind,subject,speaker,holder,stance,world_validity,narrative_ordinal,revision_id,block_id,start,"end",quote,standing,anchor,extraction_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                        row + (block_id, start, end, quote, 'accepted_derived', anchor, extraction_id))
            for problem, item in quarantined:
                self.connection.execute('INSERT INTO v1_claim_quarantine VALUES(?,?,?,?,?)',
                                        (new_id('qa'), extraction_id, revision_id, problem, json.dumps(item, default=str)[:4000]))
            if task_id is not None:
                self.connection.execute("UPDATE v1_outbox SET state='imported' WHERE task_id=?", (task_id,))
        return len(kept)

    def _promote_preview(self, preview: sqlite3.Row, canon: sqlite3.Row, task_id: str) -> int:
        """Confirming memory copies a matching preview into the ledger; the model is not asked twice."""
        rows = self.connection.execute('SELECT * FROM v1_claim_preview WHERE extraction_id=?', (preview['extraction_id'],)).fetchall()
        extraction_id = new_id('ex')
        with self.transaction():
            if self._one("SELECT 1 FROM v1_outbox WHERE task_id=? AND state='awaiting_authority'", task_id) is None:
                return 0  # a concurrent Save already imported these facts
            self.connection.execute('INSERT INTO v1_extraction VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                                    (extraction_id, preview['revision_id'], preview['content_sha256'], 'accepted', 'read',
                                     preview['returned'], preview['anchored_exact'], preview['anchored_loose'],
                                     preview['anchored_ambiguous'], preview['duplicates'], preview['quarantined'],
                                     preview['extraction_id']))
            for r in rows:
                self.connection.execute(
                    'INSERT INTO v1_claim(claim_id,kind,subject,speaker,holder,stance,world_validity,narrative_ordinal,revision_id,block_id,start,"end",quote,standing,anchor,extraction_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    (new_id('cl'), r['kind'], r['subject'], r['speaker'], r['holder'], r['stance'], r['world_validity'],
                     canon['ordinal'], r['revision_id'], r['block_id'], r['start'], r['end'], r['quote'], 'accepted_derived',
                     r['anchor'], extraction_id))
            self.connection.execute("UPDATE v1_outbox SET state='imported' WHERE task_id=?", (task_id,))
        return len(rows)

    def _preview_for(self, revision_id: str, digest: str) -> sqlite3.Row | None:
        return self._one("SELECT * FROM v1_extraction WHERE revision_id=? AND content_sha256=? AND mode='preview' AND outcome='read'",
                         revision_id, digest)

    def read_provisional(self, ordinal: int) -> int:
        sel = self.selection(ordinal)
        if sel is None:
            raise Refused('not_found', 'No selected draft to read.')
        existing = self._preview_for(sel['revision_id'], sel['sha256'])
        if existing is not None:
            return existing['anchored_exact'] + existing['anchored_loose'] + existing['anchored_ambiguous']
        return self._extract(sel['revision_id'], ordinal, 'preview')

    def extraction_receipts(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self.connection.execute('SELECT * FROM v1_extraction ORDER BY rowid')]

    def quarantine(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self.connection.execute('SELECT * FROM v1_claim_quarantine ORDER BY rowid')]

    # ---- author-only secrets -------------------------------------------
    # A secret's words are author-only. Each secret carries canary terms: distinctive words that must not
    # appear in any drafter request before the reveal episode. The gate is `secret_hits`, called by
    # `_freeze_draft`. Secret bodies and canaries are never written to events, jobs, snapshots or prompts.
    def _drafter_visible_texts(self) -> list[str]:
        texts = []
        skeleton, arc = self.governing('skeleton'), self.governing('arc')
        if skeleton:
            texts.append(str(skeleton['content'].get('spine', '')))
        if arc:
            texts.append(str(arc['content'].get('purpose', '')))
            texts += [str(i) for i in arc['content'].get('intentions', [])]
        texts += [r['note'] for r in self.connection.execute("SELECT note FROM v1_style WHERE status='adopted'")]
        sheet = self.style_sheet()
        if sheet is not None:
            texts.append(sheet['body'] + '\n' + '\n'.join(sheet['avoid']))
        texts += [r['text'] for r in self.connection.execute('SELECT text FROM v1_canon')]
        texts += [r['content'] for r in self.connection.execute(
            'SELECT r.content FROM v1_selection s JOIN v1_revision r USING(revision_id)')]
        return texts

    def secret_hits(self, text: str, ordinal: int) -> list[dict[str, str]]:
        """Secrets still guarded at this episode whose canary appears in `text`."""
        folded = _scrub(text)
        hits: dict[str, dict[str, str]] = {}
        for r in self.connection.execute(
                "SELECT s.secret_id, s.label, c.term FROM v1_secret s JOIN v1_secret_canary c USING(secret_id) "
                "WHERE s.status='active' AND (s.reveal_ordinal IS NULL OR s.reveal_ordinal > ?) ORDER BY s.rowid", (ordinal,)):
            if r['secret_id'] not in hits and _scrub(r['term']) in folded:
                hits[r['secret_id']] = {'secret_id': r['secret_id'], 'label': r['label']}
        return list(hits.values())

    def add_secret(self, *, label: str, body: str, canaries: list[str], reveal_ordinal: int | None = None) -> str:
        def invalid(message: str) -> Refused:
            return Refused('invalid_secret', message)
        if not isinstance(label, str) or not label.strip() or len(label.strip()) > 80:
            raise invalid('A secret needs a short label.')
        if not isinstance(body, str) or not body.strip() or len(body) > 4000:
            raise invalid('A secret needs its words written down.')
        if not isinstance(canaries, list) or not 1 <= len(canaries) <= 8:
            raise invalid('Give one to eight distinctive words that must not appear before the reveal.')
        terms = []
        for term in canaries:
            if not isinstance(term, str) or not 4 <= len(term.strip()) <= 60 or '\n' in term:
                raise invalid('Each protected word needs 4 to 60 characters.')
            if term.strip().casefold() in {t.casefold() for t in terms}:
                raise invalid('Protected words must be different from each other.')
            terms.append(term.strip())
        if reveal_ordinal is not None and (type(reveal_ordinal) is not int or reveal_ordinal < 1):
            raise invalid('The reveal episode must be 1 or higher, or left empty.')
        with self.transaction():
            visible = [_scrub(t) for t in self._drafter_visible_texts()]
            for term in terms:
                if any(_scrub(term) in v for v in visible):
                    raise Refused('canary_already_visible',
                                  'One protected word already appears in text the drafter receives. Choose another word, or remove it from the text first.')
            secret_id = new_id('sc')
            self.connection.execute('INSERT INTO v1_secret(secret_id,label,body,reveal_ordinal) VALUES(?,?,?,?)',
                                    (secret_id, label.strip(), body.strip(), reveal_ordinal))
            for term in terms:
                self.connection.execute('INSERT INTO v1_secret_canary VALUES(?,?)', (secret_id, term))
            self._event('secret_add', payload={'secret_id': secret_id})
        return secret_id

    def _secret_change(self, secret_id: str, sql: str, args: tuple, action: str) -> None:
        with self.transaction():
            if self.connection.execute(sql, args + (secret_id,)).rowcount != 1:
                raise Refused('not_found', 'Unknown secret.')
            self._event(action, payload={'secret_id': secret_id})

    def reveal_secret(self, secret_id: str, ordinal: int | None) -> None:
        """The reader may learn this at `ordinal`; None guards it again."""
        if ordinal is not None and (type(ordinal) is not int or ordinal < 1):
            raise Refused('invalid_secret', 'The reveal episode must be 1 or higher.')
        self._secret_change(secret_id, 'UPDATE v1_secret SET reveal_ordinal=? WHERE secret_id=?', (ordinal,), 'secret_reveal')

    def retire_secret(self, secret_id: str) -> None:
        self._secret_change(secret_id, "UPDATE v1_secret SET status='retired' WHERE secret_id=?", (), 'secret_retire')

    # ---- writing-style sheet --------------------------------------------
    # Editable by the author, versioned, never edited in place. The fixed rules in `draft_prompt`
    # (output form, naming, order of authority) are not part of it and cannot be changed from here.
    @staticmethod
    def _sheet_row(row: sqlite3.Row) -> dict[str, Any]:
        return {'version': row['version'], 'body': row['body'], 'avoid': json.loads(row['avoid'])}

    def word_band(self) -> tuple[int, int, int]:
        row = self._one('SELECT low, target, high FROM v1_length ORDER BY version DESC LIMIT 1')
        return WORD_BAND if row is None else (row['low'], row['target'], row['high'])

    def length_setting(self) -> dict[str, Any]:
        low, target, high = self.word_band()
        return {'low': low, 'target': target, 'high': high, 'limit': hard_limit(high),
                'custom': self._one('SELECT 1 FROM v1_length') is not None}

    def set_length(self, *, low: int, target: int, high: int) -> dict[str, Any]:
        """The author's words-per-episode for this series. It applies to drafts requested from now on; drafts already
        made are never changed or flagged by it."""
        lo, hi = LENGTH_BOUNDS
        values = (low, target, high)
        if any(isinstance(v, bool) or not isinstance(v, int) for v in values):
            raise Refused('invalid_length', 'Give whole numbers of words for the shortest, the aim and the longest.')
        if not (lo <= low <= target <= high <= hi):
            raise Refused('invalid_length', f'Use this order: shortest, then the aim, then longest, all between {lo} and {hi} words.')
        with self.transaction():
            if self.word_band() != values:
                version = self.connection.execute('INSERT INTO v1_length(low,target,high) VALUES(?,?,?)', values).lastrowid
                self._event('length_save', payload={'version': version, 'low': low, 'target': target, 'high': high})
        return self.length_setting()

    def style_sheet(self) -> dict[str, Any] | None:
        row = self._one('SELECT * FROM v1_style_sheet ORDER BY version DESC LIMIT 1')
        return None if row is None else self._sheet_row(row)

    def style_sheet_versions(self) -> list[dict[str, Any]]:
        return [self._sheet_row(r) for r in self.connection.execute('SELECT * FROM v1_style_sheet ORDER BY version DESC')]

    def save_style_sheet(self, body: str, avoid: list[str]) -> int:
        def invalid(message: str) -> Refused:
            return Refused('invalid_style_sheet', message)
        if not isinstance(body, str) or len(body) > 4000:
            raise invalid('The style sheet must be text of at most 4,000 characters.')
        if not isinstance(avoid, list) or len(avoid) > 40:
            raise invalid('The avoid list can hold at most 40 items.')
        items: list[str] = []
        for term in avoid:
            if not isinstance(term, str) or not 1 <= len(term.strip()) <= 40 or '\n' in term:
                raise invalid('Each avoid item needs 1 to 40 characters on one line.')
            if term.strip().casefold() in {t.casefold() for t in items}:
                raise invalid('Avoid items must be different from each other.')
            items.append(term.strip())
        body = body.strip()
        if not body and not items:
            raise invalid('Write something in the style sheet or the avoid list.')
        hits = self.secret_hits(body + '\n' + '\n'.join(items), 1)
        if hits:
            raise Refused('secret_in_input', 'The style sheet reaches the drafter in every episode, '
                          f'so it cannot contain protected words ({", ".join(h["label"] for h in hits)}).',
                          secrets=[h['secret_id'] for h in hits])
        with self.transaction():
            current = self.style_sheet()
            if current is not None and current['body'] == body and current['avoid'] == items:
                return current['version']
            version = self.connection.execute('INSERT INTO v1_style_sheet(body,avoid) VALUES(?,?)',
                                              (body, json.dumps(items, ensure_ascii=False))).lastrowid
            self._event('style_sheet_save', payload={'version': version})
        return version

    def style_hits(self, text: str) -> list[str]:
        """Avoid-list items found in `text` under the current sheet, in the sheet's order."""
        sheet = self.style_sheet()
        folded = text.casefold()
        return [] if sheet is None else [term for term in sheet['avoid'] if term.casefold() in folded]

    def style_version_for(self, revision_id: str) -> int | None:
        row = self._one('SELECT js.version FROM v1_job_style js JOIN v1_result r ON r.job_id=js.job_id WHERE r.output_revision_id=?',
                        revision_id)
        return None if row is None else row['version']

    def secrets(self) -> list[dict[str, Any]]:
        """Author-only listing. Nothing that builds a model request calls this."""
        out = []
        for r in self.connection.execute('SELECT * FROM v1_secret ORDER BY rowid'):
            terms = [t['term'] for t in self.connection.execute('SELECT term FROM v1_secret_canary WHERE secret_id=? ORDER BY rowid', (r['secret_id'],))]
            out.append({**dict(r), 'canaries': terms})
        return out

    def update_memory(self) -> dict[str, int]:
        """Explicitly authorized memory pass over exact accepted text."""
        counts = {'imported': 0, 'obsolete': 0}
        for task in self.connection.execute("SELECT * FROM v1_outbox WHERE state='awaiting_authority'").fetchall():
            canon = self._one('SELECT * FROM v1_canon WHERE revision_id=? AND sha256=?', task['revision_id'], task['sha256'])
            if canon is None:
                with self.transaction():
                    self.connection.execute("UPDATE v1_outbox SET state='obsolete' WHERE task_id=?", (task['task_id'],))
                counts['obsolete'] += 1
                continue
            preview = self._preview_for(canon['revision_id'], canon['sha256'])
            if preview is not None:
                self._promote_preview(preview, canon, task['task_id'])
            else:
                self._extract(canon['revision_id'], canon['ordinal'], 'accepted', task_id=task['task_id'])
            counts['imported'] += 1
        return counts

    def memory(self, *, boundary: int | None = None) -> dict[str, list[dict[str, Any]]]:
        """Current accepted claims (those no later claim corrects) and, separately, previews of unaccepted selected drafts."""
        limit = boundary if boundary is not None else 10**9
        accepted = [dict(r) for r in self.connection.execute(
            "SELECT c.* FROM v1_claim c JOIN v1_canon k ON k.revision_id=c.revision_id WHERE c.narrative_ordinal<=? "
            "AND NOT EXISTS (SELECT 1 FROM v1_claim n WHERE n.prior_claim_id=c.claim_id) "
            "ORDER BY c.narrative_ordinal, c.block_id, c.start", (limit,))]
        provisional = [{**dict(r), 'standing': 'preview'} for r in self.connection.execute(
            "SELECT p.* FROM v1_claim_preview p JOIN v1_selection s ON s.revision_id=p.revision_id "
            "WHERE p.narrative_ordinal<=? AND p.revision_id NOT IN (SELECT revision_id FROM v1_canon) "
            "ORDER BY p.narrative_ordinal, p.block_id, p.start", (limit,))]
        # Previews of approved revisions whose facts Save has not yet promoted: read-only, so the writer
        # can keep reviewing exactly what Save will add after Approve.
        awaiting = [{**dict(r), 'standing': 'preview'} for r in self.connection.execute(
            "SELECT p.* FROM v1_claim_preview p JOIN v1_canon k ON k.revision_id=p.revision_id "
            "WHERE p.narrative_ordinal<=? AND NOT EXISTS (SELECT 1 FROM v1_claim c WHERE c.revision_id=p.revision_id) "
            "ORDER BY p.narrative_ordinal, p.block_id, p.start", (limit,))]
        return {'accepted': accepted, 'provisional': provisional, 'awaiting': awaiting}

    def interpret(self, claim_id: str, *, kind: str, speaker: str | None, world_validity: str, note: str, holder: str | None = None) -> str:
        """A correction is a new claim revision that supersedes, never erases, the old one."""
        with self.transaction():
            old = self._one("SELECT * FROM v1_claim WHERE claim_id=?", claim_id)
            if old is None or self._one('SELECT 1 FROM v1_claim WHERE prior_claim_id=?', claim_id):
                raise Refused('stale_pointer', 'This reading was already corrected.')
            holder = holder if holder is not None else old['holder']
            problem = _claim_problem({'kind': kind, 'speaker': speaker, 'holder': holder, 'stance': old['stance'],
                                      'world_validity': world_validity})
            if problem:
                raise Refused('invalid_claim', _CORRECTION_PROBLEMS.get(problem, 'That correction is not a valid reading.'))
            new = new_id('cl')
            self.connection.execute(
                'INSERT INTO v1_claim(claim_id,kind,subject,speaker,holder,stance,world_validity,narrative_ordinal,revision_id,block_id,start,"end",quote,standing,prior_claim_id,note,anchor,extraction_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (new, kind, old['subject'], speaker, holder, old['stance'], world_validity, old['narrative_ordinal'],
                 old['revision_id'], old['block_id'], old['start'], old['end'], old['quote'], old['standing'], claim_id, note,
                 old['anchor'], old['extraction_id']))
            self._event('interpret', payload={'claim_id': new, 'supersedes': claim_id})
        return new

    def claim_history(self, claim_id: str) -> list[dict[str, Any]]:
        """Newest first. A claim is superseded exactly when another claim names it as its predecessor."""
        chain, current = [], claim_id
        while current:
            row = self._one('SELECT * FROM v1_claim WHERE claim_id=?', current)
            entry = dict(row)
            if self._one('SELECT 1 FROM v1_claim WHERE prior_claim_id=?', current):
                entry['standing'] = 'superseded'
            chain.append(entry)
            current = row['prior_claim_id']
        return chain

    def prepare_context(self, *, boundary: int) -> dict[str, Any]:
        blocked = self._blocking_reason(boundary)
        if blocked:
            raise Refused(*blocked)
        canon = [r for r in self.canon() if r['ordinal'] <= boundary]
        covered = all(self._one("SELECT 1 FROM v1_outbox WHERE revision_id=? AND sha256=? AND state='imported'", r['revision_id'], r['sha256'])
                      for r in canon)
        governing = {k: (self.governing(k) or {}).get('revision_id') for k in ('skeleton', 'arc')}
        if canon and covered:
            return {'mode': 'indexed', 'boundary': boundary, 'governing': governing,
                    'claims': self.memory(boundary=boundary)['accepted'],
                    'items': [{'ordinal': r['ordinal'], 'sha256': r['sha256']} for r in canon]}
        return {'mode': 'exact_text', 'boundary': boundary, 'governing': governing,
                'notice': 'Memory updating; using exact accepted pages.',
                'items': [{'ordinal': r['ordinal'], 'sha256': r['sha256'], 'text': r['text']} for r in canon]}

    # ---- read model -----------------------------------------------------
    def _alternative(self, row: dict[str, Any]) -> dict[str, Any]:
        text = self.revision(row['revision_id'])['text']
        return {**row, 'words': len(text.split()), 'text': text}

    def _pause_detail(self, commission: dict[str, Any]) -> dict[str, Any] | None:
        """For a run stopped by length: the episode, its word count and the limit."""
        if commission['status'] != 'paused' or commission['pause_reason'] != 'over_length':
            return None
        row = self._one(
            "SELECT a.ordinal, r.output_revision_id FROM v1_result r JOIN v1_job j USING(job_id) JOIN v1_artifact a ON a.artifact_id=j.target_artifact_id "
            "WHERE j.commission_id=? AND r.eligibility='detached' AND r.detached_reason='over_length' ORDER BY j.rowid DESC LIMIT 1", commission['commission_id'])
        if row is None:
            return None
        words, limit = len(self.revision(row['output_revision_id'])['text'].split()), hard_limit(self.word_band()[2])
        # The limit can be raised after a draft was set aside; then the draft is within it now.
        return {'ordinal': row['ordinal'], 'words': words, 'limit': limit, 'within_limit': words <= limit}

    def snapshot(self, *, history_limit: int = 40) -> dict[str, Any]:
        meta = self._one('SELECT story_id, canon_seq FROM v1_meta WHERE id=1')
        canon = self.canon()
        accepted = {r['ordinal'] for r in canon}
        episodes = []
        known = {w for layer in ('skeleton', 'arc') for w in seen_words(json.dumps((self.governing(layer) or {}).get('content', {})))}
        for artifact in self.artifacts('episode'):
            n, artifact_id = artifact['ordinal'], artifact['artifact_id']
            sel = self.selection(n)
            titled = self._one('SELECT title FROM v1_title WHERE artifact_id=?', artifact_id)
            entry = {'ordinal': n, 'artifact_id': artifact_id, 'selection': sel, 'accepted': n in accepted,
                     'title': titled['title'] if titled else None,
                     'memory_state': None, 'text': None, 'blocks': [], 'words': 0, 'length_warning': None, 'new_names': [], 'secret_hits': [], 'style_hits': [], 'predecessors': [],
                     'open_impacts': self._one("SELECT count(*) FROM v1_impact WHERE artifact_id=? AND state='open'", artifact_id)[0],
                     'alternatives': [self._alternative(dict(r)) for r in self.connection.execute(
                         "SELECT r.output_revision_id AS revision_id, r.detached_reason FROM v1_result r JOIN v1_job j USING(job_id) WHERE j.target_artifact_id=? AND r.eligibility='detached' ORDER BY j.rowid", (artifact_id,))]}
            if n in accepted:
                held = next(r for r in canon if r['ordinal'] == n)
                entry['memory_state'] = 'read' if self._one(
                    "SELECT 1 FROM v1_outbox WHERE revision_id=? AND sha256=? AND state='imported'", held['revision_id'], held['sha256']) else 'waiting'
            if sel or n in accepted:
                # Approved episodes are read from canon, never from the mutable selection pointer.
                shown = held['revision_id'] if n in accepted else sel['revision_id']
                revision = self.revision(shown)
                words = len(revision['text'].split())
                if n not in accepted:
                    entry['new_names'] = sorted(w for w in proper_names(revision['text']) if w.lower() not in known)
                known |= seen_words(revision['text'])
                entry.update(text=revision['text'], blocks=revision['blocks'], words=words, length_warning=length_warning(n, words, self.word_band()),
                             secret_hits=[h['label'] for h in self.secret_hits(revision['text'], n)],
                             style_hits=self.style_hits(revision['text']))
                effective = self._effective_job(shown)
                if effective:
                    entry['predecessors'] = [[r['revision_id'], r['sha256']] for r in self.connection.execute(
                        'SELECT revision_id, sha256 FROM v1_predecessor WHERE job_id=? ORDER BY position', (effective,))]
            episodes.append(entry)
        directions = {}
        for layer in ('skeleton', 'arc'):
            head = self._one("SELECT r.revision_id, r.content FROM v1_revision r JOIN v1_artifact a USING(artifact_id) WHERE a.kind=? ORDER BY r.seq DESC LIMIT 1", layer)
            directions[layer] = None if head is None else {'revision_id': head['revision_id'], 'content': json.loads(head['content'])}
        undone = {r['revert_of'] for r in self.connection.execute("SELECT revert_of FROM v1_event WHERE action='revert' AND revert_of IS NOT NULL")}
        history = [{**dict(r), 'undone': r['event_id'] in undone} for r in self.connection.execute(
            'SELECT seq, event_id, action, actor, artifact_id, revert_of FROM v1_event ORDER BY seq DESC LIMIT ?', (history_limit,))]
        return {
            'story': {'story_id': meta['story_id'], 'canon_seq': meta['canon_seq']},
            'governing': {k: self.governing(k) for k in ('skeleton', 'arc')},
            'directions': directions,
            'style_sheet': self.style_sheet(),
            'style_versions': self.style_sheet_versions(),
            'secrets': self.secrets(),
            'extractions': [{k: r[k] for k in ('revision_id', 'mode', 'outcome', 'returned', 'anchored_exact', 'anchored_loose', 'anchored_ambiguous', 'duplicates', 'quarantined')}
                            for r in self.extraction_receipts()],
            'episodes': episodes,
            'canon': canon,
            'candidates': [dict(r) for r in self.connection.execute(
                "SELECT w.candidate_id, a.ordinal, w.block_id, w.base_revision_id, w.replacement, w.intent, w.reason FROM v1_rewrite w JOIN v1_artifact a USING(artifact_id) WHERE w.disposition='open' ORDER BY w.rowid")],
            'commissions': [{**dict(r), 'pause_detail': self._pause_detail(dict(r))}
                            for r in self.connection.execute('SELECT * FROM v1_commission ORDER BY rowid')],
            'acceptances': [{'acceptance_id': r['acceptance_id'], 'canon_seq': r['new_seq'], 'warnings': json.loads(r['warnings'])}
                            for r in self.connection.execute('SELECT * FROM v1_acceptance ORDER BY new_seq')],
            'history': history,
            'memory': self.memory(),
            'uncertain': self.uncertain_jobs(),
            'word_band': list(self.word_band()),
            'word_limit': hard_limit(self.word_band()[2]),
            'length': self.length_setting(),
        }

    # ---- voice notes ----------------------------------------------------
    def propose_style(self, note: str, *, evidence: list[dict[str, Any]]) -> str:
        if not evidence:
            raise Refused('invalid_evidence', 'Choose at least one piece of evidence.')
        rows = []
        for item in evidence:
            if item.get('kind') == 'human_edit':
                event = self._one("SELECT * FROM v1_event WHERE event_id=? AND actor='author' AND action='save'", item.get('event_id'))
                if event is None:
                    raise Refused('invalid_evidence', 'A human edit must be one of your own saves.')
                before = '\n\n'.join(i['text'] or '' for i in json.loads(event['before_images']))
                after = '\n\n'.join(i['text'] or '' for i in json.loads(event['after_images']))
                rows.append(('human_edit', event['event_id'], None, before, after))
            elif item.get('kind') == 'explicit_feedback':
                message = self._one("SELECT * FROM v1_message WHERE message_id=? AND sender='author'", item.get('message_id'))
                if message is None:
                    raise Refused('invalid_evidence', 'Feedback evidence must be your own message.')
                rows.append(('explicit_feedback', None, message['message_id'], '', message['content']))
            else:
                raise Refused('invalid_evidence', 'Only your own edits or explicit feedback can teach a voice note.')
        style_id = new_id('st')
        with self.transaction():
            self.connection.execute("INSERT INTO v1_style VALUES(?,?,'proposed',0)", (style_id, note))
            for position, (kind, event_id, message_id, before, after) in enumerate(rows):
                self.connection.execute("INSERT INTO v1_style_evidence VALUES(?,?,?,?,?,?,?,'active')",
                                        (style_id, position, kind, event_id, message_id, before, after))
        return style_id

    def style(self, style_id: str) -> dict[str, Any]:
        row = dict(self._one('SELECT * FROM v1_style WHERE style_id=?', style_id))
        row['evidence'] = [dict(r) for r in self.connection.execute('SELECT * FROM v1_style_evidence WHERE style_id=? ORDER BY position', (style_id,))]
        return row

    def adopt_style(self, style_id: str) -> None:
        with self.transaction():
            if self.connection.execute("UPDATE v1_style SET status='adopted', needs_reaffirm=0 WHERE style_id=? AND status IN ('proposed','adopted')", (style_id,)).rowcount != 1:
                raise Refused('not_found', 'Only a proposed note can be adopted.')
            self._event('style_adopt', payload={'style_id': style_id})
