from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from shared.bot_loader import discover_bot_names, load_bot_module
from shared.round_robin import run_round_robin

ITEMS = [
    {"name": "ml_workshop", "category": "ai", "value": 8},
    {"name": "frontend_talk", "category": "web", "value": 5},
    {"name": "keynote_slot", "category": "brand", "value": 10},
    {"name": "infra_panel", "category": "cloud", "value": 7},
    {"name": "sponsor_booth", "category": "brand", "value": 6},
    {"name": "hackathon_room", "category": "dev", "value": 9},
    {"name": "api_session", "category": "web", "value": 4},
    {"name": "data_track", "category": "ai", "value": 7},
]
SET_BONUS = 6


@dataclass(slots=True)
class MatchResult:
    left_value: int
    right_value: int
    left_spend: int
    right_spend: int
    log: list[str]


def _build_state(
    *,
    round_index: int,
    item: dict[str, object],
    my_budget: int,
    opponent_budget: int,
    my_items: list[dict[str, object]],
    opponent_items: list[dict[str, object]],
    my_bids: list[int],
    opponent_bids: list[int],
) -> dict[str, object]:
    return {
        "round_index": round_index,
        "item": dict(item),
        "my_budget": my_budget,
        "opponent_budget": opponent_budget,
        "my_items": [dict(entry) for entry in my_items],
        "opponent_items": [dict(entry) for entry in opponent_items],
        "my_bids": list(my_bids),
        "opponent_bids": list(opponent_bids),
    }


def _validate_bid(bid: int, budget: int) -> int:
    if not isinstance(bid, int):
        raise ValueError(f"Bid must be an integer, got {type(bid).__name__}")
    if bid < 0:
        raise ValueError(f"Bid must be non-negative, got {bid}")
    return min(bid, budget)


def _score_items(items: list[dict[str, object]]) -> int:
    total = sum(int(item["value"]) for item in items)
    categories = [str(item["category"]) for item in items]
    for category in set(categories):
        if categories.count(category) >= 2:
            total += SET_BONUS
    return total


def play_match(left_name: str, right_name: str, budget: int = 100) -> MatchResult:
    left_bot = load_bot_module("projects.auction_game.bots", left_name)
    right_bot = load_bot_module("projects.auction_game.bots", right_name)

    left_budget = budget
    right_budget = budget
    left_items: list[dict[str, object]] = []
    right_items: list[dict[str, object]] = []
    left_bids: list[int] = []
    right_bids: list[int] = []
    log: list[str] = []

    for round_index, item in enumerate(ITEMS):
        left_bid = _validate_bid(
            left_bot.choose_bid(
                _build_state(
                    round_index=round_index,
                    item=item,
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
            f"round={round_index + 1} item={item['name']} "
            f"bids={left_name}:{left_bid} {right_name}:{right_bid} winner={winner}"
        )

    left_value = _score_items(left_items)
    right_value = _score_items(right_items)
    return MatchResult(
        left_value=left_value,
        right_value=right_value,
        left_spend=budget - left_budget,
        right_spend=budget - right_budget,
        log=log,
    )


def discover_bots() -> list[str]:
    bots_dir = Path(__file__).with_name("bots")
    return discover_bot_names(bots_dir)


def run_tournament(budget: int = 100) -> list[dict[str, object]]:
    standings = {name: {"points": 0, "value": 0, "spend": 0} for name in discover_bots()}

    def _play(left: str, right: str) -> MatchResult:
        return play_match(left, right, budget=budget)

    results = run_round_robin(list(standings), _play)
    for left, right, result in results:
        standings[left]["value"] += result.left_value
        standings[right]["value"] += result.right_value
        standings[left]["spend"] += result.left_spend
        standings[right]["spend"] += result.right_spend

        if result.left_value > result.right_value:
            standings[left]["points"] += 3
        elif result.left_value < result.right_value:
            standings[right]["points"] += 3
        else:
            standings[left]["points"] += 1
            standings[right]["points"] += 1

    ordered = []
    for name, values in standings.items():
        ordered.append({"bot": name, **values})
    ordered.sort(key=lambda item: (-item["points"], -item["value"], item["spend"], item["bot"]))
    return ordered
