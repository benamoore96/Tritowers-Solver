import argparse
import unittest

import solver
import tritowers_cli as cli


class CliTests(unittest.TestCase):
    def test_parser_exposes_seed_budget_and_tutorial_switch(self):
        args = cli.build_parser().parse_args(["--seed", "4", "--simulations", "25", "--skip-tutorial"])
        self.assertEqual((args.seed, args.simulations, args.skip_tutorial), (4, 25, True))

    def test_parser_rejects_nonpositive_simulation_budget(self):
        with self.assertRaises(SystemExit):
            cli.build_parser().parse_args(["--simulations", "0"])

    def test_board_display_uses_snapshot_and_counts(self):
        board = ["?"] * solver.TOTAL_TABLEAU
        board[18] = "2"
        game = solver.Game(board, "A", False, 3)
        text = cli.format_board(game)
        self.assertIn("19: 2", text)
        self.assertIn("Waste: A", text)
        self.assertIn("Tableau: 28", text)
        self.assertIn("Stock: 3", text)

    def test_undo_returns_independent_prior_state(self):
        board = ["--"] * solver.TOTAL_TABLEAU
        board[18] = "2"
        game = solver.Game(board, "A", False, 0)
        history = cli.UndoHistory()
        history.checkpoint(game)
        game.play(19)
        restored = history.undo()
        self.assertEqual(restored.waste, "A")
        self.assertNotIn(19, restored.removed)

    def test_eof_is_clean_stop(self):
        def eof(_):
            raise EOFError
        with self.assertRaises(SystemExit):
            cli.read_rank_or_command("> ", input_fn=eof)

    def test_commands_are_distinct_from_card_ranks(self):
        self.assertEqual(cli.read_rank_or_command("> ", input_fn=lambda _: "undo"), "UNDO")
        self.assertEqual(cli.read_rank_or_command("> ", input_fn=lambda _: "q"), "QUIT")
        self.assertEqual(cli.read_rank_or_command("> ", input_fn=lambda _: "a"), "A")


if __name__ == "__main__":
    unittest.main()
