from __future__ import annotations

from auction_game.interfaces import AuctionBot, AuctionItem, AuctionState, MIN_BID_INCREMENT


def _bonus_rate(item_count: int) -> float:
    return min(0.06 * max(0, item_count - 1) + 0.02 * max(0, item_count - 3), 0.30)


def _category_count(items: tuple[AuctionItem, ...], category: str) -> int:
    return sum(1 for item in items if item.category == category)


def _category_bonus(items: tuple[AuctionItem, ...]) -> int:
    category_values: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    for item in items:
        category_values[item.category] = category_values.get(item.category, 0) + item.value
        category_counts[item.category] = category_counts.get(item.category, 0) + 1
    return sum(
        int(category_values[category] * _bonus_rate(category_counts[category]))
        for category in category_values
    )


def _bonus_delta(items: tuple[AuctionItem, ...], item: AuctionItem) -> int:
    return _category_bonus(items + (item,)) - _category_bonus(items)


class AntiSwarmBot(AuctionBot):
    def __init__(self) -> None:
        self._category_pressure: dict[str, int] = {}

    def _observe_opening(self, state: AuctionState, bid: int) -> None:
        if bid >= state.item.value:
            self._category_pressure[state.item.category] = self._category_pressure.get(state.item.category, 0) + 2
        elif bid >= int(state.item.value * 0.75):
            self._category_pressure[state.item.category] = self._category_pressure.get(state.item.category, 0) + 1

    def _denial_value(self, state: AuctionState) -> int:
        category = state.item.category
        opponent_count = _category_count(state.opponent_items, category)
        if opponent_count == 0:
            return 0

        opponent_bonus_delta = _bonus_delta(state.opponent_items, state.item)
        pressure = self._category_pressure.get(category, 0)

        if pressure == 0 and opponent_count < 2:
            return 0

        value = opponent_bonus_delta
        if opponent_count >= 2:
            value += int(state.item.value * 0.03)
        if opponent_count >= 3:
            value += int(state.item.value * 0.04)
        if pressure >= 2:
            value += int(state.item.value * 0.04)

        return value

    def _value(self, state: AuctionState) -> int:
        own_bonus_delta = _bonus_delta(state.my_items, state.item)
        value = state.item.value - 1_000_000 + own_bonus_delta + self._denial_value(state)
        return min(state.my_budget, max(0, value))

    def choose_bid_round_1(self, state: AuctionState) -> int:
        opening_bid = self._value(state) - MIN_BID_INCREMENT
        return min(max(0, opening_bid), state.my_budget)

    def choose_bid_round_2(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        self._observe_opening(state, opponent_bid)
        target = opponent_bid + MIN_BID_INCREMENT
        if opponent_bid >= my_bid and target <= self._value(state):
            return min(target, state.my_budget)
        return my_bid

    def choose_bid_round_3(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        target = opponent_bid + MIN_BID_INCREMENT
        if opponent_bid >= my_bid and target <= self._value(state):
            return min(target, state.my_budget)
        return my_bid


BOT_CLASS = AntiSwarmBot
