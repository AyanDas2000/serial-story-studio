import importlib.util
import tempfile
import unittest
from pathlib import Path


class WorkflowTest(unittest.TestCase):
    def temporary_directory(self):
        # Keep probe data in this project's ignored local area, not system temp.
        root = Path(__file__).resolve().parents[1] / "local" / "test-runs"
        root.mkdir(parents=True, exist_ok=True)
        return tempfile.TemporaryDirectory(dir=root)

    def load_api(self):
        self.assertIsNotNone(
            importlib.util.find_spec("serial_story"),
            "The offline story package does not exist yet",
        )
        from serial_story.repository import SQLiteRepository
        from serial_story.service import StoryService
        return SQLiteRepository, StoryService

    def test_accepted_episode_survives_reopen(self):
        Repository, Service = self.load_api()
        with self.temporary_directory() as folder:
            db = Path(folder) / "story.db"
            with Repository(db) as repo:
                studio = Service(repo)
                studio.initialize("A cartographer finds a room missing from every map.")
                plan = studio.propose_plan()
                self.assertEqual([b["episode"] for b in plan.content["beats"]], list(range(1, 201)))
                studio.approve_plan(plan.id)
                draft = studio.draft()
                receipt = studio.accept(draft.id)
                self.assertEqual(receipt.text, draft.text)
                self.assertEqual(studio.status()["next_episode"], 2)
            with Repository(db) as repo:
                self.assertEqual(Service(repo).read(1).text, draft.text)
                self.assertEqual(Service(repo).status()["next_episode"], 2)


    def test_edited_acceptance_is_memory_source(self):
        import inspect
        Repository, Service = self.load_api()
        self.assertIn("edited_text", inspect.signature(Service.accept).parameters,
                      "Acceptance must allow human final prose")
        with self.temporary_directory() as folder, Repository(Path(folder) / "story.db") as repo:
            studio = Service(repo)
            studio.initialize("A harbor chart conceals a room.")
            studio.approve_plan(studio.propose_plan().id)
            draft = studio.draft()
            edited = draft.text.replace("Mara opens the map room.", "Ivo is alive. Mara waits at the harbor.")
            receipt = studio.accept(draft.id, edited_text=edited)
            self.assertEqual(receipt.text, edited)
            memory = repo.connection.execute("SELECT final_text FROM memory_sources").fetchone()[0]
            self.assertEqual(memory, edited)
            self.assertIn("Ivo is alive", studio.context().text)
            self.assertNotIn("Mara opens the map room.", studio.context().text)


    def test_repeated_acceptance_is_one_transaction(self):
        from serial_story.records import StoryError
        Repository, Service = self.load_api()
        with self.temporary_directory() as folder, Repository(Path(folder) / "story.db") as repo:
            studio = Service(repo)
            studio.initialize("A map opens a door.")
            studio.approve_plan(studio.propose_plan().id)
            draft = studio.draft()
            first = studio.accept(draft.id)
            second = studio.accept(draft.id)
            self.assertEqual(first, second)
            self.assertEqual(studio.status()["next_episode"], 2)
            self.assertEqual(repo.connection.execute("SELECT count(*) FROM memory_sources").fetchone()[0], 1)
            self.assertEqual(repo.connection.execute("SELECT count(*) FROM reviews WHERE decision='accepted'").fetchone()[0], 1)
            with self.assertRaises(StoryError):
                studio.accept(draft.id, edited_text="different final history")


    def test_rejection_requires_an_explicit_new_attempt(self):
        from serial_story.records import StoryError
        Repository, Service = self.load_api()
        self.assertTrue(hasattr(Service, "reject"), "Episode review needs a rejection operation")
        with self.temporary_directory() as folder, Repository(Path(folder) / "story.db") as repo:
            studio = Service(repo)
            studio.initialize("A map opens a door.")
            with self.assertRaises(StoryError):
                studio.draft()
            studio.approve_plan(studio.propose_plan().id)
            first = studio.draft()
            studio.reject(first.id, note="Try a different opening.")
            self.assertEqual(studio.status()["next_episode"], 1)
            self.assertEqual(repo.accepted(), [])
            self.assertNotIn(first.text, studio.context().text)
            with self.assertRaises(StoryError):
                studio.accept(first.id)
            second = studio.draft()
            self.assertNotEqual(first.id, second.id)
            self.assertEqual(second.number, 1)


    def test_acceptance_refuses_out_of_range_prose(self):
        from serial_story.records import StoryError
        Repository, Service = self.load_api()
        with self.temporary_directory() as folder, Repository(Path(folder) / "story.db") as repo:
            studio = Service(repo)
            studio.initialize("A map opens a door.")
            studio.approve_plan(studio.propose_plan().id)
            draft = studio.draft()
            self.assertTrue(400 <= len(draft.text.split()) <= 700)
            with self.assertRaises(StoryError):
                studio.accept(draft.id, edited_text="Ivo lives.")
            self.assertEqual(studio.status()["next_episode"], 1)
            self.assertEqual(repo.accepted(), [])


    def test_context_has_a_hard_character_bound(self):
        import inspect
        from serial_story.records import StoryError
        Repository, Service = self.load_api()
        self.assertIn("max_context_characters", inspect.signature(Service).parameters)
        with self.temporary_directory() as folder, Repository(Path(folder) / "story.db") as repo:
            studio = Service(repo)
            studio.initialize("A map opens a door.")
            studio.approve_plan(studio.propose_plan().id)
            draft = studio.draft()
            studio.accept(draft.id)
            small = Service(repo, max_context_characters=200)
            context = small.context()
            self.assertLessEqual(len(context.text), 200)
            self.assertEqual(context.included_revision_ids, ())
            self.assertEqual(context.omitted_revision_ids, (draft.id,))
            with self.assertRaises(StoryError):
                Service(repo, max_context_characters=10).context()


    def test_fake_attempt_budget_survives_process_restart(self):
        import subprocess
        import sys
        from serial_story.records import StoryError
        Repository, Service = self.load_api()
        with self.temporary_directory() as folder:
            db = Path(folder) / "story.db"
            with Repository(db) as repo:
                studio = Service(repo)
                studio.initialize("A map opens a door.")
                self.assertIn("budget", studio.status(), "Call accounting must be visible")
                studio.approve_plan(studio.propose_plan().id)
                for _ in range(3):
                    draft = studio.draft()
                    studio.reject(draft.id)
                with self.assertRaises(StoryError):
                    studio.draft()
                self.assertEqual(studio.status()["budget"]["attempts"], 3)
            script = (
                "import sys; from pathlib import Path; "
                "from serial_story.repository import SQLiteRepository; "
                "from serial_story.service import StoryService; "
                "repo=SQLiteRepository(Path(sys.argv[1])); StoryService(repo).draft()"
            )
            result = subprocess.run([sys.executable, "-c", script, str(db)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Call limit reached", result.stderr)


    def test_cli_recovers_pending_review_in_fresh_processes(self):
        import json
        import subprocess
        import sys
        self.assertIsNotNone(importlib.util.find_spec("serial_story.__main__"),
                             "A module CLI is required for the offline walkthrough")
        with self.temporary_directory() as folder:
            db = Path(folder) / "story.db"
            def run(*args, expected=0):
                result = subprocess.run([sys.executable, "-m", "serial_story", "--db", str(db), *args],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, expected, result.stderr)
                return json.loads(result.stdout) if result.stdout else None
            run("init", "--premise", "A map opens a door.")
            plan = run("plan")
            run("draft", expected=2)
            run("approve-plan", str(plan["id"]))
            review_file = Path(folder) / "review.txt"
            first = run("draft", "--out", str(review_file))
            self.assertEqual(review_file.read_text(encoding="utf-8"), first["text"])
            resumed = run("draft")
            self.assertEqual(first["id"], resumed["id"])
            self.assertEqual(run("status")["budget"]["attempts"], 1)
            edited = first["text"].replace("Mara opens the map room.", "Ivo is alive. Mara opens the harbor gate.")
            edit_file = Path(folder) / "edited.txt"
            edit_file.write_text(edited, encoding="utf-8")
            run("accept", str(first["id"]), "--text-file", str(edit_file))
            run("accept", str(first["id"]))
            self.assertEqual(run("status")["next_episode"], 2)
            reopened = run("read", "1")
            self.assertEqual(reopened["text"], edited)
            out = Path(folder) / "accepted.txt"
            run("read", "1", "--out", str(out))
            self.assertEqual(out.read_text(encoding="utf-8"), edited)


    def test_acceptance_rolls_back_all_canonical_changes_on_failure(self):
        import sqlite3
        Repository, Service = self.load_api()
        with self.temporary_directory() as folder, Repository(Path(folder) / "story.db") as repo:
            studio = Service(repo)
            studio.initialize("A map opens a door.")
            studio.approve_plan(studio.propose_plan().id)
            draft = studio.draft()
            repo.connection.execute(
                "CREATE TRIGGER fail_accept BEFORE INSERT ON reviews WHEN NEW.decision='accepted' "
                "BEGIN SELECT RAISE(ABORT,'injected acceptance failure'); END"
            )
            with self.assertRaises(sqlite3.IntegrityError):
                studio.accept(draft.id)
            self.assertEqual(studio.status()["next_episode"], 1)
            self.assertEqual(studio.status()["history_revision"], 0)
            self.assertEqual(repo.pending().id, draft.id)
            self.assertEqual(repo.accepted(), [])
            self.assertEqual(repo.connection.execute("SELECT count(*) FROM memory_sources").fetchone()[0], 0)

    def test_unknown_usage_keeps_reservation_after_fresh_process(self):
        import json
        import subprocess
        import sys
        from serial_story.budget import SQLiteBudget
        from serial_story.records import StoryError
        Repository, _ = self.load_api()
        with self.temporary_directory() as folder:
            db = Path(folder) / "story.db"
            with Repository(db) as repo:
                budget = SQLiteBudget(repo, max_calls=5, cap_micro_usd=7)
                first = budget.reserve(1, "writer", max_charge=4)
                budget.settle(first, actual_charge=3, latency_ms=1)
                budget.settle(first, actual_charge=3, latency_ms=1)
                second = budget.reserve(1, "checker", max_charge=4)
                budget.mark_uncertain(second, latency_ms=2)
                with self.assertRaises(StoryError):
                    budget.reserve(1, "memory", max_charge=1)
                with self.assertRaises(StoryError):
                    budget.settle(first, actual_charge=2, latency_ms=1)
            script = (
                "import sys,json; from pathlib import Path; "
                "from serial_story.repository import SQLiteRepository; "
                "from serial_story.budget import SQLiteBudget; "
                "repo=SQLiteRepository(Path(sys.argv[1])); "
                "print(json.dumps(SQLiteBudget(repo).snapshot(1)))"
            )
            child = subprocess.run([sys.executable, "-c", script, str(db)], capture_output=True, text=True, check=True)
            snapshot = json.loads(child.stdout)
            self.assertEqual(snapshot["spent_micro_usd"], 3)
            self.assertEqual(snapshot["reserved_micro_usd"], 4)
            self.assertEqual(snapshot["unresolved"], 1)
            self.assertEqual(snapshot["cap_micro_usd"], 7)
            self.assertEqual(snapshot["max_calls"], 5)

    def test_timeout_stops_regeneration_without_making_canon(self):
        from serial_story.provider import FakeProvider
        from serial_story.records import StoryError
        class TimeoutFixture(FakeProvider):
            def draft(self, context):
                raise TimeoutError("Injected offline timeout, no network")
        Repository, Service = self.load_api()
        with self.temporary_directory() as folder:
            db = Path(folder) / "story.db"
            with Repository(db) as repo:
                studio = Service(repo, provider=TimeoutFixture())
                studio.initialize("A map opens a door.")
                studio.approve_plan(studio.propose_plan().id)
                with self.assertRaises(TimeoutError):
                    studio.draft()
                self.assertEqual(repo.accepted(), [])
                self.assertIsNone(repo.pending())
            with Repository(db) as repo:
                studio = Service(repo)
                self.assertEqual(studio.status()["budget"]["unresolved"], 1)
                with self.assertRaises(StoryError):
                    studio.draft()

    def test_export_never_overwrites_different_existing_work(self):
        from serial_story.cli import export_without_overwrite
        from serial_story.records import StoryError
        with self.temporary_directory() as folder:
            path = Path(folder) / "existing.txt"
            path.write_text("Existing human work", encoding="utf-8")
            with self.assertRaises(StoryError):
                export_without_overwrite(path, "Different output")
            self.assertEqual(path.read_text(encoding="utf-8"), "Existing human work")


    def test_failed_export_leaves_no_partial_destination_and_can_retry(self):
        from unittest.mock import patch
        from serial_story.cli import export_without_overwrite
        with self.temporary_directory() as folder:
            path = Path(folder) / "episode.txt"
            original_open = Path.open
            class FailAfterPartialWrite:
                def __init__(self, stream):
                    self.stream = stream
                def __enter__(self):
                    return self
                def __exit__(self, *args):
                    return self.stream.__exit__(*args)
                def write(self, text):
                    self.stream.write(text[:4])
                    self.stream.flush()
                    raise OSError("Injected local write failure")
            def failing_open(target, mode="r", *args, **kwargs):
                stream = original_open(target, mode, *args, **kwargs)
                return FailAfterPartialWrite(stream) if mode == "x" else stream
            with patch.object(Path, "open", failing_open):
                with self.assertRaises(OSError):
                    export_without_overwrite(path, "Complete story text")
            self.assertFalse(path.exists(), "Failure must not publish a partial export")
            export_without_overwrite(path, "Complete story text")
            self.assertEqual(path.read_text(encoding="utf-8"), "Complete story text")
            self.assertEqual(sorted(p.name for p in Path(folder).iterdir()), ["episode.txt"])


    def test_identical_export_retries_preserve_lf_and_crlf(self):
        from serial_story.cli import export_without_overwrite
        from serial_story.records import StoryError
        with self.temporary_directory() as folder:
            for name, text in [("lf", "First line\nSecond line\n"),
                               ("crlf", "First line\r\nSecond line\r\n")]:
                with self.subTest(newlines=name):
                    path = Path(folder) / (name + ".txt")
                    export_without_overwrite(path, text)
                    try:
                        export_without_overwrite(path, text)
                    except StoryError as error:
                        self.fail(f"An identical export must be idempotent: {error}")
                    self.assertEqual(path.read_bytes(), text.encode("utf-8"))


if __name__ == "__main__":
    unittest.main()
