"""Defensive META variant for unknown last-minute opponents.

This bot keeps the broad META valuation idea but makes opponent typing less
sticky than meta_strategist and preserves more late-game cash. It is intended
as a portfolio bot, not as a replacement for the tuned known-field specialist.
"""

from __future__ import annotations

from auction_game.interfaces import AuctionBot, AuctionItem, AuctionState, MIN_BID_INCREMENT

CATEGORIES = ("ai", "web", "brand", "cloud", "dev", "data")
DENIAL_WEIGHT = 0.55
R1_RATIO = 0.72
PASSIVE_R1_RATIO = 0.68


def _bonus_rate(count: int) -> float:
    return min(0.06 * max(0, count - 1) + 0.02 * max(0, count - 3), 0.30)


def _category_bonus(count: int, total_value: int) -> int:
    return int(total_value * _bonus_rate(count))


def _bonus_gain(count: int, total_value: int, item_value: int) -> int:
    return _category_bonus(count + 1, total_value + item_value) - _category_bonus(count, total_value)


def _category_state(items: tuple[AuctionItem, ...], category: str) -> tuple[int, int]:
    return (
        sum(1 for item in items if item.category == category),
        sum(item.value for item in items if item.category == category),
    )


def _remaining_in_category(state: AuctionState, category: str) -> int:
    return sum(
        1
        for index in range(state.round_index + 1, state.total_rounds)
        if CATEGORIES[index % len(CATEGORIES)] == category
    )


class MetaGuardianBot(AuctionBot):
    def __init__(self) -> None:
        self._items_seen: list[AuctionItem] = []
        self._retaliator = False
        self._low_open_samples = 0
        self._high_open_samples = 0
        self._round_2_seen: set[int] = set()
        self._mirror = False

    def _remember(self, state: AuctionState) -> None:
        if len(self._items_seen) == state.round_index:
            self._items_seen.append(state.item)

    def _observe_open(self, state: AuctionState, opponent_bid: int) -> None:
        if state.round_index in self._round_2_seen:
            return
        self._round_2_seen.add(state.round_index)

        value = max(1, state.item.value)
        if value * 25 // 100 <= opponent_bid <= value * 45 // 100:
            self._low_open_samples += 1
        if opponent_bid >= value * 70 // 100:
            self._high_open_samples += 1
        if opponent_bid > 0 and opponent_bid in state.my_bids[-3:]:
            self._mirror = True

    def _detect_retaliator(self, state: AuctionState) -> bool:
        if self._retaliator:
            return True
        for past_item, opp_r3 in zip(self._items_seen, state.opponent_bids):
            if opp_r3 == past_item.value * 95 // 100:
                self._retaliator = True
                return True
        return False

    def _is_passive(self) -> bool:
        return self._low_open_samples >= 3 and self._high_open_samples == 0 and not self._mirror

    def _is_aggressive(self) -> bool:
        return self._high_open_samples >= 2 and not self._is_passive()

    def _cap(self, state: AuctionState) -> int:
        item = state.item
        my_count, my_value = _category_state(state.my_items, item.category)
        op_count, op_value = _category_state(state.opponent_items, item.category)
        remaining = _remaining_in_category(state, item.category)

        own_gain = _bonus_gain(my_count, my_value, item.value)
        denial_gain = _bonus_gain(op_count, op_value, item.value)
        high_leverage = (
            (my_count + 1) in (2, 3, 4)
            or (op_count + 1) in (2, 3, 4)
            or (remaining == 0 and (my_count >= 1 or op_count >= 1))
        )

        cap = item.value + own_gain + int(DENIAL_WEIGHT * denial_gain)
        if my_count == 0 and remaining >= 1 and not self._is_passive():
            cap += min(remaining, 2) * 300_000
        if (my_count + 1) in (3, 4):
            cap += 700_000
        if (op_count + 1) in (2, 3, 4):
            cap += 900_000
        if remaining == 0 and (my_count >= 1 or op_count >= 1):
            cap += item.value // 16

        if self._is_passive():
            cap = min(cap, max(item.value, item.value + own_gain))
        if self._is_aggressive():
            if high_leverage:
                cap = max(cap, item.value * 116 // 100)
            else:
                cap = max(cap, item.value * 102 // 100)

        rounds_left = max(1, state.total_rounds - state.round_index)
        per_round = state.my_budget / rounds_left
        soft_cap = int(per_round * (1.55 if rounds_left <= 5 else 1.35))
        budget_cap = max(soft_cap, int(item.value * (1.18 if high_leverage else 1.05)))

        reserve = 0
        if rounds_left > 4 and state.round_index >= 8:
            reserve = 13_000_000
        if rounds_left > 7 and self._is_aggressive():
            reserve = max(reserve, 18_000_000)
        spendable = max(0, state.my_budget - reserve)
        return max(0, min(cap, budget_cap, spendable if spendable else state.my_budget))

    def _opp_has_escalated(self, state: AuctionState) -> bool:
        return any(opp > mine for opp, mine in zip(state.opponent_bids, state.my_bids))

    def choose_bid_round_1(self, state: AuctionState) -> int:
        self._remember(state)
        if self._detect_retaliator(state):
            return 0
        ratio = PASSIVE_R1_RATIO if self._is_passive() else R1_RATIO
        if self._is_aggressive():
            ratio = 0.78
        return min(int(self._cap(state) * ratio), state.my_budget)

    def choose_bid_round_2(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        self._observe_open(state, opponent_bid)
        if self._detect_retaliator(state):
            return my_bid
        if opponent_bid <= my_bid:
            return my_bid
        target = opponent_bid + MIN_BID_INCREMENT
        if target > self._cap(state) or target > state.my_budget:
            return my_bid
        return target

    def choose_bid_round_3(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        if self._detect_retaliator(state):
            target = opponent_bid + MIN_BID_INCREMENT
            return max(my_bid, target) if target <= state.my_budget else my_bid

        cap = self._cap(state)
        if opponent_bid >= my_bid:
            target = opponent_bid + MIN_BID_INCREMENT
        else:
            if self._is_aggressive():
                target = my_bid + MIN_BID_INCREMENT
            elif self._is_passive():
                if my_bid >= state.item.value:
                    return my_bid
                target = my_bid + 2 * MIN_BID_INCREMENT
            elif not self._opp_has_escalated(state):
                return my_bid
            else:
                target = my_bid + MIN_BID_INCREMENT
        if target > cap or target > state.my_budget:
            return my_bid
        return target


BOT_CLASS = MetaGuardianBot
