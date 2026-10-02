"""Human-confirmed story memory. Quotes prove provenance, not semantic truth."""
from dataclasses import asdict, dataclass
import json
import sqlite3
from typing import Any, Literal

from .records import StoryError
from .repository import SQLiteRepository


@dataclass(frozen=True)
class Entity:
    id: int
    name: str
    kind: Literal['character', 'location']
    role: str


@dataclass(frozen=True)
class Fact:
    id: int
    subject_id: int
    predicate: str
    value: str
    source_revision_id: int
    evidence: str
    evidence_start: int
    evidence_end: int
    status: Literal['proposed', 'confirmed', 'rejected']
    supersedes: int | None
    superseded_by: int | None
    object_id: int | None
    situation_id: int | None


@dataclass(frozen=True)
class Situation:
    id: int
    title: str
    source_revision_id: int
    evidence: str
    evidence_start: int
    evidence_end: int


@dataclass(frozen=True)
class Direction:
    id: int
    key: str
    text: str
    start_episode: int
    end_episode: int
    subject_id: int | None
    status: Literal['active', 'retired']


MEMORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS memory_meta(id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL DEFAULT 0);
INSERT OR IGNORE INTO memory_meta(id) VALUES(1);
CREATE TABLE IF NOT EXISTS entities(
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, identity TEXT NOT NULL UNIQUE,
 kind TEXT NOT NULL CHECK(kind IN ('character','location')), role TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS facts(
 id INTEGER PRIMARY KEY, subject_id INTEGER NOT NULL REFERENCES entities(id),
 predicate TEXT NOT NULL, value TEXT NOT NULL,
 source_revision_id INTEGER NOT NULL REFERENCES episodes(id),
 evidence TEXT NOT NULL, evidence_start INTEGER NOT NULL, evidence_end INTEGER NOT NULL,
 status TEXT NOT NULL DEFAULT 'proposed' CHECK(status IN ('proposed','confirmed','rejected')),
 supersedes INTEGER REFERENCES facts(id), superseded_by INTEGER REFERENCES facts(id),
 object_id INTEGER REFERENCES entities(id), situation_id INTEGER,
 identity TEXT NOT NULL UNIQUE);
CREATE INDEX IF NOT EXISTS facts_subject ON facts(subject_id,predicate,status);
CREATE INDEX IF NOT EXISTS facts_source ON facts(source_revision_id);
CREATE UNIQUE INDEX IF NOT EXISTS one_current_fact ON facts(subject_id,predicate)
 WHERE status='confirmed' AND superseded_by IS NULL;
CREATE TABLE IF NOT EXISTS situations(
 id INTEGER PRIMARY KEY, title TEXT NOT NULL,
 source_revision_id INTEGER NOT NULL REFERENCES episodes(id),
 evidence TEXT NOT NULL, evidence_start INTEGER NOT NULL, evidence_end INTEGER NOT NULL,
 identity TEXT NOT NULL UNIQUE);
CREATE TRIGGER IF NOT EXISTS facts_situation_guard BEFORE INSERT ON facts
 WHEN NEW.situation_id IS NOT NULL AND NOT EXISTS(
 SELECT 1 FROM situations WHERE id=NEW.situation_id AND source_revision_id=NEW.source_revision_id)
 BEGIN SELECT RAISE(ABORT,'Situation and fact must share an accepted episode source'); END;
CREATE TABLE IF NOT EXISTS directions(
 id INTEGER PRIMARY KEY, key TEXT NOT NULL, text TEXT NOT NULL,
 start_episode INTEGER NOT NULL CHECK(start_episode BETWEEN 1 AND 200),
 end_episode INTEGER NOT NULL CHECK(end_episode BETWEEN start_episode AND 200),
 subject_id INTEGER REFERENCES entities(id),
 status TEXT NOT NULL CHECK(status IN ('active','retired')));
CREATE UNIQUE INDEX IF NOT EXISTS one_active_direction ON directions(key) WHERE status='active';
"""


class SQLiteMemory:
    def __init__(self, repository: SQLiteRepository):
        self.repo = repository
        self.connection = repository.connection
        self.connection.executescript(MEMORY_SCHEMA)

    def revision(self) -> int:
        return self.connection.execute('SELECT revision FROM memory_meta WHERE id=1').fetchone()[0]

    def _changed(self) -> None:
        self.connection.execute('UPDATE memory_meta SET revision=revision+1 WHERE id=1')

    @staticmethod
    def _text(value: str, limit: int = 2000) -> str:
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise StoryError('Supply non-empty text within the documented length limit.')
        return value.strip()

    def entity(self, entity_id: int) -> Entity:
        row = self.connection.execute('SELECT id,name,kind,role FROM entities WHERE id=?', (entity_id,)).fetchone()
        if row is None:
            raise StoryError('Register this character or location first.')
        return Entity(**dict(row))

    def entities(self) -> list[Entity]:
        return [Entity(**dict(r)) for r in self.connection.execute('SELECT id,name,kind,role FROM entities ORDER BY id')]

    def add_entity(self, name: str, kind: str, role: str = '') -> Entity:
        name = self._text(name, 128)
        if kind not in ('character', 'location') or (kind == 'character' and role not in ('protagonist', 'core', 'supporting')) or (kind == 'location' and role):
            raise StoryError('Use a character role or register a location without a role.')
        identity = json.dumps([kind, name.casefold()])
        with self.repo.transaction():
            self.repo.story()
            existing = self.connection.execute('SELECT id,role FROM entities WHERE identity=?', (identity,)).fetchone()
            if existing:
                if existing['role'] != role:
                    raise StoryError('This entity already has another role; do not silently overwrite it.')
                return self.entity(existing['id'])
            if kind == 'character':
                counts = self.connection.execute("SELECT count(*) AS total, sum(role IN ('protagonist','core')) AS major, sum(role='protagonist') AS heroes FROM entities WHERE kind='character'").fetchone()
                if counts['total'] >= 30:
                    raise StoryError('The story already has 30 characters. Discuss the cast before adding more.')
                if role in ('protagonist', 'core') and (counts['major'] or 0) >= 10:
                    raise StoryError('The story already has 10 major characters, including the protagonist.')
                if role == 'protagonist' and (counts['heroes'] or 0):
                    raise StoryError('A protagonist is already registered.')
            cursor = self.connection.execute('INSERT INTO entities(name,identity,kind,role) VALUES(?,?,?,?)', (name, identity, kind, role))
            self._changed()
            return self.entity(cursor.lastrowid)

    def _source(self, revision_id: int, evidence: str) -> tuple[int, int]:
        row = self.connection.execute("SELECT accepted_text FROM episodes WHERE id=? AND status='accepted'", (revision_id,)).fetchone()
        if row is None:
            raise StoryError('Facts require a human-accepted episode revision, not a draft or rejection.')
        evidence = self._text(evidence)
        text = row['accepted_text']
        start = text.find(evidence)
        if start < 0 or text.find(evidence, start + 1) >= 0:
            raise StoryError('Evidence must be an exact, unambiguous passage of accepted prose. Use a longer quote.')
        return start, start + len(evidence)

    @staticmethod
    def _fact(row: sqlite3.Row) -> Fact:
        return Fact(**{field: row[field] for field in Fact.__dataclass_fields__})

    def fact(self, fact_id: int) -> Fact:
        row = self.connection.execute('SELECT * FROM facts WHERE id=?', (fact_id,)).fetchone()
        if row is None:
            raise StoryError('Read a fact proposal and use its ID.')
        return self._fact(row)

    def propose_fact(self, subject_id: int, predicate: str, value: str, source_revision_id: int, evidence: str,
                     object_id: int | None = None, situation_id: int | None = None) -> Fact:
        predicate, value, evidence = self._text(predicate, 128), self._text(value), self._text(evidence)
        with self.repo.transaction():
            self.entity(subject_id)
            if object_id is not None:
                self.entity(object_id)
            if situation_id is not None and self.situation(situation_id).source_revision_id != source_revision_id:
                raise StoryError('A fact and its situation must refer to the same accepted episode.')
            start, end = self._source(source_revision_id, evidence)
            identity = json.dumps([subject_id, predicate, value, source_revision_id, start, end, object_id, situation_id])
            self.connection.execute('INSERT OR IGNORE INTO facts(subject_id,predicate,value,source_revision_id,evidence,evidence_start,evidence_end,object_id,situation_id,identity) VALUES(?,?,?,?,?,?,?,?,?,?)', (subject_id, predicate, value, source_revision_id, evidence, start, end, object_id, situation_id, identity))
            row = self.connection.execute('SELECT * FROM facts WHERE identity=?', (identity,)).fetchone()
            return self._fact(row)

    def confirm_fact(self, fact_id: int, supersedes: int | None = None) -> Fact:
        with self.repo.transaction():
            fact = self.fact(fact_id)
            if fact.status == 'confirmed':
                if supersedes is not None and supersedes != fact.supersedes:
                    raise StoryError('This fact was confirmed with a different replacement.')
                return fact
            if fact.status != 'proposed':
                raise StoryError('A rejected fact cannot be confirmed.')
            self._source(fact.source_revision_id, fact.evidence)
            current = self.connection.execute("SELECT * FROM facts WHERE subject_id=? AND predicate=? AND status='confirmed' AND superseded_by IS NULL", (fact.subject_id, fact.predicate)).fetchone()
            if current:
                if supersedes != current['id']:
                    raise StoryError('This property already has a current fact. Explicitly replace its ID or use a different property.')
                old_number = self.connection.execute('SELECT number FROM episodes WHERE id=?', (current['source_revision_id'],)).fetchone()[0]
                new_number = self.connection.execute('SELECT number FROM episodes WHERE id=?', (fact.source_revision_id,)).fetchone()[0]
                if (new_number, fact.evidence_start) <= (old_number, current['evidence_start']):
                    raise StoryError('Earlier evidence cannot replace later history. Historical repair is a separate workflow.')
                self.connection.execute('UPDATE facts SET superseded_by=? WHERE id=?', (fact_id, supersedes))
            elif supersedes is not None:
                raise StoryError('There is no matching current fact to replace.')
            self.connection.execute("UPDATE facts SET status='confirmed',supersedes=? WHERE id=?", (supersedes, fact_id))
            self.connection.execute("INSERT INTO reviews(target_kind,target_id,decision) VALUES('fact',?,'confirmed')", (fact_id,))
            self._changed()
            return self.fact(fact_id)

    def reject_fact(self, fact_id: int, note: str = '') -> Fact:
        if len(note) > 2000:
            raise StoryError('Shorten the review note to 2000 characters.')
        with self.repo.transaction():
            fact = self.fact(fact_id)
            if fact.status == 'rejected':
                return fact
            if fact.status != 'proposed':
                raise StoryError('Only a proposal can be rejected. Confirmed history requires an explicit replacement.')
            self.connection.execute("UPDATE facts SET status='rejected' WHERE id=?", (fact_id,))
            self.connection.execute("INSERT INTO reviews(target_kind,target_id,decision,note) VALUES('fact',?,'rejected',?)", (fact_id, note))
            return self.fact(fact_id)

    def query_facts(self, subject_id: int | None = None, current_only: bool = True, search: str = '') -> list[Fact]:
        # Values are bound, never assembled into SQL. Each property is a single-value slot.
        rows = self.connection.execute("SELECT * FROM facts WHERE status='confirmed' AND (?=0 OR superseded_by IS NULL) AND (? IS NULL OR subject_id=? OR object_id=?) AND instr(lower(predicate || ' ' || value || ' ' || evidence),lower(?))>0 ORDER BY source_revision_id,evidence_start,id", (int(current_only), subject_id, subject_id, subject_id, search))
        return [self._fact(r) for r in rows]

    def situation(self, situation_id: int) -> Situation:
        row = self.connection.execute('SELECT * FROM situations WHERE id=?', (situation_id,)).fetchone()
        if row is None:
            raise StoryError('Read a situation and use its ID.')
        return Situation(**{field: row[field] for field in Situation.__dataclass_fields__})

    def add_situation(self, title: str, source_revision_id: int, evidence: str) -> Situation:
        title, evidence = self._text(title, 200), self._text(evidence)
        with self.repo.transaction():
            start, end = self._source(source_revision_id, evidence)
            identity = json.dumps([title, source_revision_id, start, end])
            existing = self.connection.execute('SELECT id FROM situations WHERE identity=?', (identity,)).fetchone()
            if existing:
                return self.situation(existing['id'])
            cursor = self.connection.execute('INSERT INTO situations(title,source_revision_id,evidence,evidence_start,evidence_end,identity) VALUES(?,?,?,?,?,?)', (title, source_revision_id, evidence, start, end, identity))
            self._changed()
            return self.situation(cursor.lastrowid)

    def set_direction(self, key: str, text: str, start_episode: int | None = None,
                      end_episode: int = 200, subject_id: int | None = None) -> Direction:
        key, text = self._text(key, 128), self._text(text)
        with self.repo.transaction():
            next_episode = self.repo.story()['next_episode']
            start = next_episode if start_episode is None else start_episode
            if not next_episode <= start <= end_episode <= 200:
                raise StoryError('Directions concern eligible future episodes, not already accepted history.')
            if subject_id is not None:
                self.entity(subject_id)
            current = self.connection.execute("SELECT * FROM directions WHERE key=? AND status='active'", (key,)).fetchone()
            if current and (current['text'],current['start_episode'],current['end_episode'],current['subject_id']) == (text,start,end_episode,subject_id):
                return Direction(**dict(current))
            self.connection.execute("UPDATE directions SET status='retired' WHERE key=? AND status='active'", (key,))
            cursor = self.connection.execute("INSERT INTO directions(key,text,start_episode,end_episode,subject_id,status) VALUES(?,?,?,?,?,'active')", (key,text,start,end_episode,subject_id))
            self._changed()
            return Direction(**dict(self.connection.execute('SELECT * FROM directions WHERE id=?', (cursor.lastrowid,)).fetchone()))

    def directions(self, include_retired: bool = False) -> list[Direction]:
        return [Direction(**dict(r)) for r in self.connection.execute("SELECT * FROM directions WHERE ?=1 OR status='active' ORDER BY id", (int(include_retired),))]

    def prepare_context(self, episode: int, focus_entity_ids: tuple[int, ...] = ()) -> tuple[str, tuple[int, ...], tuple[int, ...], int]:
        if len(focus_entity_ids) != len(set(focus_entity_ids)) or len(focus_entity_ids) > 10:
            raise StoryError('Select at most 10 distinct active characters for an episode.')
        for entity_id in focus_entity_ids:
            if self.entity(entity_id).kind != 'character':
                raise StoryError('An active cast selection contains characters, not locations.')
        facts = [f for f in self.query_facts() if not focus_entity_ids or f.subject_id in focus_entity_ids or f.object_id in focus_entity_ids]
        directions = [d for d in self.directions() if d.start_episode <= episode <= d.end_episode and (not focus_entity_ids or d.subject_id is None or d.subject_id in focus_entity_ids)]
        lines = [f'Confirmed fact #{f.id} [accepted revision {f.source_revision_id}]: {self.entity(f.subject_id).name} | {f.predicate} = {f.value}' for f in facts]
        lines += [f'Future direction #{d.id}, NOT an event: {d.text}' for d in directions]
        return '\n'.join(lines), tuple(f.id for f in facts), tuple(d.id for d in directions), self.revision()

    def storyboard_snapshot(self) -> dict[str, Any]:
        """One consistent read, including visible proposals that are not canon."""
        with self.repo.transaction():
            return {
                'memory_revision': self.revision(),
                'next_episode': self.repo.story()['next_episode'],
                'entities': [asdict(e) for e in self.entities()],
                'current_facts': [asdict(f) for f in self.query_facts()],
                'pending_fact_proposals': [asdict(self._fact(r)) for r in self.connection.execute("SELECT * FROM facts WHERE status='proposed' ORDER BY id")],
                'future_directions': [asdict(d) for d in self.directions()],
                'warning': 'Future directions are intentions, not events; their ranges govern applicability. Facts are manual annotations. Pending proposals are not confirmed history.',
            }

    def graph_snapshot(self, subject_id: int | None = None) -> dict[str, Any]:
        # One read model, never a second editable source of truth.
        with self.repo.transaction():
            facts = self.query_facts(subject_id=subject_id, current_only=False)
            fact_ids = {fact.id for fact in facts}
            situations = [self.situation(r['id']) for r in self.connection.execute('SELECT id FROM situations ORDER BY id')]
            if subject_id is not None:
                situations = [s for s in situations if any(f.situation_id == s.id for f in facts)]
            entity_ids = {subject_id} if subject_id is not None else {e.id for e in self.entities()}
            entity_ids |= {f.subject_id for f in facts} | {f.object_id for f in facts if f.object_id is not None}
            nodes = [{**asdict(self.entity(i)), 'id': f'entity-{i}', 'label': self.entity(i).name, 'status': 'registry'} for i in sorted(entity_ids)]
            edges = []
            def link(source: str, target: str, kind: str) -> None:
                edges.append({'source': source, 'target': target, 'kind': kind})
            for direction in self.directions():
                if subject_id is not None and direction.subject_id not in (None, subject_id):
                    continue
                key = f'direction-{direction.id}'
                nodes.append({**asdict(direction), 'id': key, 'kind': 'direction', 'label': direction.text, 'status': 'planned-not-fact'})
                if direction.subject_id is not None:
                    if direction.subject_id not in entity_ids:
                        entity = self.entity(direction.subject_id)
                        nodes.append({**asdict(entity), 'id': f'entity-{entity.id}', 'label': entity.name, 'status': 'registry'})
                        entity_ids.add(entity.id)
                    link(key, f'entity-{direction.subject_id}', 'guides_future')
            sources = {f.source_revision_id for f in facts} | {s.source_revision_id for s in situations}
            for fact in facts:
                key = f'fact-{fact.id}'
                nodes.append({**asdict(fact), 'id': key, 'kind': 'fact', 'label': f'{fact.predicate}: {fact.value}', 'status': 'historical' if fact.superseded_by else 'current'})
                link(key, f'entity-{fact.subject_id}', 'about')
                link(key, f'episode-{fact.source_revision_id}', 'evidenced_by')
                if fact.object_id is not None:
                    link(key, f'entity-{fact.object_id}', 'relates_to')
                if fact.situation_id is not None:
                    link(key, f'situation-{fact.situation_id}', 'in_situation')
                # A filtered view must not link to a predecessor outside its nodes.
                if fact.supersedes is not None and fact.supersedes in fact_ids:
                    link(key, f'fact-{fact.supersedes}', 'supersedes')
            for situation in situations:
                key = f'situation-{situation.id}'
                nodes.append({**asdict(situation), 'id': key, 'kind': 'situation', 'label': situation.title, 'status': 'accepted-source'})
                link(key, f'episode-{situation.source_revision_id}', 'evidenced_by')
            for revision_id in sorted(sources):
                row = self.connection.execute("SELECT number,accepted_text FROM episodes WHERE id=? AND status='accepted'", (revision_id,)).fetchone()
                nodes.append({'id': f'episode-{revision_id}', 'kind': 'episode', 'label': f'Episode {row["number"]}', 'status': 'accepted', 'text': row['accepted_text'], 'source_revision_id': revision_id})
            warning = 'Confirmed manual annotations, not exhaustive extraction or a semantic consistency guarantee.'
            if subject_id is not None:
                warning += ' Filtered view: facts and supersession links outside the selected entity are omitted; use the unfiltered view for full recorded history.'
            return {'memory_revision': self.revision(), 'next_episode': self.repo.story()['next_episode'], 'nodes': nodes, 'edges': edges,
                    'warning': warning}
