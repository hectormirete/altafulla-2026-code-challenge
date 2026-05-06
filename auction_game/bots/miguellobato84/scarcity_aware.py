from __future__ import annotations

from auction_game.interfaces import AuctionBot, AuctionState, MIN_BID_INCREMENT


class ScarcityAwareBot(AuctionBot):
    """
    Bid more aggressively when the current category is scarce in the remaining
    slate or when the next win meaningfully advances a category bonus.
    """

    CATEGORY_ORDER = ("ai", "web", "brand", "cloud", "dev", "data")

    def _rounds_left(self, state: AuctionState) -> int:
        return max(1, state.total_rounds - state.round_index)

    def _progress(self, state: AuctionState) -> float:
        if state.total_rounds <= 1:
            return 1.0
        return state.round_index / max(1, state.total_rounds - 1)

    def _budget_pace(self, state: AuctionState) -> int:
        return max(1, state.my_budget // self._rounds_left(state))

    def _spend_cap(self, state: AuctionState) -> int:
        rounds_left = self._rounds_left(state)
        pace = self._budget_pace(state)
        reserve = pace
        if rounds_left > 4:
            reserve += pace // 2
        if rounds_left <= 2:
            reserve -= pace // 3
        return max(0, state.my_budget - max(0, reserve))

    def _category_totals(self, items: tuple) -> tuple[dict[str, int], dict[str, int]]:
        counts: dict[str, int] = {}
        values: dict[str, int] = {}
        for item in items:
            counts[item.category] = counts.get(item.category, 0) + 1
            values[item.category] = values.get(item.category, 0) + item.value
        return counts, values

    def _future_category_counts(self, state: AuctionState) -> dict[str, int]:
        remaining_rounds = self._rounds_left(state)
        start_index = state.round_index % len(self.CATEGORY_ORDER)
        counts = {category: 0 for category in self.CATEGORY_ORDER}

        for offset in range(remaining_rounds):
            category = self.CATEGORY_ORDER[(start_index + offset) % len(self.CATEGORY_ORDER)]
            counts[category] += 1

        return counts

    def _category_bonus_rate(self, item_count: int) -> float:
        return min(0.06 * max(0, item_count - 1) + 0.02 * max(0, item_count - 3), 0.30)

    def _marginal_bonus_gain(self, current_count: int, current_value: int, item_value: int) -> int:
        before = int(current_value * self._category_bonus_rate(current_count))
        after = int((current_value + item_value) * self._category_bonus_rate(current_count + 1))
        return after - before

    def _category_pressure(self, state: AuctionState) -> tuple[int, int, int, int, int, int]:
        my_counts, my_values = self._category_totals(state.my_items)
        opp_counts, opp_values = self._category_totals(state.opponent_items)
        future_counts = self._future_category_counts(state)

        category = state.item.category
        my_count = my_counts.get(category, 0)
        my_value = my_values.get(category, 0)
        opp_count = opp_counts.get(category, 0)
        opp_value = opp_values.get(category, 0)
        remaining_slots = future_counts.get(category, 0)
        bonus_gain = self._marginal_bonus_gain(my_count, my_value, state.item.value)
        return my_count, my_value, opp_count, opp_value, remaining_slots, bonus_gain

    def _scarcity_factor(self, remaining_slots: int) -> float:
        if remaining_slots <= 0:
            return 1.25
        if remaining_slots == 1:
            return 1.45
        if remaining_slots == 2:
            return 1.25
        if remaining_slots == 3:
            return 1.10
        if remaining_slots == 4:
            return 1.00
        return 0.88

    def _target_bid(self, state: AuctionState) -> int:
        my_count, my_value, opp_count, opp_value, remaining_slots, bonus_gain = self._category_pressure(state)
        rounds_left = self._rounds_left(state)
        value = state.item.value
        pace = self._budget_pace(state)
        scarcity = self._scarcity_factor(remaining_slots)

        bonus_ratio = bonus_gain / max(1, value)
        progress = self._progress(state)

        target_ratio = 0.36 + 0.12 * bonus_ratio
        target_ratio += 0.10 * (1.0 - min(1.0, remaining_slots / 4))
        target_ratio += 0.10 * progress

        if my_count > 0:
            target_ratio += 0.05 * min(my_count, 3)
            target_ratio += 0.04 * min(bonus_ratio * 10, 2.0)
        else:
            target_ratio += 0.03 * min(opp_count, 2)

        if opp_count >= my_count:
            target_ratio += 0.04 * min(opp_count - my_count + 1, 3)
        if opp_value >= my_value and opp_count > 0:
            target_ratio += 0.02
        if remaining_slots <= 2:
            target_ratio += 0.06
        if rounds_left <= 3:
            target_ratio += 0.07
        if value >= 14_000_000:
            target_ratio += 0.04

        target_ratio *= scarcity

        target = int(value * target_ratio) + int(bonus_gain * 0.70)
        if remaining_slots <= 2 and bonus_gain > 0:
            target += bonus_gain // 2

        if my_count > 0:
            target += int(value * 0.04 * min(my_count, 3))

        budget_floor = min(state.my_budget, max(0, pace))
        if rounds_left <= 2:
            budget_floor = max(budget_floor, state.my_budget // 2)
        elif rounds_left <= 4:
            budget_floor = max(budget_floor, pace // 2)

        return min(state.my_budget, max(target, budget_floor, value // 3), self._spend_cap(state))

    def _follow_up_bid(self, state: AuctionState, my_bid: int, opponent_bid: int, stage: int) -> int:
        if opponent_bid <= my_bid:
            if stage == 3:
                target = self._target_bid(state)
                if target > my_bid:
                    return min(state.my_budget, target)
            return my_bid

        target = self._target_bid(state)
        if target <= my_bid:
            return my_bid

        my_count, my_value, opp_count, opp_value, remaining_slots, bonus_gain = self._category_pressure(state)
        pressure = 0.0
        if remaining_slots <= 2:
            pressure += 0.20
        if bonus_gain > 0:
            pressure += min(0.20, bonus_gain / max(1, state.item.value * 8))
        if my_count > 0:
            pressure += 0.08 * min(my_count, 3)
        if opp_count >= my_count:
            pressure += 0.06 * min(opp_count - my_count + 1, 3)
        if opp_value >= my_value:
            pressure += 0.04
        if stage == 3:
            pressure += 0.08

        if pressure < 0.12 and target <= opponent_bid + MIN_BID_INCREMENT:
            return my_bid

        ceiling = min(state.my_budget, int(target * (1.0 + min(0.12, pressure))), self._spend_cap(state))
        candidate = min(opponent_bid + MIN_BID_INCREMENT, ceiling, state.my_budget)
        if stage == 3 and candidate == my_bid and target > my_bid:
            candidate = min(state.my_budget, target)
        if self._spend_cap(state) <= my_bid:
            return my_bid
        return max(my_bid, candidate)

    def choose_bid_round_1(self, state: AuctionState) -> int:
        return self._target_bid(state)

    def choose_bid_round_2(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        return self._follow_up_bid(state, my_bid, opponent_bid, stage=2)

    def choose_bid_round_3(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        return self._follow_up_bid(state, my_bid, opponent_bid, stage=3)


BOT_CLASS = ScarcityAwareBot
