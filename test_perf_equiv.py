import random, unittest
import solver


def reference_move_score(game, position):
    """The original copying implementation, kept as the behavioural reference."""
    before_exposed = set(game.exposed())
    child = game.copy()
    child.play(position)
    newly_exposed = set(child.exposed()) - before_exposed
    score = 0
    for exposed_position in newly_exposed:
        card = child.board[exposed_position - 1]
        if card == "?":
            score += 20
        else:
            score += 10
            if solver.can_play(card, child.waste):
                score += 8
    score += sum(
        position in blockers
        for covered, blockers in solver.BLOCKERS.items()
        if covered not in child.removed
    )
    return score


class PerformanceRefactorEquivalence(unittest.TestCase):
    def test_move_score_matches_copying_reference(self):
        rng = random.Random(7)
        checked = 0
        for _ in range(300):
            board = ["?"] * 28
            for i in range(18, 28):
                board[i] = rng.choice(solver.RANKS)
            for i in rng.sample(range(18), 6):
                board[i] = rng.choice(solver.RANKS)
            counts = {}
            for card in board + ["5"]:
                counts[card] = counts.get(card, 0) + 1
            if any(n > 4 for card, n in counts.items() if card != "?"):
                continue
            game = solver.Game(board, "5", False, 23)
            for _ in range(rng.randint(0, 6)):
                moves = game.legal_moves()
                if not moves:
                    break
                game.play(rng.choice(moves))
            for position in game.legal_moves():
                self.assertEqual(
                    solver.move_score(game, position),
                    reference_move_score(game, position),
                )
                checked += 1
        self.assertGreater(checked, 100)

    def test_seeded_recommendation_is_unchanged(self):
        # Value recorded from the pre-refactor implementation on main (e6fe284).
        board = ["?"] * 18 + ["2", "A", "3", "7", "9", "J", "5", "3", "9", "3"]
        rec = solver.best_move(solver.Game(board, "K", False, 23), 300, random.Random(1))
        self.assertEqual(rec.position, 20)
        self.assertAlmostEqual(rec.success_rate, 0.21333333333333335)

    def test_layout_constants_account_for_deck(self):
        self.assertEqual(
            solver.TOTAL_TABLEAU + solver.TOTAL_WASTE + solver.TOTAL_STOCK,
            solver.TOTAL_CARDS,
        )

    def test_covered_by_is_inverse_of_blockers(self):
        for covered, blockers in solver.BLOCKERS.items():
            for blocker in blockers:
                self.assertIn(covered, solver.COVERED_BY[blocker])
