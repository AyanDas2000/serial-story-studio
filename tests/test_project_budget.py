import tempfile
import unittest
from pathlib import Path

from serial_story.budget import SQLiteBudget
from serial_story.records import StoryError
from serial_story.repository import SQLiteRepository


class ProjectBudgetTest(unittest.TestCase):
    def test_all_episode_and_stage_spending_shares_a_persistent_project_cap(self):
        root = Path(__file__).resolve().parents[1] / 'local' / 'test-runs'
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as folder:
            db = Path(folder) / 'story.db'
            with SQLiteRepository(db) as repo:
                budget = SQLiteBudget(repo, max_calls=10, cap_micro_usd=1_000_000)
                first = budget.reserve(0, 'overall-plan', max_charge=600_000)
                budget.settle(first, actual_charge=600_000, latency_ms=1)
                second = budget.reserve(1, 'writer', max_charge=350_000)
                budget.settle(second, actual_charge=350_000, latency_ms=1)
                with self.assertRaises(StoryError, msg='A fresh episode must not reset the project dollar ceiling'):
                    budget.reserve(2, 'reviewer', max_charge=100_000)
                third = budget.reserve(2, 'memory', max_charge=50_000)
                budget.mark_uncertain(third, latency_ms=1)
            with SQLiteRepository(db) as repo:
                budget = SQLiteBudget(repo, max_calls=99, cap_micro_usd=1_000_000)
                project = budget.project_snapshot()
                self.assertEqual(project['spent_micro_usd'], 950_000)
                self.assertEqual(project['reserved_micro_usd'], 50_000)
                self.assertEqual(project['remaining_micro_usd'], 0)
                self.assertEqual(project['cap_micro_usd'], 1_000_000)
                with self.assertRaises(StoryError):
                    budget.reserve(3, 'retry', max_charge=0)


    def test_fractional_negative_and_over_ceiling_amounts_are_refused(self):
        root = Path(__file__).resolve().parents[1] / 'local' / 'test-runs'
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as folder, SQLiteRepository(Path(folder) / 'story.db') as repo:
            budget = SQLiteBudget(repo, cap_micro_usd=1_000_000)
            for amount in (0.5, True, -1):
                with self.subTest(amount=amount), self.assertRaises(StoryError):
                    budget.reserve(1, 'writer', max_charge=amount)
            with self.assertRaises(StoryError):
                SQLiteBudget(repo, project_cap_micro_usd=1_000_001)
            call = budget.reserve(1, 'writer', max_charge=10)
            with self.assertRaises(StoryError):
                budget.settle(call, actual_charge=0.5, latency_ms=1)
            with self.assertRaises(StoryError):
                budget.mark_uncertain(call, latency_ms=-1)
            self.assertEqual(budget.project_snapshot()['reserved_micro_usd'], 10)


if __name__ == '__main__':
    unittest.main()
