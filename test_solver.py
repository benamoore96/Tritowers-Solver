import unittest
from unittest.mock import patch

import solver


class CardAccountingTests(unittest.TestCase):
    def test_played_tableau_card_stays_consumed(self):
        board = ["?"] * solver.TOTAL_TABLEAU
        board[18:21] = ["A", "A", "A"]
        game = solver.Game(board, "K", False, solver.TOTAL_STOCK)
        self.assertEqual(game.unknown_counts()["A"], 1)
        game.play(19)
        self.assertEqual(game.unknown_counts()["A"], 1)

    def test_observed_draw_stays_consumed_after_next_draw(self):
        game = solver.Game(["?"] * solver.TOTAL_TABLEAU, "A", False, 2)
        game.observe_draw("2")
        game.observe_draw("3")
        self.assertEqual(game.unknown_counts()["2"], 3)
        self.assertEqual(game.unknown_counts()["3"], 3)

    def test_fifth_copy_is_rejected_when_revealed(self):
        board = ["?"] * solver.TOTAL_TABLEAU
        board[18:21] = ["A", "A", "A"]
        game = solver.Game(board, "A", False, solver.TOTAL_STOCK)
        with self.assertRaises(ValueError):
            game.observe_rank("A")

    def test_simulated_unknown_sampling_consumes_card(self):
        game = solver.Game(["?"] * solver.TOTAL_TABLEAU, "A", False, 2)
        with patch("solver.random.choice", return_value="2"):
            self.assertEqual(game.sample_unknown_card(), "2")
        self.assertEqual(game.unknown_counts()["2"], 3)


class GuaranteeTests(unittest.TestCase):
    def test_nonwinning_legal_move_is_not_guaranteed(self):
        board = ["?"] * solver.TOTAL_TABLEAU
        board[18] = "2"
        game = solver.Game(board, "A", False, solver.TOTAL_STOCK)
        self.assertEqual(game.legal_moves(), [19])
        self.assertEqual(solver.guaranteed_moves(game), [])

    def test_immediate_win_is_guaranteed(self):
        board = ["--"] * solver.TOTAL_TABLEAU
        board[18] = "2"
        game = solver.Game(board, "A", False, 0)
        self.assertEqual(solver.guaranteed_moves(game), [19])


class RecommendationTests(unittest.TestCase):
    def test_sampled_one_hundred_percent_is_not_called_proven(self):
        board = ["?"] * solver.TOTAL_TABLEAU
        board[18] = "2"
        game = solver.Game(board, "A", False, 1)
        with patch("solver.probability", return_value=1.0):
            recommendation = solver.best_move(game, simulations=7)
        self.assertEqual(recommendation.evidence, solver.Evidence.SAMPLED)
        self.assertEqual(recommendation.success_rate, 1.0)
        self.assertEqual(recommendation.simulations, 7)

    def test_immediate_win_recommendation_is_proven(self):
        board = ["--"] * solver.TOTAL_TABLEAU
        board[18] = "2"
        game = solver.Game(board, "A", False, 0)
        recommendation = solver.best_move(game, simulations=7)
        self.assertEqual(recommendation.evidence, solver.Evidence.PROVEN)
        self.assertEqual(recommendation.simulations, 0)

    def test_probability_rejects_nonpositive_budget(self):
        board = ["?"] * solver.TOTAL_TABLEAU
        board[18] = "2"
        game = solver.Game(board, "A", False, 1)
        with self.assertRaises(ValueError):
            solver.probability(game, 19, simulations=0)

    def test_seeded_recommendation_is_reproducible(self):
        board = ["?"] * solver.TOTAL_TABLEAU
        board[18:20] = ["2", "K"]
        left = solver.best_move(game=solver.Game(board, "A", False, 3), simulations=20, rng=solver.random.Random(4))
        right = solver.best_move(game=solver.Game(board, "A", False, 3), simulations=20, rng=solver.random.Random(4))
        self.assertEqual(left, right)


class CopyTests(unittest.TestCase):
    def test_copy_does_not_double_count_played_card_as_waste(self):
        board = ["?"] * solver.TOTAL_TABLEAU
        board[18:22] = ["7", "7", "7", "7"]
        game = solver.Game(board, "A", False, 1)
        game.waste = "8"
        game.play(19)
        clone = game.copy()
        self.assertEqual(clone.seen_counts["7"], 4)
        self.assertEqual(clone.waste, "7")


class StructureTests(unittest.TestCase):
    def test_blockers_are_valid_and_acyclic(self):
        self.assertEqual(set(solver.BLOCKERS), set(range(1, 19)))
        for position, blockers in solver.BLOCKERS.items():
            self.assertEqual(len(blockers), 2)
            self.assertEqual(len(set(blockers)), 2)
            self.assertTrue(all(position < blocker <= solver.TOTAL_TABLEAU for blocker in blockers))

    def test_initially_only_bottom_row_is_exposed(self):
        board = [solver.RANKS[index % len(solver.RANKS)] for index in range(solver.TOTAL_TABLEAU)]
        game = solver.Game(board, "K", False, solver.TOTAL_STOCK)
        self.assertEqual(game.exposed(), list(range(19, 29)))

    def test_each_nonbottom_card_exposes_after_its_two_blockers_removed(self):
        board = [solver.RANKS[index % len(solver.RANKS)] for index in range(solver.TOTAL_TABLEAU)]
        for position, blockers in solver.BLOCKERS.items():
            game = solver.Game(board, "K", False, solver.TOTAL_STOCK)
            game.removed.update(blockers)
            self.assertIn(position, game.exposed())


class PlayValidationTests(unittest.TestCase):
    def test_rejects_unexposed_position(self):
        board = [solver.RANKS[index % len(solver.RANKS)] for index in range(solver.TOTAL_TABLEAU)]
        game = solver.Game(board, "K", False, solver.TOTAL_STOCK)
        with self.assertRaises(ValueError):
            game.play(1)

    def test_rejects_nonadjacent_rank(self):
        board = ["?"] * solver.TOTAL_TABLEAU
        board[18] = "5"
        game = solver.Game(board, "A", False, solver.TOTAL_STOCK)
        with self.assertRaises(ValueError):
            game.play(19)

    def test_rejects_already_removed_position(self):
        board = ["--"] * solver.TOTAL_TABLEAU
        board[18] = "2"
        game = solver.Game(board, "A", False, 0)
        game.play(19)
        with self.assertRaises(ValueError):
            game.play(19)


class MoveScoreTests(unittest.TestCase):
    def test_unrelated_exposed_cards_do_not_change_candidate_score(self):
        first = ["?"] * solver.TOTAL_TABLEAU
        first[18:21] = ["2", "5", "7"]
        second = first.copy()
        second[19:21] = ["9", "Q"]
        game_a = solver.Game(first, "A", False, 1)
        game_b = solver.Game(second, "A", False, 1)
        self.assertEqual(solver.move_score(game_a, 19), solver.move_score(game_b, 19))

    def test_newly_exposed_playable_card_scores_above_blocked_card(self):
        # Position 10 is exposed by removing 19 and 20. Playing 2 makes 3 an
        # immediate continuation, while 7 is known but blocked.
        playable = ["?"] * solver.TOTAL_TABLEAU
        playable[9] = "3"
        playable[18:20] = ["2", "K"]
        blocked = playable.copy()
        blocked[9] = "7"
        game_playable = solver.Game(playable, "A", False, 1)
        game_blocked = solver.Game(blocked, "A", False, 1)
        game_playable.removed.add(20)
        game_blocked.removed.add(20)
        self.assertGreater(
            solver.move_score(game_playable, 19),
            solver.move_score(game_blocked, 19),
        )


class CliCompatibilityTests(unittest.TestCase):
    def test_validate_deal_preserves_ordered_known_stock(self):
        board, waste, known, stock = solver.validate_deal(
            ["?"] * solver.TOTAL_TABLEAU, "a", True, ["2", "K"]
        )
        self.assertEqual(waste, "A")
        self.assertTrue(known)
        self.assertEqual(stock, ["2", "K"])
        self.assertEqual(len(board), solver.TOTAL_TABLEAU)

    def test_validate_deal_rejects_bad_unknown_stock_count(self):
        with self.assertRaises(ValueError):
            solver.validate_deal(["?"] * solver.TOTAL_TABLEAU, "A", False, -1)

    def test_validate_deal_rejects_unknown_slots_beyond_unseen_pool(self):
        known_board = (list(solver.RANKS) * 3)[:solver.TOTAL_TABLEAU]
        for board, stock_known, stock in (
            (known_board, False, 24),
            (["?"] * solver.TOTAL_TABLEAU, False, 53),
            (["?"] * solver.TOTAL_TABLEAU, False, 24),
            (["?"] * solver.TOTAL_TABLEAU, True, list(solver.RANKS) * 2),
        ):
            with self.subTest(stock_known=stock_known, stock=stock):
                with self.assertRaisesRegex(ValueError, "Unknown cards exceed"):
                    solver.validate_deal(board, "A", stock_known, stock)

    def test_validate_deal_accepts_exact_unseen_capacity(self):
        known_board = (list(solver.RANKS) * 3)[:solver.TOTAL_TABLEAU]
        for board, stock_known, stock in (
            (known_board, False, 23),
            (["?"] * solver.TOTAL_TABLEAU, False, 23),
            (["?"] * solver.TOTAL_TABLEAU, True, (list(solver.RANKS) * 2)[:23]),
        ):
            with self.subTest(stock_known=stock_known):
                self.assertEqual(
                    solver.validate_deal(board, "A", stock_known, stock)[3], stock
                )

    def test_reveal_unknowns_stores_normalized_rank(self):
        board = ["?"] * solver.TOTAL_TABLEAU
        board[19:28] = ["3", "4", "5", "6", "7", "8", "9", "10", "J"]
        game = solver.Game(board, "A", False, 1)
        solver.reveal_unknowns(game, read_card=lambda _: "k")
        self.assertEqual(game.board[18], "K")
        self.assertEqual(game.seen_counts["K"], 1)
        self.assertIn(19, game.legal_moves())

    def test_snapshot_is_stable_and_does_not_alias_state(self):
        game = solver.Game(["?"] * solver.TOTAL_TABLEAU, "A", False, 4)
        snapshot = game.state_snapshot()
        self.assertIsInstance(snapshot["board"], tuple)
        self.assertIsInstance(snapshot["removed"], frozenset)
        self.assertEqual(snapshot["stock_remaining"], 4)
        self.assertEqual(snapshot["remaining"], solver.TOTAL_TABLEAU)

    def test_reveal_unknowns_accepts_cli_reader(self):
        board = ["?"] * solver.TOTAL_TABLEAU
        board[19:28] = ["3", "4", "5", "6", "7", "8", "9", "10", "J"]
        game = solver.Game(board, "K", False, 1)
        prompts = []
        solver.reveal_unknowns(game, read_card=lambda prompt: prompts.append(prompt) or "A")
        self.assertEqual(game.board[18], "A")
        self.assertEqual(prompts, ["Position 19: "])

    def test_draw_accepts_cli_io_delegates(self):
        game = solver.Game(["?"] * solver.TOTAL_TABLEAU, "A", False, 1)
        output = []
        self.assertTrue(solver.draw(game, read_card=lambda _: "2", emit=output.append))
        self.assertEqual(game.waste, "2")
        self.assertEqual(game.stock_remaining, 0)

    def test_recommendation_legacy_adapter_is_explicit(self):
        rec = solver.Recommendation(19, 1.0, solver.Evidence.SAMPLED, 10)
        self.assertEqual(rec.as_legacy_tuple(), (19, 1.0))
        self.assertFalse(rec.is_proven)


if __name__ == "__main__":
    unittest.main()
