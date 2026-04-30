from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from auction_game.bot_loader import discover_bot_names, load_bot
from auction_game.interfaces import AuctionItem, AuctionState
from auction_game.round_robin import run_round_robin

DEFAULT_BUDGET = 200_000_000
DEFAULT_ITEM_COUNT = 20
MIN_ITEM_VALUE = 11_000_000
MAX_ITEM_VALUE = 20_000_000
ITEM_CATEGORIES = ["ai", "web", "brand", "cloud", "dev", "data"]


@dataclass(slots=True)
class MatchResult:
    left_value: int
    right_value: int
    left_category_bonus: int
    right_category_bonus: int
    left_money_left: int
    right_money_left: int
    left_score: int
    right_score: int
    log: list[str]


def generate_items(
    *,
    item_count: int = DEFAULT_ITEM_COUNT,
    min_value: int = MIN_ITEM_VALUE,
    max_value: int = MAX_ITEM_VALUE,
    rng: random.Random | None = None,
) -> list[AuctionItem]:
    if item_count <= 0:
        raise ValueError("item_count must be positive")
    if min_value <= 0 or max_value <= 0:
        raise ValueError("item values must be positive")
    if min_value > max_value:
        raise ValueError("min_value must be less than or equal to max_value")

    generator = rng or random.Random()
    items: list[AuctionItem] = []
    for index in range(item_count):
        items.append(
            AuctionItem(
                name=f"item_{index + 1}",
                category=ITEM_CATEGORIES[index % len(ITEM_CATEGORIES)],
                value=generator.randint(min_value, max_value),
            )
        )
    return items


def _build_state(
    *,
    round_index: int,
    item: AuctionItem,
    total_rounds: int,
    my_budget: int,
    opponent_budget: int,
    my_items: list[AuctionItem],
    opponent_items: list[AuctionItem],
    my_bids: list[int],
    opponent_bids: list[int],
) -> AuctionState:
    return AuctionState(
        round_index=round_index,
        total_rounds=total_rounds,
        item=item,
        my_budget=my_budget,
        opponent_budget=opponent_budget,
        my_items=tuple(my_items),
        opponent_items=tuple(opponent_items),
        my_bids=tuple(my_bids),
        opponent_bids=tuple(opponent_bids),
    )


def _validate_bid(bid: int, budget: int) -> int:
    if not isinstance(bid, int):
        raise ValueError(f"Bid must be an integer, got {type(bid).__name__}")
    if bid < 0:
        raise ValueError(f"Bid must be non-negative, got {bid}")
    return min(bid, budget)


def _category_bonus_rate(item_count: int) -> float:
    raw_rate = 0.06 * max(0, item_count - 1) + 0.02 * max(0, item_count - 3)
    return min(raw_rate, 0.30)


def _category_bonus(items: list[AuctionItem]) -> int:
    category_values: dict[str, int] = defaultdict(int)
    category_counts: dict[str, int] = defaultdict(int)

    for item in items:
        category_values[item.category] += item.value
        category_counts[item.category] += 1

    total_bonus = 0
    for category, total_value in category_values.items():
        total_bonus += int(total_value * _category_bonus_rate(category_counts[category]))
    return total_bonus


def _score_items(items: list[AuctionItem], money_left: int) -> tuple[int, int]:
    item_value = sum(item.value for item in items)
    category_bonus = _category_bonus(items)
    return item_value + category_bonus + money_left, category_bonus


def play_match(
    left_name: str,
    right_name: str,
    budget: int = DEFAULT_BUDGET,
    items: list[AuctionItem] | None = None,
) -> MatchResult:
    left_bot = load_bot("auction_game.bots", left_name)
    right_bot = load_bot("auction_game.bots", right_name)
    match_items = list(items or generate_items())

    left_budget = budget
    right_budget = budget
    left_items: list[AuctionItem] = []
    right_items: list[AuctionItem] = []
    left_bids: list[int] = []
    right_bids: list[int] = []
    log: list[str] = []

    for round_index, item in enumerate(match_items):
        left_bid = _validate_bid(
            left_bot.choose_bid(
                _build_state(
                    round_index=round_index,
                    item=item,
                    total_rounds=len(match_items),
                    my_budget=left_budget,
                    opponent_budget=right_budget,
                    my_items=left_items,
                    opponent_items=right_items,
                    my_bids=left_bids,
                    opponent_bids=right_bids,
                )
            ),
            left_budget,
        )
        right_bid = _validate_bid(
            right_bot.choose_bid(
                _build_state(
                    round_index=round_index,
                    item=item,
                    total_rounds=len(match_items),
                    my_budget=right_budget,
                    opponent_budget=left_budget,
                    my_items=right_items,
                    opponent_items=left_items,
                    my_bids=right_bids,
                    opponent_bids=left_bids,
                )
            ),
            right_budget,
        )

        left_bids.append(left_bid)
        right_bids.append(right_bid)

        if left_bid > right_bid:
            left_budget -= left_bid
            left_items.append(item)
            winner = left_name
        elif right_bid > left_bid:
            right_budget -= right_bid
            right_items.append(item)
            winner = right_name
        else:
            winner = "tie"

        log.append(
            f"round={round_index + 1} item={item.name} "
            f"bids={left_name}:{left_bid} {right_name}:{right_bid} winner={winner}"
        )

    left_value = sum(item.value for item in left_items)
    right_value = sum(item.value for item in right_items)
    left_score, left_category_bonus = _score_items(left_items, left_budget)
    right_score, right_category_bonus = _score_items(right_items, right_budget)
    return MatchResult(
        left_value=left_value,
        right_value=right_value,
        left_category_bonus=left_category_bonus,
        right_category_bonus=right_category_bonus,
        left_money_left=left_budget,
        right_money_left=right_budget,
        left_score=left_score,
        right_score=right_score,
        log=log,
    )


def discover_bots() -> list[str]:
    bots_dir = Path(__file__).with_name("bots")
    return discover_bot_names(bots_dir)


def run_tournament(
    budget: int = DEFAULT_BUDGET,
    item_count: int = DEFAULT_ITEM_COUNT,
    min_value: int = MIN_ITEM_VALUE,
    max_value: int = MAX_ITEM_VALUE,
    seed: int | None = None,
) -> list[dict[str, object]]:
    standings = {
        name: {
            "points": 0,
            "wins": 0,
            "draws": 0,
            "matches": 0,
            "score": 0,
            "value": 0,
            "category_bonus": 0,
            "money_left": 0,
        }
        for name in discover_bots()
    }
    items = generate_items(
        item_count=item_count,
        min_value=min_value,
        max_value=max_value,
        rng=random.Random(seed),
    )

    def _play(left: str, right: str) -> MatchResult:
        return play_match(left, right, budget=budget, items=items)

    results = run_round_robin(list(standings), _play)
    for left, right, result in results:
        standings[left]["matches"] += 1
        standings[right]["matches"] += 1
        standings[left]["score"] += result.left_score
        standings[right]["score"] += result.right_score
        standings[left]["value"] += result.left_value
        standings[right]["value"] += result.right_value
        standings[left]["category_bonus"] += result.left_category_bonus
        standings[right]["category_bonus"] += result.right_category_bonus
        standings[left]["money_left"] += result.left_money_left
        standings[right]["money_left"] += result.right_money_left

        if result.left_score > result.right_score:
            standings[left]["points"] += 3
            standings[left]["wins"] += 1
        elif result.left_score < result.right_score:
            standings[right]["points"] += 3
            standings[right]["wins"] += 1
        else:
            standings[left]["points"] += 1
            standings[right]["points"] += 1
            standings[left]["draws"] += 1
            standings[right]["draws"] += 1

    ordered = []
    for name, values in standings.items():
        matches = int(values["matches"])
        wins = int(values["wins"])
        ordered.append(
            {
                "bot": name,
                **values,
                "win_rate": (wins / matches) if matches else 0.0,
            }
        )
    ordered.sort(
        key=lambda item: (
            -item["win_rate"],
            -item["wins"],
            -item["score"],
            -item["value"],
            -item["money_left"],
            item["bot"],
        )
    )
    return ordered
