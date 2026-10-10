import argparse
import unittest
import subprocess
import sys
from unittest.mock import patch
import json
import random
import tempfile
from pathlib import Path

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
    def session(self, game, commands):
        lines = iter(commands)
        output = []
        result = cli.play_session(game, 1, random.Random(1),
                                  input_fn=lambda _: next(lines), emit=output.append)
        return result, "\n".join(output)

    def game(self, rank="2", stock=None):
        board = ["--"] * 28
        board[18] = rank
        return solver.Game(board, "A", True, [] if stock is None else stock)

    def test_session_quit_does_not_apply_recommendation(self):
        result, text = self.session(self.game(), ["quit"])
        self.assertEqual(result.remaining(), 1)
        self.assertIn("19: 2", text)
        self.assertIn("PLAY 2 @ 19", text)

    def test_session_confirm_then_undo_restores_waste_and_counts(self):
        original = self.game()
        result, text = self.session(original.copy(), ["", "undo", "quit"])
        self.assertEqual(result.state_snapshot(), original.state_snapshot())
        self.assertEqual(result.seen_counts, original.seen_counts)
        self.assertIn("WIN!", text)

    def test_known_draw_can_be_undone(self):
        original = self.game("5", ["3"])
        result, _ = self.session(original.copy(), ["", "undo", "quit"])
        self.assertEqual(result.state_snapshot(), original.state_snapshot())
        self.assertEqual(result.seen_counts, original.seen_counts)

    def test_reveal_and_play_undo_restores_unseen_pool(self):
        original = self.game("?")
        result, _ = self.session(original.copy(), ["2", "", "undo", "quit"])
        self.assertEqual(result.state_snapshot(), original.state_snapshot())
        self.assertEqual(result.seen_counts, original.seen_counts)

    def test_unknown_draw_can_be_undone(self):
        game = self.game("5")
        game.stock_known, game.stock = False, 1
        original = game.copy()
        result, _ = self.session(game, ["", "3", "undo", "quit"])
        self.assertEqual(result.state_snapshot(), original.state_snapshot())
        self.assertEqual(result.seen_counts, original.seen_counts)

    def test_queen_is_a_rank_at_reveal_not_quit(self):
        result, _ = self.session(self.game("?"), ["Q", "quit"])
        # Quitting before an action rolls back newly entered observations too.
        self.assertEqual(result.board[18], "?")
        self.assertEqual(result.seen_counts["Q"], 0)

    def test_bad_rank_rolls_back_before_retry(self):
        original = self.game("?")
        result, text = self.session(original.copy(), ["nonsense", "quit"])
        self.assertEqual(result.state_snapshot(), original.state_snapshot())
        self.assertIn("Invalid input", text)

    def test_json_entry_point_emits_only_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "deal.json"
            game = self.game()
            path.write_text(json.dumps(dict(board=game.board, waste=game.waste,
                                            stock_known=True, stock=[])))
            result = subprocess.run([sys.executable, solver.__file__, "--input", str(path),
                                     "--non-interactive", "--simulations", "1", "--seed", "4"],
                                    text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            self.assertEqual((data["action"], data["position"]), ("play", 19))
            self.assertEqual(data["evidence"], "PROVEN")

    def test_json_rejects_malformed_shapes_and_impossible_deals(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "deal.json"
            for data in [[], {}, dict(board=["A"]*28, waste="A", stock_known=True, stock=[]),
                         dict(board=[1]*28, waste="A", stock_known=True, stock=[])]:
                path.write_text(json.dumps(data))
                with self.subTest(data=data):
                    with self.assertRaises(ValueError):
                        cli.load_game(path)

    def test_noninteractive_requires_input(self):
        with self.assertRaises(SystemExit):
            cli.run(["--non-interactive"])

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
