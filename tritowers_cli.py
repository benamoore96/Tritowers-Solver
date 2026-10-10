"""CLI presentation helpers for Tritowers Solver.

Reproduced locally from Alex Kendall's validated CLI/usability workstream report
because its patch could not cross the peer channel. Rules remain in ``solver``.

Use ``python solver.py --input deal.json --non-interactive --seed 1`` for one
JSON recommendation without changing the deal. The file must contain exactly
``board`` (28 rank strings, "?" unknown or "--" removed), ``waste`` (rank),
``stock_known`` (boolean), and ``stock`` (ordered ranks if known, else count).
Non-interactive mode requires every live tableau rank to be known. Interactive
mode accepts unknown cards, requests reveals, and supports confirmed actions
with undo/quit. At rank prompts use the word "quit", since Q is a queen.

"""

import argparse
import json
import random
import sys
from pathlib import Path
from dataclasses import dataclass, field

import solver


def build_parser():
    parser = argparse.ArgumentParser(description="Interactive rank-only TriTowers solver")
    parser.add_argument("--seed", type=int, help="make sampled recommendations reproducible")
    parser.add_argument(
        "--simulations", type=positive_int, default=solver.SIMULATIONS,
        help=f"simulations per candidate (default: {solver.SIMULATIONS})",
    )
    parser.add_argument("--skip-tutorial", action="store_true", help="skip the startup tutorial")
    parser.add_argument("--input", type=Path, help="JSON deal: board, waste, stock_known, stock")
    parser.add_argument("--non-interactive", action="store_true",
                        help="print one JSON recommendation; requires --input with no unknown tableau")
    return parser


def positive_int(value):
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def format_board(game):
    """Render all positions without reaching into solver decision logic."""
    state = game.state_snapshot()

    def card(position):
        if position in state["removed"]:
            return "--"
        return state["board"][position - 1]

    rows = (
        (1, 2, 3),
        (4, 5, 6, 7, 8, 9),
        tuple(range(10, 19)),
        tuple(range(19, 29)),
    )
    rendered = [" ".join(f"{position:02d}:{card(position):>2}" for position in row) for row in rows]
    rendered.append(
        f"Waste: {state['waste']} | Tableau: {state['remaining']} | "
        f"Stock: {state['stock_remaining']}"
    )
    return "\n".join(rendered)


@dataclass
class UndoHistory:
    """CLI-owned state history; engine mutations remain validated."""

    _states: list = field(default_factory=list)

    def checkpoint(self, game):
        self._states.append(game.copy())

    def can_undo(self):
        return bool(self._states)

    def undo(self):
        if not self._states:
            raise ValueError("Nothing to undo.")
        return self._states.pop()


def read_rank_or_command(prompt, input_fn=input):
    """Read a rank while handling EOF and reserved CLI commands cleanly."""
    try:
        raw = input_fn(prompt).strip()
    except EOFError as error:
        raise SystemExit("Input ended; solver stopped without changing the next move.") from error
    command = raw.lower()
    if command in {"undo", "u"}:
        return "UNDO"
    if command in {"quit", "q", "exit"}:
        return "QUIT"
    return solver.normalize(raw)


def load_game(path):
    """Load a fresh deal, not a history snapshot, through engine validation."""
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as error:
        raise ValueError(f"Cannot read JSON deal: {error}") from error
    if not isinstance(data, dict):
        raise ValueError("Deal must be a JSON object.")
    required = {"board", "waste", "stock_known", "stock"}
    if set(data) != required:
        raise ValueError("Deal needs exactly board, waste, stock_known and stock.")
    if not isinstance(data["board"], list) or not all(isinstance(c, str) for c in data["board"]):
        raise ValueError("Board must be a list of rank strings.")
    if not isinstance(data["waste"], str) or type(data["stock_known"]) is not bool:
        raise ValueError("Waste must be a rank string; stock_known must be a boolean.")
    if data["stock_known"] and (not isinstance(data["stock"], list) or
                               not all(isinstance(c, str) for c in data["stock"])):
        raise ValueError("Known stock must be a list of rank strings.")
    return solver.Game(**data)


def recommendation_data(game, simulations, rng):
    """Return one action without changing the deal or implying proof from sampling."""
    if not game.remaining():
        return {"action": "win"}
    if not game.legal_moves():
        return {"action": "draw" if game.stock_remaining else "lost"}
    rec = solver.best_move(game, simulations=simulations, rng=rng)
    return {"action": "play", "position": rec.position,
            "rank": game.board[rec.position - 1], "evidence": rec.evidence.name,
            "success_rate": rec.success_rate, "simulations": rec.simulations}


def play_session(game, simulations, rng, input_fn=input, emit=print):
    """Confirm each action; undo restores all card counts and observations."""
    history = UndoHistory()
    while True:
        before = game.copy()
        try:
            emit(format_board(game))
            for position in game.exposed():
                if game.board[position - 1] == "?":
                    raw = input_fn(f"Position {position:02d} rank (undo/quit): ").strip()
                    if raw.lower() in {"undo", "u", "quit", "exit"}:
                        raise SessionCommand(raw.lower())
                    game.board[position - 1] = game.observe_rank(raw)
            if game.board != before.board:
                emit(format_board(game))
            action = recommendation_data(game, simulations, rng)
            if action["action"] in {"win", "lost"}:
                emit("WIN!" if action["action"] == "win" else "No playable cards; stock empty.")
                command = input_fn("undo to recover, Enter to finish (quit): ").strip().lower()
                if command not in {"undo", "u"}:
                    return before if command in {"quit", "q", "exit"} else game
            else:
                if action["action"] == "play":
                    emit(f"PLAY {action['rank']} @ {action['position']:02d} [{action['evidence']}]")
                else:
                    emit("DRAW")
                command = input_fn("Enter to confirm, undo, or quit: ").strip().lower()
            if command in {"quit", "q", "exit"}:
                return before
            if command in {"undo", "u"}:
                if history.can_undo():
                    game = history.undo()
                else:
                    game = before
                    emit("Nothing to undo.")
                continue
            if command not in {"", "play", "draw", "yes", "y"}:
                game = before
                emit("Use Enter to confirm, undo, or quit.")
                continue
            if action["action"] == "play":
                game.play(action["position"])
            else:
                if game.stock_known:
                    solver.draw(game, emit=emit)
                else:
                    raw = input_fn("DRAW rank (undo/quit): ").strip()
                    if raw.lower() in {"undo", "u", "quit", "exit"}:
                        raise SessionCommand(raw.lower())
                    game.observe_draw(raw)
            history.checkpoint(before)
        except SessionCommand as command:
            game = before
            if str(command) in {"quit", "q", "exit"}:
                return game
            if history.can_undo():
                game = history.undo()
            else:
                emit("Nothing to undo.")
        except ValueError as error:
            game = before
            emit(f"Invalid input: {error}")


class SessionCommand(Exception):
    """An explicit user command at a rank prompt, never a card rank."""


def run(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.non_interactive and not args.input:
        parser.error("--non-interactive requires --input")
    try:
        game = load_game(args.input) if args.input else None
    except ValueError as error:
        parser.error(str(error))
    if args.non_interactive:
        if "?" in game.board:
            parser.error("--non-interactive needs known or removed tableau cards, not ?")
        print(json.dumps(recommendation_data(game, args.simulations, random.Random(args.seed))))
        return
    if not args.skip_tutorial:
        print("Confirm each recommendation with Enter. Use undo to restore the previous action, or quit.")
    if game is None:
        game = solver.setup()
    play_session(game, args.simulations, random.Random(args.seed))


if __name__ == "__main__":
    try:
        run()
    except EOFError:
        print("Input ended; solver stopped.", file=sys.stderr)
        raise SystemExit(1)
    except KeyboardInterrupt:
        print("Solver stopped.", file=sys.stderr)
        raise SystemExit(130)
