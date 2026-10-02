"""V1 writing desk: authority, linked drafts, block rewrites, undo, acceptance, memory.

Contract: docs/v1/01-04. Opening a story never runs DDL; only `Desk.create`
(the explicit migration) does. Every provider exchange happens outside any
SQLite transaction; results are always stored and eligibility is decided after.
"""
import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from ..records import StoryError
from .provider import GenerationProvider, GenerationRequest, ProviderUnavailable

SCHEMA_VERSION = 'v1_0001'

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
  standing TEXT NOT NULL CHECK(standing IN ('provisional_selected','accepted_derived','superseded')),
  prior_claim_id TEXT, note TEXT NOT NULL DEFAULT '');
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
CREATE INDEX v1_claim_scope ON v1_claim(narrative_ordinal, standing);
"""


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
# A commission draft over the maximum is kept whole but not selected automatically.
WORD_BAND = (550, 700, 900)


def length_warning(ordinal: int, words: int) -> dict[str, Any] | None:
    low, _, high = WORD_BAND
    if low <= words <= high:
        return None
    return {'ordinal': ordinal, 'words': words, 'band': list(WORD_BAND)}


def draft_prompt(*, ordinal: int, spine: str, purpose: str, intention: str,
                 predecessors: list[tuple[int, str]], voice_notes: list[str]) -> str:
    """The `sequential_draft` contract. Output rules come last so that predecessor
    prose, which can be thousands of characters, is never the final thing read."""
    low, target, high = WORD_BAND
    if predecessors:
        data = ['Earlier episodes, in story order. This is canon to stay consistent with, not a template to copy form '
                'from, and it ranks below the spine and arc. Keep its facts, names and events; ignore its layout.']
        for n, text in predecessors:
            data.append(f'[Episode {n} begins]\n{text}\n[Episode {n} ends]')
    else:
        data = ['None yet. This is the first episode.']
    voice = ["Apply these only where they do not conflict with anything above; they never override the spine, "
             "the arc or this episode's job."] + [f'- {note}' for note in voice_notes] if voice_notes else ['None adopted.']
    sections = [
        f'You are writing episode {ordinal} of a serial story. Write that one episode as narrative prose and nothing else.',
        'PRECEDENCE\nThe spine and arc outrank the established story data and the voice notes. '
        'If sections conflict, follow this order: 1. the governing spine, 2. the arc purpose, '
        "3. this episode's job, 4. the established story data, 5. the adopted voice notes.",
        f"AUTHOR'S GOVERNING SPINE (do not restate)\n{spine}",
        f'ARC PURPOSE\n{purpose}',
        f"THIS EPISODE'S JOB (episode {ordinal})\n{intention}",
        'ESTABLISHED STORY DATA (reference only; do not imitate its formatting)\n' + '\n\n'.join(data),
        'ADOPTED VOICE NOTES (lower priority than the spine and arc)\n' + '\n'.join(voice),
        '\n'.join([
            'OUTPUT RULES',
            f'- Form: continuous narrative prose for episode {ordinal} only. No headings, no markdown, no screenplay '
            'or script format, no stage directions, no speaker labels, no sound cues, no episode title or preamble, '
            'no notes or commentary. Dialogue sits inside the prose in quotation marks.',
            f'- Length: aim for {target} words; stay within {low} to {high} words. '
            f'Running past {high} words is worse than running short.',
            '- Characters: Do not introduce a named character who does not already appear in the established story data '
            'or the direction above. When the established story data names a person, use that exact name. '
            'Unnamed minor figures are allowed.',
            '- Ending: end on a turn (a decision, a discovery, a reversal), not a summary or a moral.',
            '- Return the episode text only.',
        ]),
    ]
    return '\n\n'.join(sections)


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
        with self.transaction():
            artifact_id = self._artifact(layer)
            head = self._one('SELECT revision_id FROM v1_revision WHERE artifact_id=? ORDER BY seq DESC LIMIT 1', artifact_id)
            revision_id = self._insert_revision(artifact_id, json.dumps(content, sort_keys=True), origin=origin,
                                                parent_id=head['revision_id'] if head else None)
            self._event('save', artifact_id=artifact_id, after=revision_id)
        return revision_id

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
            if current is None:
                self.connection.execute('INSERT INTO v1_governing VALUES(?,?,1)', (row['kind'], revision_id))
            else:
                self.connection.execute('UPDATE v1_governing SET revision_id=?, cas=cas+1 WHERE scope_kind=?', (revision_id, row['kind']))
            if row['kind'] == 'arc':
                for ordinal, _ in enumerate(json.loads(row['content'])['intentions'], 1):
                    self._artifact('episode', ordinal)
            return self._event('adopt', artifact_id=row['kind'], before=current_id, after=revision_id)

    def converse(self, *, target: str, text: str) -> dict[str, str]:
        """Conversation is stored and answered; it never moves a pointer."""
        with self.transaction():
            seq = self._one('SELECT coalesce(max(seq),0)+1 FROM v1_message')[0]
            asked = new_id('msg')
            self.connection.execute('INSERT INTO v1_message VALUES(?,?,?,?,?)', (asked, seq, target, 'author', text))
        reply = self.provider.generate(GenerationRequest('converse', text, key=sha(target + text))).text
        with self.transaction():
            answered = new_id('msg')
            self.connection.execute('INSERT INTO v1_message VALUES(?,?,?,?,?)', (answered, seq + 1, target, 'assistant', reply))
        return {'question': asked, 'reply': answered, 'text': reply}

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
        prompt = draft_prompt(
            ordinal=ordinal, spine=skeleton['content']['spine'], purpose=arc['content']['purpose'],
            intention=arc['content']['intentions'][ordinal - 1],
            predecessors=[(n, self.revision(revision_id)['text']) for n, (revision_id, _) in enumerate(basis, 1)],
            voice_notes=[r['note'] for r in self.connection.execute("SELECT note FROM v1_style WHERE status='adopted' ORDER BY style_id")])
        sel = self._one('SELECT cas FROM v1_selection WHERE artifact_id=?', artifact_id)
        job_id = new_id('job')
        frozen_basis = {'skeleton': skeleton['revision_id'], 'arc': arc['revision_id'], 'predecessors': basis}
        self.connection.execute('INSERT INTO v1_job VALUES(?,?,?,?,?,?,?,?,?)',
                                (job_id, 'sequential_draft', commission_id, artifact_id, sha(prompt), prompt,
                                 sel['cas'] if sel else 0, json.dumps(frozen_basis), 'frozen'))
        for position, (revision_id, digest) in enumerate(basis):
            self.connection.execute('INSERT INTO v1_predecessor VALUES(?,?,?,?)', (job_id, position, revision_id, digest))
        return job_id

    def _basis_current(self, job: sqlite3.Row, ordinal: int) -> str | None:
        frozen = json.loads(job['basis'])
        if self.governing('skeleton')['revision_id'] != frozen['skeleton'] or self.governing('arc')['revision_id'] != frozen['arc']:
            return 'direction_changed'
        if [list(p) for p in (self._predecessor_basis(ordinal) or [])] != frozen['predecessors']:
            return 'predecessor_changed'
        sel = self._one('SELECT cas FROM v1_selection WHERE artifact_id=?', job['target_artifact_id'])
        if (sel['cas'] if sel else 0) != job['frozen_selection_cas']:
            return 'selection_changed'
        return None

    def commission_arc(self, *, slots: tuple[int, int], progression: str = 'provisional_chain') -> dict[str, Any]:
        if self.governing('skeleton') is None or self.governing('arc') is None:
            raise Refused('direction_missing', 'Adopt a skeleton and an arc before drafting through the arc.')
        first, last = slots
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
            done = self._one("SELECT 1 FROM v1_job j JOIN v1_result r USING(job_id) WHERE j.commission_id=? AND j.target_artifact_id=? AND r.eligibility='selected' AND r.output_revision_id=(SELECT revision_id FROM v1_selection WHERE artifact_id=?)",
                             commission_id, artifact_id, artifact_id)
            if done and self._one("SELECT 1 FROM v1_impact WHERE artifact_id=? AND state='open'", artifact_id) is None:
                if self._basis_current(self._one("SELECT j.* FROM v1_job j JOIN v1_result r USING(job_id) WHERE r.output_revision_id=(SELECT revision_id FROM v1_selection WHERE artifact_id=?)", artifact_id), ordinal) is None:
                    continue
            if self._one('SELECT 1 FROM v1_canon WHERE ordinal=?', ordinal):
                continue
            with self.transaction():
                blocked = self._blocking_reason(ordinal - 1)
                if blocked:
                    self._pause(commission_id, blocked[0])
                    return self.commission(commission_id)
                job_id = self._freeze_draft(commission_id, ordinal)
                if job_id is None:
                    self._pause(commission_id, 'waiting_predecessor')
                    return self.commission(commission_id)
                self._event('job_frozen', actor=actor, artifact_id=artifact_id, payload={'job_id': job_id})
                self.connection.execute("UPDATE v1_job SET state='sent' WHERE job_id=?", (job_id,))
            job = self._one('SELECT * FROM v1_job WHERE job_id=?', job_id)
            # Exchange: no transaction is open here, so other writers may proceed.
            request = GenerationRequest('sequential_draft', job['prompt'], key=job['request_sha256'], params={'ordinal': ordinal})
            try:
                result = self.provider.generate(request)
            except ProviderUnavailable:
                with self.transaction():
                    self.connection.execute("UPDATE v1_job SET state='uncertain' WHERE job_id=?", (job_id,))
                    self._pause(commission_id, 'accounting_uncertain')
                return self.commission(commission_id)
            with self.transaction():
                output = self._insert_revision(artifact_id, result.text, origin='generated', job_id=job_id, reason='commission draft')
                self.connection.execute("UPDATE v1_job SET state='imported' WHERE job_id=?", (job_id,))
                status = self._one('SELECT status FROM v1_commission WHERE commission_id=?', commission_id)['status']
                changed = self._basis_current(job, ordinal) or (None if status == 'running' else 'commission_' + status)
                over_length = len(result.text.split()) > WORD_BAND[2]
                if changed is None and not over_length and row['progression'] == 'provisional_chain':
                    prior = self._one('SELECT revision_id FROM v1_selection WHERE artifact_id=?', artifact_id)
                    event_id = self._event('select', actor=actor, artifact_id=artifact_id,
                                           before=prior['revision_id'] if prior else None, after=output)
                    self._set_selection(artifact_id, output, by='commission', event_id=event_id)
                    self.connection.execute('INSERT INTO v1_result VALUES(?,?,?,NULL)', (job_id, output, 'selected'))
                    self.connection.execute("UPDATE v1_impact SET state='superseded' WHERE artifact_id=? AND state='open'", (artifact_id,))
                else:
                    reason = changed or ('over_length' if over_length else 'review_each')
                    self.connection.execute('INSERT INTO v1_result VALUES(?,?,?,?)', (job_id, output, 'detached', reason))
                    self._event('result_detached', actor=actor, artifact_id=artifact_id, after=output, payload={'reason': reason})
                    if changed:
                        self._pause(commission_id, 'basis_changed')
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
                                                              variant=variant, params={'ordinal': ordinal}))
        except ProviderUnavailable:
            with self.transaction():
                self.connection.execute("UPDATE v1_job SET state='uncertain' WHERE job_id=?", (job_id,))
            raise Refused('accounting_uncertain', 'The request has no verified outcome. It will not be retried.')
        with self.transaction():
            output = self._insert_revision(artifact_id, result.text, origin='generated', job_id=job_id, reason='requested alternative')
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
            """SELECT DISTINCT a.ordinal, a.artifact_id FROM v1_selection s JOIN v1_artifact a USING(artifact_id)
               WHERE a.ordinal > ? AND (
                 EXISTS (SELECT 1 FROM v1_revision r JOIN v1_predecessor p ON p.job_id=r.job_id
                         WHERE r.revision_id=s.revision_id AND p.revision_id=?)
                 OR EXISTS (SELECT 1 FROM v1_impact i WHERE i.artifact_id=a.artifact_id AND i.upstream_artifact_id=? AND i.upstream_revision_id=?))
               ORDER BY a.ordinal""", (ordinal, revision_id, artifact_id, revision_id))
        return [(r['ordinal'], r['artifact_id']) for r in rows]

    def impact_preview(self, ordinal: int) -> list[int]:
        sel = self.selection(ordinal)
        return [] if sel is None else [n for n, _ in self._downstream(sel['artifact_id'], sel['revision_id'])]

    def _save(self, artifact_id: str, base_revision_id: str, blocks: list[tuple[str | None, str]], *, expected_cas: int,
              action: str, actor: str = 'author', revert_of: str | None = None, payload: dict | None = None) -> dict[str, Any]:
        sel = self._one('SELECT * FROM v1_selection WHERE artifact_id=?', artifact_id)
        if sel is None or sel['cas'] != expected_cas or sel['revision_id'] != base_revision_id:
            raise Refused('stale_pointer', 'This episode changed since you opened it. Compare before saving.',
                          current=None if sel is None else sel['revision_id'])
        if self._one("SELECT 1 FROM v1_canon WHERE artifact_id=?", artifact_id):
            raise Refused('accepted', 'Accepted text changes only through a staged change set.')
        base = {b['block_id']: b for b in self.revision(base_revision_id)['blocks']}
        seen, final, before_images, after_images = set(), [], [], []
        for block_id, text in blocks:
            if block_id is not None and (block_id not in base or block_id in seen):
                raise Refused('ambiguous_block', 'A submitted block does not belong to the base revision.')
            block_id = block_id or new_id('b')
            seen.add(block_id)
            final.append((block_id, text))
            prior = base.get(block_id)
            if prior is None or prior['text'] != text:
                before_images.append({'block_id': block_id, 'text': None if prior is None else prior['text']})
                after_images.append({'block_id': block_id, 'text': text})
        for block_id, prior in base.items():
            if block_id not in seen:
                before_images.append({'block_id': block_id, 'text': prior['text']})
                after_images.append({'block_id': block_id, 'text': None})
        revision_id = self._insert_revision(artifact_id, '', origin='human', parent_id=base_revision_id, blocks=final, reason=action)
        event_id = self._event(action, actor=actor, artifact_id=artifact_id, before=base_revision_id, after=revision_id,
                               before_images=before_images, after_images=after_images, revert_of=revert_of, payload=payload)
        self._set_selection(artifact_id, revision_id, by='author', event_id=event_id)
        flagged = []
        for ordinal, downstream in self._downstream(artifact_id, base_revision_id):
            self.connection.execute('INSERT INTO v1_impact VALUES(?,?,?,?,?,?)',
                                    (new_id('im'), downstream, artifact_id, revision_id, event_id, 'open'))
            flagged.append(ordinal)
        for row in self.connection.execute("SELECT commission_id FROM v1_commission WHERE status='running'").fetchall():
            if flagged:
                self._pause(row['commission_id'], 'basis_changed')
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
        target = {i['block_id']: i['text'] for i in json.loads(event[restore])}
        sel = self._one('SELECT * FROM v1_selection WHERE artifact_id=?', event['artifact_id'])
        current = self.revision(sel['revision_id'])['blocks']
        present = {b['block_id']: b['text'] for b in current}
        for block_id, text in images.items():
            if present.get(block_id) != text:
                raise Refused('overlap', 'That passage changed since; undo would overwrite newer words.',
                              block_id=block_id, now=present.get(block_id), expected=text)
        blocks = [(b['block_id'], target.get(b['block_id'], b['text'])) for b in current if target.get(b['block_id'], b['text']) is not None]
        blocks += [(None, t) for bid, t in target.items() if bid not in present and t is not None]
        return self._save(event['artifact_id'], sel['revision_id'], blocks, expected_cas=sel['cas'], action=action, revert_of=revert_of)

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
                job = self._one('SELECT job_id FROM v1_revision WHERE revision_id=?', revision_id)['job_id']
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
    def _import_claims(self, revision_id: str, ordinal: int, standing: str) -> int:
        blocks = self.revision(revision_id)['blocks']
        raw = self.provider.generate(GenerationRequest('promotion', revision_id, key=revision_id,
                                                       params={'blocks': [{'block_id': b['block_id'], 'text': b['text']} for b in blocks]})).text
        by_id = {b['block_id']: b['text'] for b in blocks}
        imported = 0
        with self.transaction():
            for claim in json.loads(raw):
                text = by_id.get(claim.get('block_id'))
                start, end = claim.get('start'), claim.get('end')
                if (text is None or type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text)
                        or text[start:end] != claim.get('quote') or (claim.get('kind') == 'testimony' and not claim.get('speaker'))):
                    continue
                self.connection.execute(
                    'INSERT INTO v1_claim(claim_id,kind,subject,speaker,holder,stance,world_validity,narrative_ordinal,revision_id,block_id,start,"end",quote,standing) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    (new_id('cl'), claim['kind'], claim.get('subject', ''), claim.get('speaker'), claim.get('holder'),
                     claim.get('stance', 'asserts'), claim.get('world_validity', 'unknown'), ordinal, revision_id,
                     claim['block_id'], start, end, claim['quote'], standing))
                imported += 1
        return imported

    def read_provisional(self, ordinal: int) -> int:
        sel = self.selection(ordinal)
        if sel is None:
            raise Refused('not_found', 'No selected draft to read.')
        return self._import_claims(sel['revision_id'], ordinal, 'provisional_selected')

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
            self._import_claims(canon['revision_id'], canon['ordinal'], 'accepted_derived')
            with self.transaction():
                self.connection.execute("UPDATE v1_outbox SET state='imported' WHERE task_id=?", (task['task_id'],))
            counts['imported'] += 1
        return counts

    def memory(self, *, boundary: int | None = None) -> dict[str, list[dict[str, Any]]]:
        limit = boundary if boundary is not None else 10**9
        accepted = [dict(r) for r in self.connection.execute(
            "SELECT c.* FROM v1_claim c JOIN v1_canon k ON k.revision_id=c.revision_id WHERE c.standing='accepted_derived' AND c.narrative_ordinal<=? ORDER BY c.narrative_ordinal, c.block_id, c.start", (limit,))]
        provisional = [dict(r) for r in self.connection.execute(
            "SELECT c.* FROM v1_claim c JOIN v1_selection s ON s.revision_id=c.revision_id WHERE c.standing='provisional_selected' AND c.narrative_ordinal<=? AND c.revision_id NOT IN (SELECT revision_id FROM v1_canon) ORDER BY c.narrative_ordinal", (limit,))]
        return {'accepted': accepted, 'provisional': provisional}

    def interpret(self, claim_id: str, *, kind: str, speaker: str | None, world_validity: str, note: str, holder: str | None = None) -> str:
        """A correction is a new claim revision that supersedes, never erases, the old one."""
        if kind == 'testimony' and not speaker:
            raise Refused('invalid_claim', 'Testimony needs a speaker.')
        with self.transaction():
            old = self._one("SELECT * FROM v1_claim WHERE claim_id=?", claim_id)
            if old is None or old['standing'] == 'superseded':
                raise Refused('stale_pointer', 'This reading was already corrected.')
            new = new_id('cl')
            self.connection.execute(
                'INSERT INTO v1_claim(claim_id,kind,subject,speaker,holder,stance,world_validity,narrative_ordinal,revision_id,block_id,start,"end",quote,standing,prior_claim_id,note) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (new, kind, old['subject'], speaker, holder, old['stance'], world_validity, old['narrative_ordinal'],
                 old['revision_id'], old['block_id'], old['start'], old['end'], old['quote'], old['standing'], claim_id, note))
            self.connection.execute("UPDATE v1_claim SET standing='superseded' WHERE claim_id=?", (claim_id,))
            self._event('interpret', payload={'claim_id': new, 'supersedes': claim_id})
        return new

    def claim_history(self, claim_id: str) -> list[dict[str, Any]]:
        chain, current = [], claim_id
        while current:
            row = self._one('SELECT * FROM v1_claim WHERE claim_id=?', current)
            chain.append(dict(row))
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
    def snapshot(self, *, history_limit: int = 40) -> dict[str, Any]:
        meta = self._one('SELECT story_id, canon_seq FROM v1_meta WHERE id=1')
        canon = self.canon()
        accepted = {r['ordinal'] for r in canon}
        episodes = []
        for artifact in self.artifacts('episode'):
            n, artifact_id = artifact['ordinal'], artifact['artifact_id']
            sel = self.selection(n)
            entry = {'ordinal': n, 'artifact_id': artifact_id, 'selection': sel, 'accepted': n in accepted,
                     'text': None, 'blocks': [], 'words': 0, 'length_warning': None, 'predecessors': [],
                     'open_impacts': self._one("SELECT count(*) FROM v1_impact WHERE artifact_id=? AND state='open'", artifact_id)[0],
                     'alternatives': [dict(r) for r in self.connection.execute(
                         "SELECT r.output_revision_id AS revision_id, r.detached_reason FROM v1_result r JOIN v1_job j USING(job_id) WHERE j.target_artifact_id=? AND r.eligibility='detached' ORDER BY j.rowid", (artifact_id,))]}
            if sel:
                revision = self.revision(sel['revision_id'])
                words = len(revision['text'].split())
                entry.update(text=revision['text'], blocks=revision['blocks'], words=words, length_warning=length_warning(n, words))
                if revision['job_id']:
                    entry['predecessors'] = [[r['revision_id'], r['sha256']] for r in self.connection.execute(
                        'SELECT revision_id, sha256 FROM v1_predecessor WHERE job_id=? ORDER BY position', (revision['job_id'],))]
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
            'episodes': episodes,
            'canon': canon,
            'candidates': [dict(r) for r in self.connection.execute(
                "SELECT w.candidate_id, a.ordinal, w.block_id, w.base_revision_id, w.replacement, w.intent, w.reason FROM v1_rewrite w JOIN v1_artifact a USING(artifact_id) WHERE w.disposition='open' ORDER BY w.rowid")],
            'commissions': [dict(r) for r in self.connection.execute('SELECT * FROM v1_commission ORDER BY rowid')],
            'acceptances': [{'acceptance_id': r['acceptance_id'], 'canon_seq': r['new_seq'], 'warnings': json.loads(r['warnings'])}
                            for r in self.connection.execute('SELECT * FROM v1_acceptance ORDER BY new_seq')],
            'history': history,
            'memory': self.memory(),
            'uncertain': self.uncertain_jobs(),
            'word_band': list(WORD_BAND),
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
