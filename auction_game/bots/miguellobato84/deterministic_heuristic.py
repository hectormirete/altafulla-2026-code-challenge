from __future__ import annotations

from auction_game.interfaces import AuctionBot, AuctionState, MIN_BID_INCREMENT


class DeterministicHeuristicBot(AuctionBot):
    def _rounds_left(self, state: AuctionState) -> int:
        return max(1, state.total_rounds - state.round_index)

    def _budget_share(self, state: AuctionState) -> int:
        return max(1, state.my_budget // self._rounds_left(state))

    def _spend_cap(self, state: AuctionState) -> int:
        rounds_left = self._rounds_left(state)
        budget_share = self._budget_share(state)
        reserve = budget_share
        if rounds_left > 4:
            reserve += budget_share // 2
        if rounds_left <= 2:
            reserve -= budget_share // 3
        return max(0, state.my_budget - max(0, reserve))

    def _category_state(self, items: tuple, category: str) -> tuple[int, int]:
        count = 0
        total_value = 0
        for item in items:
            if item.category == category:
                count += 1
                total_value += item.value
        return count, total_value

    def _category_bonus_rate(self, item_count: int) -> float:
        raw_rate = 0.06 * max(0, item_count - 1) + 0.02 * max(0, item_count - 3)
        return min(raw_rate, 0.30)

    def _marginal_bonus_gain(self, current_count: int, current_value: int, item_value: int) -> int:
        before = int(current_value * self._category_bonus_rate(current_count))
        after = int((current_value + item_value) * self._category_bonus_rate(current_count + 1))
        return after - before

    def _category_pressure(self, state: AuctionState) -> int:
        my_count, my_value = self._category_state(state.my_items, state.item.category)
        opp_count, opp_value = self._category_state(state.opponent_items, state.item.category)
        my_gain = self._marginal_bonus_gain(my_count, my_value, state.item.value)
        opp_gain = self._marginal_bonus_gain(opp_count, opp_value, state.item.value)
        return my_gain - max(0, opp_gain // 2)

    def _opening_bid(self, state: AuctionState) -> int:
        value = state.item.value
        rounds_left = self._rounds_left(state)
        budget_share = self._budget_share(state)
        category_pressure = self._category_pressure(state)

        if value >= 15_500_000:
            ratio = 0.60
        elif value >= 13_500_000:
            ratio = 0.53
        elif value >= 11_500_000:
            ratio = 0.46
        else:
            ratio = 0.38

        if rounds_left <= 3:
            ratio += 0.05
        elif rounds_left <= 6:
            ratio += 0.02

        if category_pressure > 0:
            ratio += min(0.08, category_pressure / max(1, value) * 0.7)

        target = int(value * ratio)
        target = max(target, value // 4)
        target = max(target, budget_share // 2)

        if state.opponent_budget > state.my_budget:
            target = max(target, value // 3)

        cap = budget_share if rounds_left <= 2 else max(budget_share // 2, int(value * 0.70))
        spend_cap = self._spend_cap(state)
        return min(state.my_budget, max(0, min(target, cap, spend_cap)))

    def _should_press(self, state: AuctionState, my_bid: int, opponent_bid: int) -> bool:
        if opponent_bid <= my_bid:
            return False

        value = state.item.value
        category_pressure = self._category_pressure(state)

        if value >= 15_000_000:
            return True
        if category_pressure > value // 20:
            return True
        if state.round_index >= state.total_rounds - 2:
            return value >= 11_000_000 or opponent_bid >= my_bid + MIN_BID_INCREMENT
        if state.opponent_budget > state.my_budget and value >= 12_500_000:
            return True
        return opponent_bid >= my_bid + 2_000_000

    def _follow_up_bid(self, state: AuctionState, my_bid: int, opponent_bid: int, round_multiplier: float) -> int:
        if not self._should_press(state, my_bid, opponent_bid):
            return my_bid

        value = state.item.value
        rounds_left = self._rounds_left(state)
        budget_share = self._budget_share(state)
        category_pressure = self._category_pressure(state)
        target_floor = max(my_bid, opponent_bid + MIN_BID_INCREMENT)

        if value >= 16_000_000:
            ceiling_ratio = 0.92
        elif value >= 14_000_000:
            ceiling_ratio = 0.82
        elif value >= 12_000_000:
            ceiling_ratio = 0.70
        else:
            ceiling_ratio = 0.58

        if rounds_left <= 2:
            ceiling_ratio += 0.08
        elif rounds_left <= 5:
            ceiling_ratio += 0.03

        if category_pressure > 0:
            ceiling_ratio += min(0.06, category_pressure / max(1, value) * 0.5)

        if state.opponent_budget > state.my_budget:
            ceiling_ratio += 0.03

        target = int(value * min(0.98, ceiling_ratio))
        target = max(target, int(value * round_multiplier))
        target = max(target, budget_share)
        target = max(target, target_floor)

        if state.round_index >= state.total_rounds - 1:
            target = max(target, int(value * 0.65))

        return min(state.my_budget, max(my_bid, target, min(self._spend_cap(state), state.my_budget)))

    def choose_bid_round_1(self, state: AuctionState) -> int:
        return self._opening_bid(state)

    def choose_bid_round_2(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        return self._follow_up_bid(state, my_bid, opponent_bid, 0.52)

    def choose_bid_round_3(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        return self._follow_up_bid(state, my_bid, opponent_bid, 0.60)


BOT_CLASS = DeterministicHeuristicBot
