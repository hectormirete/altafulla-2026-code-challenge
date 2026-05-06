from __future__ import annotations

from collections import defaultdict

from auction_game import AuctionBot, AuctionState
from auction_game.interfaces import AuctionItem, MIN_BID_INCREMENT

ITEM_CATEGORIES = ("ai", "web", "brand", "cloud", "dev", "data")
AVERAGE_ITEM_VALUE = 12_000_000


def _bonus_rate(item_count: int) -> float:
    raw_rate = 0.06 * max(0, item_count - 1) + 0.02 * max(0, item_count - 3)
    return min(raw_rate, 0.30)


def _floor_to_increment(value: int) -> int:
    if value <= 0:
        return 0
    return value // MIN_BID_INCREMENT * MIN_BID_INCREMENT


def _category_snapshot(items: tuple[AuctionItem, ...]) -> tuple[dict[str, int], dict[str, int]]:
    counts: dict[str, int] = defaultdict(int)
    totals: dict[str, int] = defaultdict(int)
    for item in items:
        counts[item.category] += 1
        totals[item.category] += item.value
    return counts, totals


def _score(items: tuple[AuctionItem, ...], budget: int) -> int:
    counts, totals = _category_snapshot(items)
    value = sum(item.value for item in items)
    bonus = sum(int(total * _bonus_rate(counts[category])) for category, total in totals.items())
    return value + bonus + budget


class CodexChampionBot(AuctionBot):
    def _remaining_same_category(self, state: AuctionState) -> int:
        category = state.item.category
        remaining = 0
        for index in range(state.round_index + 1, state.total_rounds):
            if ITEM_CATEGORIES[index % len(ITEM_CATEGORIES)] == category:
                remaining += 1
        return remaining

    def _marginal_gain(self, items: tuple[AuctionItem, ...], item: AuctionItem) -> int:
        counts, totals = _category_snapshot(items)
        current_count = counts[item.category]
        current_total = totals[item.category]
        next_total = current_total + item.value
        current_bonus = int(current_total * _bonus_rate(current_count))
        next_bonus = int(next_total * _bonus_rate(current_count + 1))
        return item.value + (next_bonus - current_bonus)

    def _future_synergy(self, items: tuple[AuctionItem, ...], item: AuctionItem, remaining_same_category: int) -> int:
        if remaining_same_category <= 0:
            return 0

        counts, totals = _category_snapshot(items)
        current_count = counts[item.category]
        current_total = totals[item.category]
        expected_future_total = current_total + remaining_same_category * AVERAGE_ITEM_VALUE
        current_path = int(expected_future_total * _bonus_rate(current_count))
        upgraded_path = int((expected_future_total + item.value) * _bonus_rate(current_count + 1))
        immediate_path = int((current_total + item.value) * _bonus_rate(current_count + 1))
        return max(0, upgraded_path - current_path - immediate_path)

    def _reserve_price(self, state: AuctionState) -> int:
        rounds_left = state.total_rounds - state.round_index - 1
        remaining_same_category = self._remaining_same_category(state)
        my_counts, _ = _category_snapshot(state.my_items)
        opponent_counts, _ = _category_snapshot(state.opponent_items)
        my_category_count = my_counts[state.item.category]
        opponent_category_count = opponent_counts[state.item.category]

        my_gain = self._marginal_gain(state.my_items, state.item)
        opponent_gain = self._marginal_gain(state.opponent_items, state.item)
        future_synergy = self._future_synergy(state.my_items, state.item, remaining_same_category)

        current_gap = _score(state.my_items, state.my_budget) - _score(state.opponent_items, state.opponent_budget)
        catch_up_pressure = max(0, -current_gap) // max(1, rounds_left + 1)

        opportunity_cost = 1.0 + 0.22 * rounds_left / max(1, state.total_rounds - 1)
        if rounds_left > 0:
            pace_budget = state.my_budget / (rounds_left + 1)
            if pace_budget < 9_500_000:
                opportunity_cost += 0.10

        focus_multiplier = 0.72
        if state.item.category in {"ai", "web"}:
            focus_multiplier += 0.12
        if my_category_count >= 1:
            focus_multiplier += 0.12 + 0.06 * my_category_count
        if my_category_count == 0 and remaining_same_category == 0:
            focus_multiplier -= 0.18
        focus_multiplier = min(focus_multiplier, 1.08)

        denial_pressure = 0
        if current_gap < 0 or opponent_category_count > my_category_count:
            denial_pressure += int(opponent_gain * 0.15)
        if rounds_left <= 2:
            denial_pressure += int(opponent_gain * 0.20)

        raw_value = int(my_gain * focus_multiplier) + int(future_synergy * 0.25) + denial_pressure + int(catch_up_pressure * 0.18)
        if state.my_budget - state.opponent_budget >= 30_000_000 and current_gap >= -5_000_000:
            raw_value = int(raw_value * 0.75)
        reserve = int(raw_value / opportunity_cost)
        reserve = min(reserve, state.my_budget)
        return _floor_to_increment(reserve)

    def _opening_bid(self, reserve_price: int) -> int:
        if reserve_price <= 0:
            return 0
        if reserve_price <= 3 * MIN_BID_INCREMENT:
            return reserve_price
        return MIN_BID_INCREMENT

    def _raise_target(self, reserve_price: int, opponent_bid: int) -> int:
        minimum_raise = opponent_bid + MIN_BID_INCREMENT
        if minimum_raise > reserve_price:
            return 0
        return reserve_price

    def choose_bid_round_1(self, state: AuctionState) -> int:
        reserve_price = self._reserve_price(state)
        return self._opening_bid(reserve_price)

    def choose_bid_round_2(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        reserve_price = self._reserve_price(state)
        target = self._raise_target(reserve_price, opponent_bid)
        if target == 0:
            return my_bid
        return min(state.my_budget, max(my_bid, target))

    def choose_bid_round_3(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        reserve_price = self._reserve_price(state)
        rounds_left = state.total_rounds - state.round_index - 1
        score_gap = _score(state.my_items, state.my_budget) - _score(state.opponent_items, state.opponent_budget)

        if rounds_left <= 2 and score_gap < 0:
            reserve_price = min(
                state.my_budget,
                _floor_to_increment(reserve_price + (-score_gap) // 5),
            )

        target = self._raise_target(reserve_price, opponent_bid)
        if target == 0:
            return my_bid
        return min(state.my_budget, max(my_bid, target))


BOT_CLASS = CodexChampionBot
