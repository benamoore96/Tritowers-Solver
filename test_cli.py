import argparse
import unittest
import subprocess
import sys
from unittest.mock import patch

import solver
import tritowers_cli as cli


class CliTests(unittest.TestCase):
    def test_cli_internal_errors_keep_their_traceback(self):
        with patch.object(solver, "main", side_effect=RuntimeError("regression")):
            with self.assertRaisesRegex(RuntimeError, "regression"):
                solver.run_cli()

    def test_cli_expected_stops_return_failure_codes(self):
        for error, code in [(EOFError(), 1), (KeyboardInterrupt(), 130)]:
            with self.subTest(error=type(error).__name__):
                with patch.object(solver, "main", side_effect=error):
                    with patch("sys.stderr"):
                        self.assertEqual(solver.run_cli(), code)

    def test_cli_success_returns_zero(self):
        with patch.object(solver, "main"):
            self.assertEqual(solver.run_cli(), 0)

    def test_script_eof_is_nonzero_and_explained(self):
        result = subprocess.run([sys.executable, solver.__file__], input="",
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Input ended; solver stopped.", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

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
