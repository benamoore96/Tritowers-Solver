"""Full-information baseline for the move_score heuristic (issue #17, evidence only).

Deals random 52-card games with tableau, waste and stock order all known, then
plays each policy to the end. This measures how much the heuristic helps over
simple rules. It is NOT a tuning run and NOT the solver's unknown-stock play.

    python tools/heuristic_baseline.py --deals 10000 --seed 11
"""
import argparse
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import solver  # noqa: E402


def deal(rng):
    deck = [rank for rank in solver.RANKS for _ in range(solver.COPIES_PER_RANK)]
    rng.shuffle(deck)
    return deck[:28], deck[28], deck[29:]


def play_out(policy, rng):
    board, waste, stock = deal(rng)
    game = solver.Game(board, waste, True, stock)
    while True:
        if game.remaining() == 0:
            return True
        moves = game.legal_moves()
        if moves:
            game.play(policy(game, moves, rng))
        elif game.stock:
            game.waste = game.stock.pop(0)
        else:
            return False


POLICIES = {
    "first_legal (top first)": lambda g, m, r: min(m),
    "random_legal": lambda g, m, r: r.choice(m),
    "bottom_row_first": lambda g, m, r: max(m),
    "move_score_argmax": lambda g, m, r: max(m, key=lambda p: (solver.move_score(g, p), p)),
}


def evaluate(deals, seed, policies=POLICIES):
    """Return {name: (win_rate, 95% half-width)}; every policy sees the same seed."""
    results = {}
    for name, policy in policies.items():
        rng = random.Random(seed)
        wins = sum(play_out(policy, rng) for _ in range(deals))
        rate = wins / deals
        results[name] = (rate, 1.96 * math.sqrt(rate * (1 - rate) / deals))
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--deals", type=int, default=3000)
    parser.add_argument("--seed", type=int, default=11)
    args = parser.parse_args(argv)
    for name, (rate, half) in evaluate(args.deals, args.seed).items():
        print(f"{name:28s} {rate:.3f} +/- {half:.3f}")


if __name__ == "__main__":
    main()
