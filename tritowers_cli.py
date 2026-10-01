"""CLI presentation helpers for Tritowers Solver.

Reproduced locally from Alex Kendall's validated CLI/usability workstream report
because its patch could not cross the peer channel. Rules remain in ``solver``.
"""

import argparse
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
