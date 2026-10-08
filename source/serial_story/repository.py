import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Protocol

from .records import AcceptedEpisode, Episode, Plan, StoryError


class StoryRepository(Protocol):
    def initialize(self, premise: str) -> None: ...
    def story(self) -> dict[str, Any]: ...
    def plan(self) -> Plan | None: ...
    def save_plan(self, content: dict[str, Any]) -> Plan: ...
    def approve_plan(self, plan_id: int) -> Plan: ...
    def pending(self) -> Episode | None: ...
    def save_draft(self, text: str, number: int, history: int, memory_revision: int = 0) -> Episode: ...
    def accept(self, revision_id: int, edited_text: str | None = None) -> AcceptedEpisode: ...
    def reject(self, revision_id: int, note: str) -> None: ...
    def accepted(self) -> list[AcceptedEpisode]: ...
    def read(self, number: int) -> AcceptedEpisode: ...


SCHEMA = """
CREATE TABLE IF NOT EXISTS story (
    id INTEGER PRIMARY KEY CHECK(id=1), premise TEXT NOT NULL,
    next_episode INTEGER NOT NULL DEFAULT 1, history_revision INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS plans (
    id INTEGER PRIMARY KEY, status TEXT NOT NULL CHECK(status IN ('proposed','approved')),
    content TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS episodes (
    id INTEGER PRIMARY KEY, number INTEGER NOT NULL CHECK(number BETWEEN 1 AND 200),
    status TEXT NOT NULL CHECK(status IN ('pending','accepted','rejected')),
    text TEXT NOT NULL, accepted_text TEXT, parent_history INTEGER NOT NULL,
    CHECK((status='accepted' AND accepted_text IS NOT NULL) OR
          (status!='accepted' AND accepted_text IS NULL))
);
CREATE UNIQUE INDEX IF NOT EXISTS accepted_number ON episodes(number) WHERE status='accepted';
CREATE UNIQUE INDEX IF NOT EXISTS pending_number ON episodes(number) WHERE status='pending';
CREATE TABLE IF NOT EXISTS memory_sources (
    episode_id INTEGER PRIMARY KEY REFERENCES episodes(id), final_text TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY, target_kind TEXT NOT NULL, target_id INTEGER NOT NULL,
    decision TEXT NOT NULL, note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE(target_kind,target_id,decision)
);
"""


class SQLiteRepository:
    """One local story per database, explicit short write transactions."""

    def __init__(self, path: Path, *, read_only: bool = False):
        if read_only:
            self.connection = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=5, isolation_level=None)
            self.connection.row_factory = sqlite3.Row
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(
            path, timeout=5,
            autocommit=sqlite3.LEGACY_TRANSACTION_CONTROL, isolation_level=None,
        )
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.executescript(SCHEMA)
        columns = {r['name'] for r in self.connection.execute('PRAGMA table_info(episodes)')}
        if 'parent_memory' not in columns:
            self.connection.execute('ALTER TABLE episodes ADD COLUMN parent_memory INTEGER NOT NULL DEFAULT 0')

    def __enter__(self) -> "SQLiteRepository":
        return self

    def __exit__(self, *args: object) -> None:
        self.connection.close()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        # Compose canonical mutations with an outer studio receipt transaction.
        nested = self.connection.in_transaction
        self._savepoint_number = getattr(self, '_savepoint_number', 0) + 1
        point = f'repository_{self._savepoint_number}'
        self.connection.execute(f'SAVEPOINT {point}' if nested else 'BEGIN IMMEDIATE')
        try:
            yield
            self.connection.execute(f'RELEASE SAVEPOINT {point}' if nested else 'COMMIT')
        except BaseException:
            if nested:
                self.connection.execute(f'ROLLBACK TO SAVEPOINT {point}')
                self.connection.execute(f'RELEASE SAVEPOINT {point}')
            else:
                self.connection.execute('ROLLBACK')
            raise

    def initialize(self, premise: str) -> None:
        if not premise.strip():
            raise StoryError("Supply a non-empty premise.")
        with self.transaction():
            existing = self.connection.execute("SELECT premise FROM story WHERE id=1").fetchone()
            if existing is not None:
                if existing["premise"] != premise:
                    raise StoryError("This database already has another story. Choose a new database.")
                return
            self.connection.execute("INSERT INTO story(id,premise) VALUES(1,?)", (premise,))

    def story(self) -> dict[str, Any]:
        row = self.connection.execute("SELECT * FROM story WHERE id=1").fetchone()
        if row is None:
            raise StoryError("Create a story first with the init command.")
        return dict(row)

    def plan(self) -> Plan | None:
        row = self.connection.execute("SELECT * FROM plans ORDER BY id DESC LIMIT 1").fetchone()
        return Plan(row["id"], row["status"], json.loads(row["content"])) if row else None

    def save_plan(self, content: dict[str, Any]) -> Plan:
        with self.transaction():
            self.story()
            if self.plan() is not None:
                raise StoryError("A plan already exists. Read and review it first.")
            self.connection.execute("INSERT INTO plans(status,content) VALUES('proposed',?)", (json.dumps(content),))
        result = self.plan()
        assert result is not None
        return result

    def approve_plan(self, plan_id: int) -> Plan:
        with self.transaction():
            plan = self.plan()
            if plan is None or plan.id != plan_id:
                raise StoryError("Read the current plan and use its proposal ID.")
            if plan.status != "approved":
                self.connection.execute("UPDATE plans SET status='approved' WHERE id=?", (plan_id,))
                self.connection.execute(
                    "INSERT INTO reviews(target_kind,target_id,decision) VALUES('plan',?,'approved')", (plan_id,),
                )
        result = self.plan()
        assert result is not None
        return result

    @staticmethod
    def _episode(row: sqlite3.Row) -> Episode:
        return Episode(row["id"], row["number"], row["status"], row["text"], row["accepted_text"], row["parent_history"], row["parent_memory"])

    def pending(self) -> Episode | None:
        row = self.connection.execute("SELECT * FROM episodes WHERE status='pending' ORDER BY id DESC LIMIT 1").fetchone()
        return self._episode(row) if row else None

    def memory_revision(self) -> int:
        if self.connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='memory_meta'").fetchone() is None:
            return 0
        return self.connection.execute('SELECT revision FROM memory_meta WHERE id=1').fetchone()[0]

    def save_draft(self, text: str, number: int, history: int, memory_revision: int = 0) -> Episode:
        with self.transaction():
            story = self.story()
            if story["next_episode"] != number or story["history_revision"] != history or self.memory_revision() != memory_revision:
                raise StoryError("History changed while drafting. Stop and inspect the current story.")
            cursor = self.connection.execute(
                "INSERT INTO episodes(number,status,text,parent_history,parent_memory) VALUES(?,'pending',?,?,?)", (number, text, history, memory_revision),
            )
            revision_id = cursor.lastrowid
        row = self.connection.execute("SELECT * FROM episodes WHERE id=?", (revision_id,)).fetchone()
        assert row is not None
        return self._episode(row)

    def accept(self, revision_id: int, edited_text: str | None = None) -> AcceptedEpisode:
        with self.transaction():
            row = self.connection.execute("SELECT * FROM episodes WHERE id=?", (revision_id,)).fetchone()
            if row is not None and row["status"] == "accepted":
                if edited_text is not None and edited_text != row["accepted_text"]:
                    raise StoryError("Already accepted. Historical edits require a separate repair workflow.")
                return AcceptedEpisode(revision_id, row["number"], row["accepted_text"])
            if row is None or row["status"] != "pending":
                raise StoryError("Read a pending draft before accepting it.")
            story = self.story()
            if row["number"] != story["next_episode"] or row["parent_history"] != story["history_revision"] or row['parent_memory'] != self.memory_revision():
                raise StoryError("Accepted history or story directions changed. Inspect this draft, then explicitly reject/redraft if needed.")
            final = row["text"] if edited_text is None else edited_text
            if not 400 <= len(final.split()) <= 700:
                raise StoryError("Final prose must contain 400-700 whitespace-separated words. Edit and try again.")
            self.connection.execute("UPDATE episodes SET status='accepted',accepted_text=? WHERE id=?", (final, revision_id))
            self.connection.execute("INSERT INTO memory_sources(episode_id,final_text) VALUES(?,?)", (revision_id, final))
            self.connection.execute("INSERT INTO reviews(target_kind,target_id,decision) VALUES('episode',?,'accepted')", (revision_id,))
            self.connection.execute("UPDATE story SET next_episode=next_episode+1,history_revision=history_revision+1 WHERE id=1")
        return AcceptedEpisode(revision_id, row["number"], final)

    def reject(self, revision_id: int, note: str) -> None:
        with self.transaction():
            row = self.connection.execute("SELECT * FROM episodes WHERE id=?", (revision_id,)).fetchone()
            if row is not None and row["status"] == "rejected":
                return
            if row is None or row["status"] != "pending":
                raise StoryError("Only a pending draft can be rejected.")
            self.connection.execute("UPDATE episodes SET status='rejected' WHERE id=?", (revision_id,))
            self.connection.execute(
                "INSERT INTO reviews(target_kind,target_id,decision,note) VALUES('episode',?,'rejected',?)",
                (revision_id, note),
            )

    def accepted(self) -> list[AcceptedEpisode]:
        return [AcceptedEpisode(r["id"], r["number"], r["accepted_text"]) for r in self.connection.execute(
            "SELECT id,number,accepted_text FROM episodes WHERE status='accepted' ORDER BY number",
        )]

    def read(self, number: int) -> AcceptedEpisode:
        for episode in self.accepted():
            if episode.number == number:
                return episode
        raise StoryError("This episode has not been accepted. Review a draft first.")
