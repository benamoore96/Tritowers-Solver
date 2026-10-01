"""
======================================================================
                         TRITOWERS SOLVER
======================================================================

A rank-only TriTowers solver.

CARD STRUCTURE
--------------

Standard 52-card deck:

    28 tableau cards
     1 waste card
    23 stock cards
    ----------------
    52 cards total

Suits are completely ignored.

There are four copies of every rank:

    A  2  3  4  5  6  7  8  9  10  J  Q  K


TABLEAU POSITIONS
-----------------

                         [01]       [02]       [03]

                    [04] [05]   [06] [07]   [08] [09]

               [10] [11] [12] [13] [14] [15] [16] [17] [18]

        [19] [20] [21] [22] [23] [24] [25] [26] [27] [28]


The bottom row is positions 19-28.


SOLVER BEHAVIOUR
----------------

1. Ask whether the complete tableau is known.

2. Ask whether the stock order is known.

3. Ask for the waste card.

4. Enter the known cards as quickly as possible.

5. If only the bottom row is known, upper cards are requested
   ONLY when they become exposed.

6. The solver looks for a guaranteed route first.

7. If no guaranteed route is available, it chooses the route
   with the highest estimated probability of success.

8. Solver moves require NO confirmation.

9. If the stock is unknown, the user only enters the card
   that actually appears when a draw occurs.

======================================================================
"""

import random
from collections import Counter
from dataclasses import dataclass
from enum import Enum


# ======================================================================
# SETTINGS
# ======================================================================

RANKS = (
    "A",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    "10",
    "J",
    "Q",
    "K",
)

VALUE = {
    rank: index + 1
    for index, rank in enumerate(RANKS)
}

COPIES_PER_RANK = 4

TOTAL_TABLEAU = 28
TOTAL_WASTE = 1
TOTAL_STOCK = 23
TOTAL_CARDS = 52

SIMULATIONS = 1200
MAX_SIMULATION_MOVES = 100

# In TriTowers, A and K are treated as adjacent.
ACE_WRAP = True


class Evidence(Enum):
    """What supports a move recommendation."""

    PROVEN = "proven"
    SAMPLED = "sampled"


@dataclass(frozen=True)
class Recommendation:
    position: int
    success_rate: float
    evidence: Evidence
    simulations: int = 0

    @property
    def is_proven(self):
        return self.evidence is Evidence.PROVEN

    def as_legacy_tuple(self):
        """Temporary adapter for old CLI code; never implies proof from 1.0."""
        return self.position, self.success_rate


# ======================================================================
# TABLEAU STRUCTURE
# ======================================================================

"""
The 28 cards are arranged as:

                         [01]       [02]       [03]

                    [04] [05]   [06] [07]   [08] [09]

               [10] [11] [12] [13] [14] [15] [16] [17] [18]

        [19] [20] [21] [22] [23] [24] [25] [26] [27] [28]


A card is exposed when BOTH cards covering it have been removed.

The three tower tops have two blockers each.

The second row has two blockers each.

The third row has two blockers each.

The bottom row has no blockers.
"""


# ----------------------------------------------------------------------
# BLOCKERS
#
# For each position, this gives the two cards directly beneath it
# which must BOTH be removed before the card is exposed.
# ----------------------------------------------------------------------

BLOCKERS = {

    # --------------------------------------------------------------
    # TOP OF TOWER 1
    # --------------------------------------------------------------

    1: (4, 5),

    # --------------------------------------------------------------
    # TOP OF TOWER 2
    # --------------------------------------------------------------

    2: (6, 7),

    # --------------------------------------------------------------
    # TOP OF TOWER 3
    # --------------------------------------------------------------

    3: (8, 9),

    # --------------------------------------------------------------
    # SECOND ROW - TOWER 1
    # --------------------------------------------------------------

    4: (10, 11),
    5: (11, 12),

    # --------------------------------------------------------------
    # SECOND ROW - TOWER 2
    # --------------------------------------------------------------

    6: (13, 14),
    7: (14, 15),

    # --------------------------------------------------------------
    # SECOND ROW - TOWER 3
    # --------------------------------------------------------------

    8: (16, 17),
    9: (17, 18),

    # --------------------------------------------------------------
    # THIRD ROW
    # --------------------------------------------------------------

    10: (19, 20),
    11: (20, 21),
    12: (21, 22),

    13: (22, 23),
    14: (23, 24),
    15: (24, 25),

    16: (25, 26),
    17: (26, 27),
    18: (27, 28),
}


# ======================================================================
# CARD FUNCTIONS
# ======================================================================

def normalize(card):
    """
    Convert input to a valid rank.
    """

    card = card.strip().upper()

    if card in ("?", "--"):
        return card

    if card not in RANKS:
        raise ValueError(
            f"Invalid card '{card}'. "
            f"Use A, 2-10, J, Q or K."
        )

    return card


def can_play(card, waste):
    """
    Determine whether 'card' can be played on 'waste'.
    """

    card_value = VALUE[card]
    waste_value = VALUE[waste]

    if abs(card_value - waste_value) == 1:
        return True

    if ACE_WRAP and {card_value, waste_value} == {1, 13}:
        return True

    return False


# ======================================================================
# STATE VALIDATION AND CLI MIGRATION SURFACE
# ======================================================================


def validate_board(board):
    """Return a normalized 28-card board or raise ``ValueError``."""
    if len(board) != TOTAL_TABLEAU:
        raise ValueError(f"Board must contain exactly {TOTAL_TABLEAU} positions.")
    normalized = [normalize(card) for card in board]
    return normalized


def validate_deal(board, waste, stock_known, stock):
    """Normalize and validate the complete known portion of a deal.

    This is the canonical entry point for CLIs and future UIs. Unknown stock is
    represented by a nonnegative count; known stock remains ordered.
    """
    board = validate_board(board)
    waste = normalize(waste)
    if waste not in RANKS:
        raise ValueError("Waste must have a known rank.")

    if stock_known:
        if not isinstance(stock, (list, tuple)):
            raise ValueError("Known stock must be an ordered sequence.")
        normalized_stock = [normalize(card) for card in stock]
        if any(card not in RANKS for card in normalized_stock):
            raise ValueError("Known stock cannot contain unknown or removed cards.")
        stock = normalized_stock
    else:
        if isinstance(stock, bool) or not isinstance(stock, int) or stock < 0:
            raise ValueError("Unknown stock must be a nonnegative card count.")

    counts = Counter(card for card in board if card in RANKS)
    counts[waste] += 1
    if stock_known:
        counts.update(stock)
    overfull = {rank: count for rank, count in counts.items() if count > COPIES_PER_RANK}
    if overfull:
        details = ", ".join(f"{rank}={count}" for rank, count in sorted(overfull.items()))
        raise ValueError(f"Impossible deck: {details}")
    if sum(counts.values()) > TOTAL_CARDS:
        raise ValueError("Known cards exceed a standard deck.")
    unknown_slots = board.count("?") + (0 if stock_known else stock)
    unseen_cards = TOTAL_CARDS - sum(counts.values())
    if unknown_slots > unseen_cards:
        raise ValueError("Unknown cards exceed the unseen standard-deck pool.")
    return board, waste, stock_known, stock


# ======================================================================
# GAME STATE
# ======================================================================

class Game:

    def __init__(
        self,
        board,
        waste,
        stock_known,
        stock
    ):

        board, waste, stock_known, stock = validate_deal(
            board, waste, stock_known, stock
        )
        self.board = board
        self.waste = waste
        self.stock_known = stock_known
        self.stock = list(stock) if stock_known else stock

        # Positions are 1-28.
        self.removed = {
            position
            for position, card in enumerate(self.board, start=1)
            if card == "--"
        }

        # Every observed card remains consumed even after it leaves the
        # tableau or is covered by a later waste card.
        self.seen_counts = Counter(
            card for card in self.board if card in RANKS
        )
        self.seen_counts[self.waste] += 1
        if self.stock_known:
            self.seen_counts.update(self.stock)
        self._validate_seen_counts()

    @property
    def stock_remaining(self):
        """Number of stock cards remaining, independent of stock mode."""
        return len(self.stock) if self.stock_known else self.stock

    def state_snapshot(self):
        """Stable read-only-shaped state for CLIs and display adapters."""
        return {
            "board": tuple(self.board),
            "removed": frozenset(self.removed),
            "waste": self.waste,
            "stock_known": self.stock_known,
            "stock": tuple(self.stock) if self.stock_known else self.stock,
            "stock_remaining": self.stock_remaining,
            "remaining": self.remaining(),
        }

    # ------------------------------------------------------------------
    # COPY
    # ------------------------------------------------------------------

    def copy(self):
        # Do not reconstruct through __init__: a played tableau card remains in
        # board for display while also becoming waste, so recounting would count
        # the same physical card twice. Copy the validated state directly.
        new_game = object.__new__(Game)
        new_game.board = self.board.copy()
        new_game.waste = self.waste
        new_game.stock_known = self.stock_known
        new_game.stock = self.stock.copy() if self.stock_known else self.stock
        new_game.removed = self.removed.copy()
        new_game.seen_counts = self.seen_counts.copy()
        return new_game

    def _validate_seen_counts(self):
        overfull = {
            rank: count
            for rank, count in self.seen_counts.items()
            if count > COPIES_PER_RANK
        }
        if overfull:
            details = ", ".join(
                f"{rank}={count}" for rank, count in sorted(overfull.items())
            )
            raise ValueError(f"Impossible deck: {details}")

    def observe_rank(self, card):
        """Record one newly observed card, rejecting impossible deals."""
        card = normalize(card)
        if card not in RANKS:
            raise ValueError("An observed card must have a known rank.")
        if self.seen_counts[card] >= COPIES_PER_RANK:
            raise ValueError(f"Impossible deck: more than four {card} cards.")
        self.seen_counts[card] += 1
        return card

    def unknown_counts(self):
        return {
            rank: COPIES_PER_RANK - self.seen_counts[rank]
            for rank in RANKS
        }

    def unknown_card_pool(self):
        return [
            rank
            for rank, count in self.unknown_counts().items()
            for _ in range(count)
        ]

    def sample_unknown_card(self, rng=None):
        pool = self.unknown_card_pool()
        if not pool:
            raise ValueError("No unknown cards remain in the deck.")
        rng = rng or random
        return self.observe_rank(rng.choice(pool))

    def observe_draw(self, card):
        if self.stock_known:
            raise ValueError("Cannot manually observe a known stock.")
        if self.stock <= 0:
            raise ValueError("The stock is empty.")
        card = self.observe_rank(card)
        self.stock -= 1
        self.waste = card
        return card

    # ------------------------------------------------------------------
    # TABLEAU REMAINING
    # ------------------------------------------------------------------

    def remaining(self):

        count = 0

        for position in range(1, 29):

            if position in self.removed:
                continue

            card = self.board[position - 1]

            if card != "--":
                count += 1

        return count

    # ------------------------------------------------------------------
    # EXPOSED CARDS
    # ------------------------------------------------------------------

    def exposed(self):

        """
        Return all currently exposed tableau positions.
        """

        result = []

        for position in range(1, 29):

            if position in self.removed:
                continue

            card = self.board[position - 1]

            if card == "--":
                continue

            blockers = BLOCKERS.get(
                position,
                ()
            )

            if all(
                blocker in self.removed
                for blocker in blockers
            ):

                result.append(position)

        return result

    # ------------------------------------------------------------------
    # LEGAL MOVES
    # ------------------------------------------------------------------

    def legal_moves(self):

        result = []

        for position in self.exposed():

            card = self.board[position - 1]

            # Unknown card cannot be played yet.
            if card == "?":
                continue

            if can_play(
                card,
                self.waste
            ):
                result.append(position)

        return result

    # ------------------------------------------------------------------
    # PLAY
    # ------------------------------------------------------------------

    def play(self, position):
        """Apply one legal tableau move.

        Keeping validation at the state boundary prevents callers, tests, and
        future interfaces from creating impossible games.
        """
        if not isinstance(position, int) or not 1 <= position <= TOTAL_TABLEAU:
            raise ValueError(f"Invalid tableau position: {position!r}")
        if position in self.removed:
            raise ValueError(f"Position {position:02d} has already been removed.")
        if position not in self.exposed():
            raise ValueError(f"Position {position:02d} is not exposed.")
        card = self.board[position - 1]
        if card not in RANKS:
            raise ValueError(f"Position {position:02d} has no known playable card.")
        if not can_play(card, self.waste):
            raise ValueError(f"{card} cannot be played on {self.waste}.")
        self.removed.add(position)
        self.waste = card
        return card


# ======================================================================
# CARD ACCOUNTING
# ======================================================================

def known_counts(game):
    """Return a copy of all ranks observed in this game."""
    return game.seen_counts.copy()


def unknown_counts(game):
    """Compatibility wrapper for callers outside ``Game``."""
    return game.unknown_counts()


def unknown_card_pool(game):
    """Compatibility wrapper for callers outside ``Game``."""
    return game.unknown_card_pool()


def random_unknown_card(game, rng=None):
    """Sample and consume one previously unknown card."""
    return game.sample_unknown_card(rng)


# ======================================================================
# INPUT FUNCTIONS
# ======================================================================

def read_cards(prompt, count):
    """
    Read exactly 'count' cards from one line.

    Example:

        > A 4 7 10 Q 3 ...
    """

    while True:

        try:

            values = (
                input(prompt)
                .strip()
                .upper()
                .split()
            )

            if len(values) != count:

                print(
                    f"Please enter exactly "
                    f"{count} cards."
                )

                continue

            return [
                normalize(card)
                for card in values
            ]

        except ValueError as error:

            print(error)


def read_rank(prompt):

    while True:

        try:

            card = normalize(
                input(prompt)
            )

            if card in ("?", "--"):

                print(
                    "Please enter an actual card rank."
                )

                continue

            return card

        except ValueError as error:

            print(error)


# ======================================================================
# STARTUP EXPLANATION
# ======================================================================

def explain():

    print()
    print("=" * 72)
    print("                         TRITOWERS SOLVER")
    print("=" * 72)

    print(
        """
CARD INFORMATION
----------------

This solver ignores SUITS completely.

Only the rank/number of each card matters.

There are four copies of every rank:

    A  2  3  4  5  6  7  8  9  10  J  Q  K


THE 52 CARDS
------------

    28 tableau cards
     1 waste card
    23 stock cards
    ----------------
    52 cards total


TABLEAU
-------

The tableau is the group of 28 cards arranged into the
three towers.


WASTE
-----

The waste is the single card currently showing.

A tableau card can be played when its rank is immediately
above or below the waste card.

A and K are treated as adjacent.


STOCK
-----

The stock is the pile of cards that you draw when there
are no playable tableau cards.

There are ALWAYS 23 stock cards at the start.


EXPOSED
-------

A card is exposed when BOTH cards covering it have been
removed.

If you only know the bottom row, you do NOT need to enter
the other tableau cards initially.

The solver will ask for an unknown card when it becomes
exposed.


GUARANTEED ROUTE
----------------

The solver first searches for a route that is guaranteed
to work based on the information currently available.


STATISTICAL ROUTE
-----------------

If no guaranteed route can be established, the solver
simulates possible future cards and chooses the move with
the highest estimated chance of success.


DURING PLAY
-----------

You do NOT need to confirm the solver's moves.

When a card becomes exposed, simply enter its rank.

When an unknown stock card is drawn, simply enter the rank
that appeared.

The solver then immediately continues.
"""
    )

    print()
    print("=" * 72)
    print("                         POSITION MAP")
    print("=" * 72)

    print(
        """
                         [01]       [02]       [03]


                    [04] [05]   [06] [07]   [08] [09]


               [10] [11] [12] [13] [14] [15] [16] [17] [18]


        [19] [20] [21] [22] [23] [24] [25] [26] [27] [28]


BOTTOM ROW:

19 20 21 22 23 24 25 26 27 28
"""
    )

    print("=" * 72)
    print()


# ======================================================================
# SETUP
# ======================================================================

def setup():

    explain()

    # ------------------------------------------------------------------
    # ASK ALL INFORMATION QUESTIONS BEFORE CARD ENTRY
    # ------------------------------------------------------------------

    print("=" * 72)
    print("                         GAME INFORMATION")
    print("=" * 72)

    print()

    print(
        "Do you know all 28 tableau cards?"
    )

    print(
        "1 = Yes, I know all 28"
    )

    print(
        "2 = No, I only know the bottom row"
    )

    while True:

        tableau_mode = input(
            "\nChoice [1/2]: "
        ).strip()

        if tableau_mode in ("1", "2"):
            break

        print(
            "Please enter 1 or 2."
        )

    print()

    print(
        "Do you know the order of the 23 stock cards?"
    )

    print(
        "1 = Yes, I know the stock order"
    )

    print(
        "2 = No, the stock is unknown"
    )

    while True:

        stock_mode = input(
            "\nChoice [1/2]: "
        ).strip()

        if stock_mode in ("1", "2"):
            break

        print(
            "Please enter 1 or 2."
        )

    # ------------------------------------------------------------------
    # TABLEAU ENTRY
    # ------------------------------------------------------------------

    board = ["?"] * TOTAL_TABLEAU

    print()
    print("=" * 72)
    print("                           CARD ENTRY")
    print("=" * 72)

    if tableau_mode == "1":

        print(
            """
Enter all 28 tableau cards in POSITION ORDER.

Order:

01 02 03 04 05 06 07 08 09 10 ... 26 27 28

Enter all 28 cards on ONE line.

Use -- if a tableau position has already been cleared.
"""
        )

        board = read_cards(
            "> ",
            28
        )

    else:

        print(
            """
Enter ONLY the bottom row.

Positions:

19 20 21 22 23 24 25 26 27 28

Enter all 10 cards on ONE line.
"""
        )

        bottom = read_cards(
            "> ",
            10
        )

        board[18:28] = bottom

    # ------------------------------------------------------------------
    # WASTE
    # ------------------------------------------------------------------

    print()

    waste = read_rank(
        "Current waste card: "
    )

    # ------------------------------------------------------------------
    # STOCK
    # ------------------------------------------------------------------

    if stock_mode == "1":

        print(
            """
Enter the 23 stock cards in DRAW ORDER.

The FIRST card you enter is the NEXT card that
will be drawn.

Enter all 23 cards on ONE line.
"""
        )

        stock = read_cards(
            "> ",
            TOTAL_STOCK
        )

        stock_known = True

    else:

        # 52 total - 28 tableau - 1 waste = 23 stock.
        stock = TOTAL_STOCK

        stock_known = False

    # ------------------------------------------------------------------
    # VALIDATE DECK
    # ------------------------------------------------------------------

    board_counts = Counter(
        card
        for card in board
        if card in RANKS
    )

    board_counts[waste] += 1

    if stock_known:

        for card in stock:
            board_counts[card] += 1

    for rank in RANKS:

        if board_counts[rank] > COPIES_PER_RANK:

            raise ValueError(
                f"Too many copies of {rank} "
                f"were entered. A standard deck has "
                f"only four."
            )

    return Game(
        board,
        waste,
        stock_known,
        stock
    )


# ======================================================================
# REVEAL UNKNOWN CARDS
# ======================================================================

def reveal_unknowns(game, read_card=read_rank):

    """
    Ask for every newly exposed unknown tableau card.

    If only the bottom row was entered initially, this is how
    the solver progressively learns the rest of the tableau.
    """

    unknown_positions = [
        position
        for position in game.exposed()
        if game.board[position - 1] == "?"
    ]

    for position in unknown_positions:

        card = read_card(f"Position {position:02d}: ")

        card = game.observe_rank(card)
        game.board[position - 1] = card


# ======================================================================
# STOCK DRAW
# ======================================================================

def draw(game, read_card=read_rank, emit=print):

    # ------------------------------------------------------------------
    # KNOWN STOCK
    # ------------------------------------------------------------------

    if game.stock_known:

        if not game.stock:
            return False

        card = game.stock.pop(0)

        game.waste = card

        emit(f"DRAW -> {card}")

        return True

    # ------------------------------------------------------------------
    # UNKNOWN STOCK
    # ------------------------------------------------------------------

    if game.stock <= 0:
        return False

    # The user only tells us what card actually appeared.
    card = read_card("DRAW -> ")

    game.observe_draw(card)

    return True


# ======================================================================
# MOVE HEURISTIC
# ======================================================================

def move_score(game, position):
    """Score only consequences caused by this move.

    The former implementation rescored every already exposed card and added a
    sibling-constant "cards removed" term. That made most of the score unrelated
    to the candidate move and produced avoidable ties.
    """
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
            if can_play(card, child.waste):
                score += 8

    # Prefer moves that remove a blocker from still-covered cards. This differs
    # between sibling moves and measures genuine future progress.
    score += sum(
        position in blockers
        for covered, blockers in BLOCKERS.items()
        if covered not in child.removed
    )
    return score


# ======================================================================
# GUARANTEED MOVE CHECK
# ======================================================================

def guaranteed_moves(game):
    """Return moves that immediately and provably clear the tableau.

    A Monte Carlo success rate, or merely having stock left, is not a proof.
    Broader proof-producing search can be added separately.
    """
    result = []
    for position in game.legal_moves():
        child = game.copy()
        child.play(position)
        if child.remaining() == 0:
            result.append(position)
    return result


# ======================================================================
# SIMULATION
# ======================================================================

def simulate(
    game,
    first_move=None,
    rng=None
):

    """
    Simulate a possible future game.

    Unknown tableau and stock cards are sampled according to
    the known cards and the four-copy rule.
    """

    rng = rng or random
    g = game.copy()

    # --------------------------------------------------------------
    # Apply proposed first move.
    # --------------------------------------------------------------

    if first_move is not None:

        g.play(first_move)

    # --------------------------------------------------------------
    # Simulate.
    # --------------------------------------------------------------

    # Every iteration either removes a tableau card or consumes a stock card.
    max_transitions = g.remaining() + (
        len(g.stock) if g.stock_known else g.stock
    )
    for _ in range(max_transitions):

        # ----------------------------------------------------------
        # Win.
        # ----------------------------------------------------------

        if g.remaining() == 0:

            return True

        # ----------------------------------------------------------
        # Resolve unknown exposed tableau cards.
        # ----------------------------------------------------------

        for position in g.exposed():

            if g.board[position - 1] == "?":

                g.board[position - 1] = (
                    random_unknown_card(g, rng)
                )

        # ----------------------------------------------------------
        # Play available tableau cards.
        # ----------------------------------------------------------

        moves = g.legal_moves()

        if moves:

            scored = [
                (
                    move_score(
                        g,
                        position
                    ),
                    position
                )
                for position in moves
            ]

            scored.sort(
                reverse=True
            )

            # Consider the strongest few moves rather than
            # making the simulation completely deterministic.
            top = scored[
                :min(3, len(scored))
            ]

            _, position = rng.choice(
                top
            )

            g.play(position)

            continue

        # ----------------------------------------------------------
        # No tableau move: draw.
        # ----------------------------------------------------------

        if g.stock_known:

            if not g.stock:

                return False

            g.waste = g.stock.pop(0)

        else:

            if g.stock <= 0:

                return False

            g.stock -= 1

            g.waste = g.sample_unknown_card(rng)

    return (
        g.remaining() == 0
    )


# ======================================================================
# PROBABILITY
# ======================================================================

def probability(game, position, simulations=SIMULATIONS, rng=None):
    """Estimate a move's win rate with reproducible injected randomness."""
    if simulations <= 0:
        raise ValueError("simulations must be positive")
    rng = rng or random
    wins = sum(
        simulate(game, first_move=position, rng=rng)
        for _ in range(simulations)
    )
    return wins / simulations


# ======================================================================
# BEST MOVE
# ======================================================================

def best_move(game, simulations=SIMULATIONS, rng=None):
    """Return a recommendation whose evidence type cannot be confused.

    A sampled rate of 100% remains sampled evidence, never a proof.
    """
    moves = game.legal_moves()
    if not moves:
        return None

    proven = guaranteed_moves(game)
    if proven:
        position = max(proven, key=lambda candidate: move_score(game, candidate))
        return Recommendation(position, 1.0, Evidence.PROVEN)

    rng = rng or random
    scored = [
        (
            probability(game, position, simulations=simulations, rng=rng),
            move_score(game, position),
            position,
        )
        for position in moves
    ]
    success_rate, _, position = max(scored)
    return Recommendation(
        position,
        success_rate,
        Evidence.SAMPLED,
        simulations,
    )


# ======================================================================
# MAIN GAME LOOP
# ======================================================================

def main():

    game = setup()

    print()
    print("=" * 72)
    print("                         SOLVER ACTIVE")
    print("=" * 72)

    while True:

        # --------------------------------------------------------------
        # Ask for newly exposed unknown cards.
        # --------------------------------------------------------------

        reveal_unknowns(game)

        # --------------------------------------------------------------
        # Check for win.
        # --------------------------------------------------------------

        if game.remaining() == 0:

            print()
            print("=" * 72)
            print("                              WIN!")
            print("=" * 72)

            return

        # --------------------------------------------------------------
        # Find legal tableau moves.
        # --------------------------------------------------------------

        moves = game.legal_moves()

        # --------------------------------------------------------------
        # No tableau move -> draw.
        # --------------------------------------------------------------

        if not moves:

            if (
                (
                    game.stock_known
                    and not game.stock
                )
                or
                (
                    not game.stock_known
                    and game.stock <= 0
                )
            ):

                print()
                print(
                    "No playable tableau cards "
                    "and the stock is empty."
                )

                return

            draw(game)

            continue

        # --------------------------------------------------------------
        # Find best move.
        # --------------------------------------------------------------

        recommendation = best_move(game)
        position = recommendation.position
        card = game.board[position - 1]

        # --------------------------------------------------------------
        # Guaranteed route.
        # --------------------------------------------------------------

        if recommendation.evidence is Evidence.PROVEN:

            print(
                f"\nPLAY {card} @ "
                f"{position:02d} "
                f"[GUARANTEED]"
            )

        # --------------------------------------------------------------
        # Statistical route.
        # --------------------------------------------------------------

        else:

            print(
                f"\nPLAY {card} @ "
                f"{position:02d} "
                f"[{recommendation.success_rate * 100:.1f}% sampled "
                f"over {recommendation.simulations} runs]"
            )

        # --------------------------------------------------------------
        # Automatically apply move.
        #
        # No confirmation required.
        # --------------------------------------------------------------

        game.play(position)


# ======================================================================
# START
# ======================================================================

if __name__ == "__main__":

    try:

        main()

    except KeyboardInterrupt:

        print(
            "\nSolver stopped."
        )

    except Exception as error:

        print(
            f"\nERROR: {error}"
          )
