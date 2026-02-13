import random
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class GameResult:
    won: bool
    delta: int
    detail: str


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


def blackjack(stake: int) -> GameResult:
    player = random.randint(12, 21)
    dealer = random.randint(12, 21)
    if player > dealer:
        return GameResult(True, int(stake * 1.5), f"Player {player} vs Dealer {dealer}")
    if player == dealer:
        return GameResult(True, 0, f"Push: {player} vs {dealer}")
    return GameResult(False, -stake, f"Player {player} vs Dealer {dealer}")


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
