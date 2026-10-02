import random
import time
import unittest

import solver

BOARD = ["?"] * 18 + ["2", "A", "3", "7", "9", "J", "5", "3", "9", "3"]


def game():
    return solver.Game(list(BOARD), "K", False, 23)


class TimeBudgetTests(unittest.TestCase):
    def test_default_is_unchanged(self):
        rec = solver.best_move(game(), 300, random.Random(1))
        self.assertEqual(rec.position, 20)
        self.assertAlmostEqual(rec.success_rate, 0.21333333333333335)
        self.assertEqual(rec.simulations, 300)

    def test_budget_stops_early_and_reports_runs(self):
        started = time.monotonic()
        rec = solver.best_move(game(), 100000, random.Random(1), time_budget=0.3)
        self.assertLess(time.monotonic() - started, 3)
        self.assertGreaterEqual(rec.simulations, solver.MIN_BUDGET_SIMULATIONS)
        self.assertLess(rec.simulations, 100000)
        self.assertFalse(rec.is_proven)

    def test_tiny_budget_still_gives_minimum_runs(self):
        rec = solver.best_move(game(), 1000, random.Random(1), time_budget=1e-9)
        self.assertEqual(rec.simulations, solver.MIN_BUDGET_SIMULATIONS)

    def test_invalid_budget_rejected(self):
        with self.assertRaises(ValueError):
            solver.best_move(game(), 10, random.Random(1), time_budget=0)

    def test_estimate_matches_probability(self):
        rate, runs = solver.estimate(game(), 20, 50, random.Random(3))
        self.assertEqual(runs, 50)
        self.assertEqual(rate, solver.probability(game(), 20, 50, random.Random(3)))


if __name__ == "__main__":
    unittest.main()
