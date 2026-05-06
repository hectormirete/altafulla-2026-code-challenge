"""High-ceiling specialist for the defensive bot portfolio.

This bot is intentionally not tuned for the current visible leaderboard. Its
job is to hedge against last-minute category builders that bid around
110-115% of item value and beat conservative META-style caps.
"""

from __future__ import annotations

from auction_game.interfaces import AuctionBot, AuctionItem, AuctionState, MIN_BID_INCREMENT

CATEGORIES = ("ai", "web", "brand", "cloud", "dev", "data")


def _bonus_rate(count: int) -> float:
    return min(0.06 * max(0, count - 1) + 0.02 * max(0, count - 3), 0.30)


def _category_bonus(count: int, total_value: int) -> int:
    return int(total_value * _bonus_rate(count))


def _category_state(items: tuple[AuctionItem, ...], category: str) -> tuple[int, int]:
    return (
        sum(1 for item in items if item.category == category),
        sum(item.value for item in items if item.category == category),
    )


def _bonus_gain(items: tuple[AuctionItem, ...], item: AuctionItem) -> int:
    count, value = _category_state(items, item.category)
    return _category_bonus(count + 1, value + item.value) - _category_bonus(count, value)


def _remaining_in_category(state: AuctionState, category: str) -> int:
    return sum(
        1
        for index in range(state.round_index + 1, state.total_rounds)
        if CATEGORIES[index % len(CATEGORIES)] == category
    )


class MetaRatcheterBot(AuctionBot):
    def __init__(self) -> None:
        self._items_seen: list[AuctionItem] = []
        self._retaliator = False
        self._high_open_samples = 0
        self._round_2_seen: set[int] = set()

    def _remember(self, state: AuctionState) -> None:
        if len(self._items_seen) == state.round_index:
            self._items_seen.append(state.item)

    def _observe_open(self, state: AuctionState, opponent_bid: int) -> None:
        if state.round_index in self._round_2_seen:
            return
        self._round_2_seen.add(state.round_index)
        if opponent_bid >= state.item.value * 80 // 100:
            self._high_open_samples += 1

    def _detect_retaliator(self, state: AuctionState) -> bool:
        if self._retaliator:
            return True
        for past_item, opp_r3 in zip(self._items_seen, state.opponent_bids):
            if opp_r3 == past_item.value * 95 // 100:
                self._retaliator = True
                return True
        return False

    def _is_high_pressure(self) -> bool:
        return self._high_open_samples >= 2

    def _is_leverage_item(self, state: AuctionState) -> bool:
        my_count, _ = _category_state(state.my_items, state.item.category)
        op_count, _ = _category_state(state.opponent_items, state.item.category)
        remaining = _remaining_in_category(state, state.item.category)
        return (
            (my_count + 1) in (2, 3, 4)
            or (op_count + 1) in (2, 3, 4)
            or (remaining == 0 and (my_count > 0 or op_count > 0))
        )

    def _ceiling(self, state: AuctionState) -> int:
        item = state.item
        leverage = self._is_leverage_item(state)
        own_gain = _bonus_gain(state.my_items, item)
        denial_gain = _bonus_gain(state.opponent_items, item)

        if leverage:
            ceiling = max(item.value * 113 // 100, item.value + own_gain + denial_gain)
        else:
            ceiling = max(item.value * 104 // 100, item.value + own_gain)

        if self._is_high_pressure() and leverage:
            ceiling = max(ceiling, item.value * 114 // 100)

        rounds_left = max(1, state.total_rounds - state.round_index)
        if rounds_left > 4 and state.round_index >= 10 and not leverage:
            ceiling = min(ceiling, max(0, state.my_budget - 10_000_000))
        if rounds_left <= 3:
            ceiling = max(ceiling, item.value * 115 // 100)

        return max(0, min(ceiling, state.my_budget))

    def choose_bid_round_1(self, state: AuctionState) -> int:
        self._remember(state)
        if self._detect_retaliator(state):
            return 0

        my_count, _ = _category_state(state.my_items, state.item.category)
        op_count, _ = _category_state(state.opponent_items, state.item.category)
        if my_count > 0 or op_count > 0:
            ratio = 108
        elif self._is_high_pressure():
            ratio = 98
        else:
            ratio = 92
        return min(state.item.value * ratio // 100, self._ceiling(state), state.my_budget)

    def choose_bid_round_2(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        self._observe_open(state, opponent_bid)
        if self._detect_retaliator(state):
            return my_bid
        if opponent_bid <= my_bid:
            return my_bid
        target = opponent_bid + MIN_BID_INCREMENT
        if target > self._ceiling(state) or target > state.my_budget:
            return my_bid
        return target

    def choose_bid_round_3(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        if self._detect_retaliator(state):
            target = opponent_bid + MIN_BID_INCREMENT
            return max(my_bid, target) if target <= state.my_budget else my_bid
        if opponent_bid <= my_bid:
            return my_bid
        target = opponent_bid + MIN_BID_INCREMENT
        if target > self._ceiling(state) or target > state.my_budget:
            return my_bid
        return target


BOT_CLASS = MetaRatcheterBot
