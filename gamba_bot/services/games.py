import random
from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class GameResult:
    won: bool
    delta: int
    detail: str


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


def create_blackjack_round() -> BlackjackRound:
    deck = [f"{rank}{suit}" for suit in SUITS for rank in RANKS]
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


def slots(stake: int) -> GameResult:
    symbols = ["7", "BAR", "Cherry", "Bell", "Star"]
    a, b, c = random.choices(symbols, k=3)
    line = f"{a} | {b} | {c}"
    if a == b == c:
        return GameResult(True, stake * 5, f"{line} - jackpot!")
    if a == b or b == c or a == c:
        return GameResult(True, stake, f"{line} - small win.")
    return GameResult(False, -stake, f"{line} - no match.")


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
