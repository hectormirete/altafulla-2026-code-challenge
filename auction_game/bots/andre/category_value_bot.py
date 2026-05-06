from __future__ import annotations

from auction_game.interfaces import AuctionBot, AuctionItem, AuctionState, MIN_BID_INCREMENT


def _bonus_rate(count: int) -> float:
    return min(0.06 * max(0, count - 1) + 0.02 * max(0, count - 3), 0.30)


def _bonus(items: tuple[AuctionItem, ...]) -> int:
    values: dict[str, int] = {}
    counts: dict[str, int] = {}
    for item in items:
        values[item.category] = values.get(item.category, 0) + item.value
        counts[item.category] = counts.get(item.category, 0) + 1
    return sum(int(values[category] * _bonus_rate(counts[category])) for category in values)


class CategoryValueBot(AuctionBot):
    def __init__(self) -> None:
        self._triggered_fair_opener = False

    def _value(self, state: AuctionState) -> int:
        current_category_bonus = _bonus(state.my_items)
        items_after_win = state.my_items + (state.item,)
        category_bonus_after_win = _bonus(items_after_win)
        extra_category_bonus = category_bonus_after_win - current_category_bonus
        return min(state.my_budget, state.item.value + extra_category_bonus + 2_000_000)

    def choose_bid_round_1(self, state: AuctionState) -> int:
        return min(max(0, self._value(state) - MIN_BID_INCREMENT), state.my_budget)

    def choose_bid_round_2(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        if not self._triggered_fair_opener and state.item.value + 800_000 <= opponent_bid <= state.item.value + 1_200_000:
            self._triggered_fair_opener = True
            return min(max(my_bid, opponent_bid + MIN_BID_INCREMENT), state.my_budget)
        return my_bid

    def choose_bid_round_3(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        target = opponent_bid + MIN_BID_INCREMENT
        if opponent_bid >= my_bid and target <= self._value(state):
            return min(target, state.my_budget)
        return my_bid


BOT_CLASS = CategoryValueBot
