"""Live read-only inspection of an explicitly selected local story database.

No schema initialization, provider calls, key reads, approvals or edit routes.
"""
import hashlib
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def read_connection(path: Path):
    path = path.resolve(strict=True)
    connection = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=5,
                                 isolation_level=None)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute('PRAGMA query_only=ON')
        connection.execute('PRAGMA trusted_schema=OFF')
        connection.execute('BEGIN')
        yield connection
    finally:
        connection.close()


def story_snapshot(path: Path, *, fixture: bool = False) -> dict:
    with read_connection(path) as connection:
        tables = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        def rows(table: str) -> list[dict]:
            # Call sites are fixed application-owned names, never HTTP input.
            return [dict(r) for r in connection.execute(f'SELECT * FROM {table} ORDER BY id')] if table in tables else []
        stories = rows('story')
        plans = rows('plans')
        plan = plans[-1] if plans else None
        if plan:
            plan['content'] = json.loads(plan['content'])
        episodes = rows('episodes')
        for episode in episodes:
            prose = episode['accepted_text'] if episode['status'] == 'accepted' else episode['text']
            episode['prose'] = prose
            episode['words'] = len(prose.split())
            episode['word_count_ok'] = 400 <= episode['words'] <= 700
        result = {
            'fixture_only': fixture, 'generation_enabled': False,
            'story': stories[0] if stories else None, 'plan': plan, 'episodes': episodes,
            'entities': rows('entities'), 'facts': rows('facts'),
            'situations': rows('situations'), 'directions': rows('directions'),
            'reviews': rows('reviews'), 'calls': rows('calls'),
            'budget_policy': rows('budget_policy'), 'memory_meta': rows('memory_meta'),
            'quality_assessment': 'Word counts only. Narrative quality and semantic continuity require author review.'
        }
        result['revision'] = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()
        return result


def live_graph(path: Path) -> str:
    # Reuse the reviewed graph builder without calling any schema constructors.
    # Every access remains inside SQLite's read-only, single-snapshot transaction.
    from ..repository import SQLiteRepository
    from ..memory import SQLiteMemory
    from ..graph import render_graph
    class ReadOnlyRepository(SQLiteRepository):
        def __init__(self, connection):
            self.connection = connection
        @contextmanager
        def transaction(self):
            yield
    class ReadOnlyMemory(SQLiteMemory):
        def __init__(self, repository):
            self.repo = repository
            self.connection = repository.connection
    with read_connection(path) as connection:
        return render_graph(ReadOnlyMemory(ReadOnlyRepository(connection)).graph_snapshot())


