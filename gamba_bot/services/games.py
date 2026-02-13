import random
from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class GameResult:
    won: bool
    delta: int
    detail: str


@dataclass(frozen=True)
class SlotResult:
    symbols: tuple[str, str, str]
    gross_win: int
    net_delta: int
    reason: str


RANKS = ("2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A")
SUITS = ("S", "H", "D", "C")
CARD_VALUES = {
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
    "7": 7,
    "8": 8,
    "9": 9,
    "10": 10,
    "J": 10,
    "Q": 10,
    "K": 10,
    "A": 11,
}


@dataclass
class BlackjackRound:
    deck: list[str] = field(default_factory=list)
    player_hand: list[str] = field(default_factory=list)
    dealer_hand: list[str] = field(default_factory=list)

    def draw(self) -> str:
        return self.deck.pop()

    def player_hit(self) -> str:
        card = self.draw()
        self.player_hand.append(card)
        return card

    def dealer_hit(self) -> str:
        card = self.draw()
        self.dealer_hand.append(card)
        return card


def create_blackjack_round(num_decks: int = 8) -> BlackjackRound:
    if num_decks < 1:
        raise ValueError("num_decks must be at least 1")
    deck = [f"{rank}{suit}" for _ in range(num_decks) for suit in SUITS for rank in RANKS]
    random.shuffle(deck)
    round_state = BlackjackRound(deck=deck)
    round_state.player_hand.append(round_state.draw())
    round_state.dealer_hand.append(round_state.draw())
    round_state.player_hand.append(round_state.draw())
    round_state.dealer_hand.append(round_state.draw())
    return round_state


def hand_total(cards: list[str]) -> int:
    total = 0
    aces = 0
    for card in cards:
        rank = card[:-1]
        total += CARD_VALUES[rank]
        if rank == "A":
            aces += 1
    while total > 21 and aces > 0:
        total -= 10
        aces -= 1
    return total


def is_blackjack(cards: list[str]) -> bool:
    return len(cards) == 2 and hand_total(cards) == 21


def dealer_must_hit(cards: list[str]) -> bool:
    return hand_total(cards) < 14


def roulette(stake: int, pick: Literal["red", "black", "green"]) -> GameResult:
    wheel = random.randint(0, 36)
    actual = "green" if wheel == 0 else ("red" if wheel % 2 == 0 else "black")
    if pick == actual:
        if pick == "green":
            win = stake * 14
        else:
            win = stake
        return GameResult(True, win, f"Ball landed on {actual} ({wheel}).")
    return GameResult(False, -stake, f"Ball landed on {actual} ({wheel}).")


SLOT_EMOJI = {
    "seven": "7️⃣",
    "diamond": "💎",
    "bar": "🟫",
    "bell": "🔔",
    "grape": "🍇",
    "lemon": "🍋",
    "cherry": "🍒",
}

# Reel strips model weighted symbol frequencies and therefore real symbol odds.
SLOT_REELS: tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]] = (
    tuple(
        ["cherry"] * 14
        + ["lemon"] * 13
        + ["grape"] * 9
        + ["bell"] * 7
        + ["bar"] * 5
        + ["diamond"] * 3
        + ["seven"] * 2
    ),
    tuple(
        ["cherry"] * 15
        + ["lemon"] * 12
        + ["grape"] * 8
        + ["bell"] * 8
        + ["bar"] * 5
        + ["diamond"] * 3
        + ["seven"] * 1
    ),
    tuple(
        ["cherry"] * 13
        + ["lemon"] * 14
        + ["grape"] * 9
        + ["bell"] * 7
        + ["bar"] * 5
        + ["diamond"] * 3
        + ["seven"] * 2
    ),
)

SLOT_3OAK_MULTIPLIERS = {
    "seven": 20.0,
    "diamond": 12.0,
    "bar": 8.0,
    "bell": 5.0,
    "grape": 3.0,
    "lemon": 2.5,
    "cherry": 2.0,
}


def spin_slot_reels(
    current_stops: list[int] | None,
    holds: list[bool],
) -> tuple[list[int], tuple[str, str, str]]:
    if len(holds) != 3:
        raise ValueError("Holds must contain exactly 3 values.")
    if current_stops is None:
        current_stops = [0, 0, 0]

    stops: list[int] = []
    symbols: list[str] = []
    for idx, reel in enumerate(SLOT_REELS):
        if holds[idx]:
            stop = current_stops[idx] % len(reel)
        else:
            stop = random.randint(0, len(reel) - 1)
        stops.append(stop)
        symbols.append(reel[stop])
    return stops, (symbols[0], symbols[1], symbols[2])


def evaluate_slots(symbols: tuple[str, str, str], stake: int) -> SlotResult:
    if stake <= 0:
        raise ValueError("Stake must be greater than zero.")

    a, b, c = symbols
    if a == b == c:
        multiplier = SLOT_3OAK_MULTIPLIERS[a]
        gross = max(1, int(round(stake * multiplier)))
        return SlotResult(symbols, gross, gross - stake, f"Three {a}s ({multiplier}x)")

    cherries = symbols.count("cherry")
    if cherries == 2:
        multiplier = 1.2
        gross = max(1, int(round(stake * multiplier)))
        return SlotResult(symbols, gross, gross - stake, "Two cherries (1.2x)")
    if cherries == 1:
        multiplier = 0.4
        gross = max(1, int(round(stake * multiplier)))
        return SlotResult(symbols, gross, gross - stake, "One cherry (0.4x)")

    return SlotResult(symbols, 0, -stake, "No payout")


def slot_paytable_lines() -> list[str]:
    lines = []
    for symbol, mult in SLOT_3OAK_MULTIPLIERS.items():
        emoji = SLOT_EMOJI[symbol]
        lines.append(f"{emoji} {emoji} {emoji} -> {mult}x")
    lines.append("🍒 🍒 _ -> 1.2x")
    lines.append("🍒 _ _ -> 0.4x")
    return lines


def slots(stake: int) -> GameResult:
    _, symbols = spin_slot_reels(None, [False, False, False])
    result = evaluate_slots(symbols, stake)
    pretty = " | ".join(SLOT_EMOJI[s] for s in symbols)
    return GameResult(
        won=result.net_delta >= 0,
        delta=result.net_delta,
        detail=f"{pretty} - {result.reason}",
    )


def poker(stake: int) -> GameResult:
    ranks = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
    player = random.choice(ranks)
    bot = random.choice(ranks)
    pi = ranks.index(player)
    bi = ranks.index(bot)
    if pi > bi:
        return GameResult(True, stake * 2, f"You drew {player}, house drew {bot}.")
    if pi == bi:
        return GameResult(True, 0, f"Both drew {player}.")
    return GameResult(False, -stake, f"You drew {player}, house drew {bot}.")


def minesweeper(stake: int, tiles: int) -> GameResult:
    mine = random.randint(1, 6)
    if tiles == mine:
        return GameResult(False, -stake, f"Tile {tiles} had a mine.")
    return GameResult(True, int(stake * 1.2), f"Tile {tiles} was safe. Mine was {mine}.")


def wordlinks(stake: int, guess: int) -> GameResult:
    words = random.choice(
        [
            ("discord", 7),
            ("roulette", 8),
            ("casino", 6),
            ("balance", 7),
            ("blackjack", 9),
        ]
    )
    word, actual = words
    if guess == actual:
        return GameResult(True, stake * 3, f'Length of "{word}" is {actual}.')
    return GameResult(False, -stake, f'Length of "{word}" is {actual}.')
