import json
import sqlite3
import uuid
from contextlib import AbstractContextManager
from typing import Any, Literal, Protocol

from .records import StoryError


class BudgetAccounting(Protocol):
    def reserve(self, episode: int, stage: str, max_charge: int = 0,
                manifest: dict[str, Any] | None = None) -> str: ...
    def settle(self, call_id: str, actual_charge: int, latency_ms: int,
               outcome: Literal["succeeded", "failed"] = "succeeded") -> None: ...
    def mark_uncertain(self, call_id: str, latency_ms: int) -> None: ...
    def snapshot(self, episode: int) -> dict[str, int]: ...


class BudgetStore(Protocol):
    connection: sqlite3.Connection
    def transaction(self) -> AbstractContextManager[None]: ...


BUDGET_SCHEMA = """
CREATE TABLE IF NOT EXISTS budget_policy (
    id INTEGER PRIMARY KEY CHECK(id=1), max_calls INTEGER NOT NULL CHECK(max_calls>0),
    cap_micro_usd INTEGER NOT NULL CHECK(cap_micro_usd>=0),
    project_cap_micro_usd INTEGER NOT NULL DEFAULT 1000000 CHECK(project_cap_micro_usd BETWEEN 0 AND 1000000)
);
CREATE TABLE IF NOT EXISTS calls (
    id TEXT PRIMARY KEY, episode INTEGER NOT NULL CHECK(episode BETWEEN 0 AND 200),
    stage TEXT NOT NULL, provider TEXT NOT NULL DEFAULT 'fake',
    status TEXT NOT NULL CHECK(status IN ('reserved','succeeded','failed','uncertain')),
    reserved_micro_usd INTEGER NOT NULL CHECK(reserved_micro_usd>=0),
    spent_micro_usd INTEGER NOT NULL DEFAULT 0 CHECK(spent_micro_usd>=0),
    latency_ms INTEGER, context_manifest TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
"""


class SQLiteBudget:
    """Durable accounting seam. Nonzero amounts are artificial offline tests only."""

    def __init__(self, store: BudgetStore, max_calls: int = 3, cap_micro_usd: int = 0,
                 project_cap_micro_usd: int = 1_000_000):
        if any(type(v) is not int or v < 0 for v in (max_calls, cap_micro_usd, project_cap_micro_usd)) or max_calls == 0 or project_cap_micro_usd > 1_000_000:
            raise StoryError('Use non-negative integer micro-USD amounts, positive call limits and a project ceiling no greater than USD 1.')
        self.store = store
        store.connection.executescript(BUDGET_SCHEMA)
        columns = {r['name'] for r in store.connection.execute('PRAGMA table_info(budget_policy)')}
        if 'project_cap_micro_usd' not in columns:
            store.connection.execute('ALTER TABLE budget_policy ADD COLUMN project_cap_micro_usd INTEGER NOT NULL DEFAULT 1000000 CHECK(project_cap_micro_usd BETWEEN 0 AND 1000000)')
        with store.transaction():
            # Reopening never overwrites a persisted cap or attempt limit.
            store.connection.execute(
                "INSERT OR IGNORE INTO budget_policy(id,max_calls,cap_micro_usd,project_cap_micro_usd) VALUES(1,?,?,?)",
                (max_calls, cap_micro_usd, project_cap_micro_usd),
            )

    def snapshot(self, episode: int) -> dict[str, int]:
        policy = self.store.connection.execute("SELECT * FROM budget_policy WHERE id=1").fetchone()
        row = self.store.connection.execute(
            "SELECT count(*) AS attempts, COALESCE(sum(reserved_micro_usd),0) AS reserved, "
            "COALESCE(sum(spent_micro_usd),0) AS spent, "
            "COALESCE(sum(status IN ('reserved','uncertain')),0) AS unresolved FROM calls WHERE episode=?",
            (episode,),
        ).fetchone()
        return {"attempts": row["attempts"], "reserved_micro_usd": row["reserved"],
                "spent_micro_usd": row["spent"], "unresolved": row["unresolved"],
                "max_calls": policy["max_calls"], "cap_micro_usd": policy["cap_micro_usd"]}

    def project_snapshot(self) -> dict[str, int]:
        policy = self.store.connection.execute('SELECT project_cap_micro_usd FROM budget_policy WHERE id=1').fetchone()
        row = self.store.connection.execute("SELECT COALESCE(sum(reserved_micro_usd),0) AS reserved, COALESCE(sum(spent_micro_usd),0) AS spent, COALESCE(sum(status IN ('reserved','uncertain')),0) AS unresolved FROM calls").fetchone()
        return {'cap_micro_usd': policy[0], 'spent_micro_usd': row['spent'],
                'reserved_micro_usd': row['reserved'], 'unresolved': row['unresolved'],
                'remaining_micro_usd': policy[0] - row['spent'] - row['reserved']}

    def reserve(self, episode: int, stage: str, max_charge: int = 0,
                manifest: dict[str, Any] | None = None) -> str:
        if type(max_charge) is not int or max_charge < 0 or type(episode) is not int or not 0 <= episode <= 200 or not isinstance(stage, str) or not stage.strip() or len(stage) > 128:
            raise StoryError('Use an eligible episode, named stage and non-negative integer reservation.')
        with self.store.transaction():
            budget = self.snapshot(episode)
            project = self.project_snapshot()
            if project['unresolved']:
                raise StoryError("An earlier call is unresolved. Inspect accounting before another attempt.")
            if budget["attempts"] >= budget["max_calls"]:
                raise StoryError("Call limit reached for this episode. Stop and discuss the next attempt.")
            if budget["spent_micro_usd"] + budget["reserved_micro_usd"] + max_charge > budget["cap_micro_usd"]:
                raise StoryError("Cost limit reached. No call was made.")
            if max_charge > project['remaining_micro_usd']:
                raise StoryError('Project-wide USD 1 ceiling reached. No call was made.')
            call_id = uuid.uuid4().hex
            self.store.connection.execute(
                "INSERT INTO calls(id,episode,stage,status,reserved_micro_usd,context_manifest) "
                "VALUES(?,?,?,'reserved',?,?)",
                (call_id, episode, stage, max_charge, json.dumps(manifest or {})),
            )
        return call_id

    def settle(self, call_id: str, actual_charge: int, latency_ms: int,
               outcome: Literal["succeeded", "failed"] = "succeeded") -> None:
        if type(actual_charge) is not int or type(latency_ms) is not int or actual_charge < 0 or latency_ms < 0 or outcome not in ("succeeded", "failed"):
            raise StoryError("Invalid accounting settlement.")
        with self.store.transaction():
            row = self.store.connection.execute("SELECT * FROM calls WHERE id=?", (call_id,)).fetchone()
            if row is None:
                raise StoryError("Unknown call ID.")
            if row["status"] in ("succeeded", "failed"):
                if row["spent_micro_usd"] != actual_charge or row["status"] != outcome:
                    raise StoryError("This call has already been settled differently.")
                return
            if actual_charge > row["reserved_micro_usd"]:
                raise StoryError("Charge exceeds reservation. Keep the call unresolved and reconcile explicitly.")
            self.store.connection.execute(
                "UPDATE calls SET status=?,reserved_micro_usd=0,spent_micro_usd=?,latency_ms=? WHERE id=?",
                (outcome, actual_charge, latency_ms, call_id),
            )

    def mark_uncertain(self, call_id: str, latency_ms: int) -> None:
        if type(latency_ms) is not int or latency_ms < 0:
            raise StoryError('Latency must be a non-negative integer.')
        with self.store.transaction():
            changed = self.store.connection.execute(
                "UPDATE calls SET status='uncertain',latency_ms=? WHERE id=? AND status IN ('reserved','uncertain')",
                (latency_ms, call_id),
            )
            if changed.rowcount != 1:
                raise StoryError("Only an unresolved call can have uncertain usage.")


class ProjectMergeLedger:
    """Real Merge accounting, separate from per-story synthetic accounting.

    Runtime uses CANONICAL_PATH only. Alternate paths are dependency injection
    for offline synthetic tests, never an HTTP or CLI option. No cap/rate option.
    Reserved rows survive process death and block all new dispatches.
    """
    from pathlib import Path as _Path
    CANONICAL_PATH = _Path(__file__).resolve().parents[1] / 'local' / 'merge-project-ledger.db'
    CAP = 1_000_000

    def __init__(self, path=None):
        path = self.CANONICAL_PATH if path is None else self._Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, timeout=5, isolation_level=None)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute('PRAGMA synchronous=FULL')
        self.connection.executescript('''
        CREATE TABLE IF NOT EXISTS merge_calls (
          operation_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL,
          status TEXT NOT NULL CHECK(status IN ('reserved','succeeded','uncertain')),
          reserved INTEGER NOT NULL CHECK(reserved>=0), spent INTEGER NOT NULL DEFAULT 0 CHECK(spent>=0),
          manifest TEXT NOT NULL, receipt TEXT, reported_charge INTEGER, dispatched INTEGER NOT NULL DEFAULT 0, confirmation TEXT,
          created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
        );
        ''')

        columns = {r['name'] for r in self.connection.execute('PRAGMA table_info(merge_calls)')}
        if 'confirmation' not in columns:
            self.connection.execute('ALTER TABLE merge_calls ADD COLUMN confirmation TEXT')

    def close(self):
        self.connection.close()

    def get(self, operation_id):
        row = self.connection.execute('SELECT * FROM merge_calls WHERE operation_id=?', (operation_id,)).fetchone()
        if row is None:
            return None
        return {**dict(row), 'manifest': json.loads(row['manifest']),
                'receipt': json.loads(row['receipt']) if row['receipt'] else None}

    def snapshot(self):
        row = self.connection.execute("SELECT coalesce(sum(reserved),0),coalesce(sum(spent),0),coalesce(sum(status IN ('reserved','uncertain')),0) FROM merge_calls").fetchone()
        return {'cap_micro_usd': self.CAP, 'reserved_micro_usd': row[0], 'spent_micro_usd': row[1],
                'remaining_micro_usd': self.CAP - row[0] - row[1], 'unresolved': row[2]}

    def reserve(self, operation_id, fingerprint, amount, manifest, confirmation=None):
        if (not isinstance(operation_id, str) or not 1 <= len(operation_id) <= 80 or
                not isinstance(fingerprint, str) or not fingerprint or type(amount) is not int or amount < 0):
            raise StoryError('Invalid Merge reservation.')
        encoded = json.dumps(manifest, sort_keys=True, allow_nan=False)
        self.connection.execute('BEGIN IMMEDIATE')
        try:
            previous = self.get(operation_id)
            if previous:
                if previous['fingerprint'] != fingerprint:
                    raise StoryError('This action ID belongs to a different frozen request.')
                self.connection.execute('COMMIT')
                return previous
            snapshot = self.snapshot()
            if snapshot['unresolved']:
                raise StoryError('An earlier Merge call is unresolved. No new call is permitted.')
            if amount > snapshot['remaining_micro_usd']:
                raise StoryError('Shared project USD 1 ceiling reached. No call was made.')
            self.connection.execute("INSERT INTO merge_calls(operation_id,fingerprint,status,reserved,manifest,confirmation) VALUES(?,?,'reserved',?,?,?)",
                                    (operation_id, fingerprint, amount, encoded, json.dumps(confirmation, sort_keys=True, allow_nan=False) if confirmation is not None else None))
            self.connection.execute('COMMIT')
        except BaseException:
            if self.connection.in_transaction:
                self.connection.execute('ROLLBACK')
            raise
        return self.get(operation_id)

    def succeed(self, operation_id, charge, receipt):
        if type(charge) is not int or charge < 0:
            raise StoryError('Invalid reported Merge charge.')
        encoded = json.dumps(receipt, sort_keys=True, allow_nan=False)
        self.connection.execute('BEGIN IMMEDIATE')
        over = False
        try:
            row = self.get(operation_id)
            if row is None or row['status'] == 'uncertain':
                raise StoryError('Only a reserved Merge call may settle.')
            if row['status'] == 'succeeded':
                if row['spent'] != charge or row['receipt'] != receipt:
                    raise StoryError('This Merge receipt already settled differently.')
            else:
                over = charge > row['reserved']
                self.connection.execute('UPDATE merge_calls SET status=?,reserved=?,spent=?,receipt=?,reported_charge=? WHERE operation_id=?',
                    ('uncertain' if over else 'succeeded', charge if over else 0,
                     0 if over else charge, encoded, charge, operation_id))
            self.connection.execute('COMMIT')
        except BaseException:
            if self.connection.in_transaction:
                self.connection.execute('ROLLBACK')
            raise
        if over:
            raise StoryError('Reported charge exceeds reservation. Receipt retained; further calls are blocked.')

    def uncertain(self, operation_id, receipt=None):
        if receipt is not None:
            charge = receipt['charge_micro_usd']
            if type(charge) is not int or charge < 0:
                raise StoryError('Invalid reported Merge charge.')
            self.connection.execute("UPDATE merge_calls SET receipt=?,reported_charge=?,reserved=max(reserved,?) WHERE operation_id=? AND status IN ('reserved','uncertain')",
                (json.dumps(receipt, sort_keys=True, allow_nan=False), charge, charge, operation_id))
        changed = self.connection.execute("UPDATE merge_calls SET status='uncertain' WHERE operation_id=? AND status IN ('reserved','uncertain')", (operation_id,))
        if changed.rowcount != 1:
            raise StoryError('Only an unresolved Merge call may be marked uncertain.')


    def claim_dispatch(self, operation_id):
        """Atomic ownership, committed before outbound I/O; never reclaimed."""
        return self.connection.execute("UPDATE merge_calls SET dispatched=1 WHERE operation_id=? AND status='reserved' AND dispatched=0", (operation_id,)).rowcount == 1
