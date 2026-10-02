import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import solver

MID_GAME = " ".join(["?"] * 17 + ["--"] + ["2", "A", "3", "7", "9", "J", "5", "3", "9", "3"])
FRESH = " ".join(["?"] * 18 + ["2", "A", "3", "7", "9", "J", "5", "3", "9", "3"])


def run_setup(answers):
    with patch("builtins.input", side_effect=answers), redirect_stdout(io.StringIO()):
        return solver.setup()


class ReadStockCountTests(unittest.TestCase):
    def test_retries_until_valid(self):
        said = []
        answers = iter(["abc", "-1", "24", " 9 "])
        self.assertEqual(solver.read_stock_count(lambda _: next(answers), said.append), 9)
        self.assertEqual(len(said), 3)

    def test_accepts_bounds(self):
        self.assertEqual(solver.read_stock_count(lambda _: "0", print), 0)
        self.assertEqual(solver.read_stock_count(lambda _: "23", print), 23)


class SetupStockTests(unittest.TestCase):
    def test_fresh_deal_keeps_default_stock(self):
        game = run_setup(["1", "2", FRESH, "K"])
        self.assertEqual(game.stock_remaining, 23)

    def test_mid_game_entry_asks_for_stock(self):
        game = run_setup(["1", "2", MID_GAME, "K", "11"])
        self.assertEqual(game.stock_remaining, 11)


if __name__ == "__main__":
    unittest.main()
