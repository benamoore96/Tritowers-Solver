import unittest

from tools import heuristic_baseline as hb


class HeuristicBaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = hb.evaluate(1500, seed=11)

    def test_move_score_beats_random_by_a_clear_margin(self):
        score = self.results["move_score_argmax"][0]
        rand = self.results["random_legal"][0]
        self.assertGreater(score - rand, 0.08)

    def test_move_score_beats_top_first(self):
        self.assertGreater(
            self.results["move_score_argmax"][0],
            self.results["first_legal (top first)"][0] + 0.10,
        )

    def test_same_seed_is_reproducible(self):
        again = hb.evaluate(200, seed=5)
        self.assertEqual(again, hb.evaluate(200, seed=5))

    def test_every_deal_is_a_legal_52_card_game(self):
        import random
        board, waste, stock = hb.deal(random.Random(1))
        self.assertEqual(len(board) + 1 + len(stock), 52)


if __name__ == "__main__":
    unittest.main()
