from __future__ import annotations

from auction_game import AuctionBot, AuctionItem, AuctionState, MIN_BID_INCREMENT


class B2Bot(AuctionBot):
    """Score-aware Bellman successor with tighter pacing and denial control."""

    _CATEGORY_ORDER = ("ai", "web", "brand", "cloud", "dev", "data")

    def __init__(self) -> None:
        self._opponent_overpay_events = 0
        self._opponent_chase_events = 0
        self._opponent_led_round_2 = False

    def choose_bid_round_1(self, state: AuctionState) -> int:
        ceiling = self._ceiling(state, opponent_bid=0, final_round=False)
        opener = min(ceiling, int(self._own_effective_value(state) * self._opener_rate(state)))
        if self._opponent_overpay_events:
            opener = min(opener, int(state.item.value * 0.80))
        return self._clamp(opener, 0, state.my_budget)

    def choose_bid_round_2(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        self._opponent_led_round_2 = opponent_bid > my_bid
        self._observe_opponent_bid(state, opponent_bid)
        return self._raise_if_worthwhile(state, my_bid, opponent_bid, final_round=False)

    def choose_bid_round_3(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        if self._opponent_led_round_2 and opponent_bid >= my_bid + MIN_BID_INCREMENT:
            self._opponent_chase_events += 1
        self._observe_opponent_bid(state, opponent_bid)
        return self._raise_if_worthwhile(state, my_bid, opponent_bid, final_round=True)

    def _raise_if_worthwhile(
        self,
        state: AuctionState,
        my_bid: int,
        opponent_bid: int,
        *,
        final_round: bool,
    ) -> int:
        ceiling = self._ceiling(state, opponent_bid=opponent_bid, final_round=final_round)

        if final_round and opponent_bid == my_bid:
            tie_break = my_bid + MIN_BID_INCREMENT
            if tie_break <= ceiling and tie_break <= state.my_budget:
                return tie_break
            return min(my_bid, state.my_budget)

        if opponent_bid <= my_bid:
            return min(my_bid, state.my_budget)

        required = opponent_bid + MIN_BID_INCREMENT
        if required > state.my_budget:
            return min(my_bid, state.my_budget)
        if required <= ceiling:
            return required
        return min(my_bid, state.my_budget)

    def _ceiling(self, state: AuctionState, *, opponent_bid: int, final_round: bool) -> int:
        own_value = self._own_effective_value(state)
        opponent_value = self._opponent_effective_value(state)
        opponent_profit = max(0, opponent_value - opponent_bid)

        denial_weight = 0.48 if final_round else 0.24
        if self._opponent_overpay_events:
            denial_weight *= 0.60
        if self._opponent_chase_events >= 2:
            denial_weight *= 0.75

        ceiling = own_value + int(opponent_profit * denial_weight)
        ceiling = min(ceiling, self._budget_pacing_ceiling(state, final_round=final_round))
        return self._clamp(ceiling, 0, state.my_budget)

    def _own_effective_value(self, state: AuctionState) -> int:
        marginal = self._marginal_category_bonus(state.my_items, state.item)
        future = self._future_category_option_value(state, state.my_items)
        return state.item.value + marginal + future + self._score_pressure(state) + self._endgame_pressure(state)

    def _opponent_effective_value(self, state: AuctionState) -> int:
        marginal = self._marginal_category_bonus(state.opponent_items, state.item)
        future = self._future_category_option_value(state, state.opponent_items)
        return state.item.value + marginal + int(future * 0.75)

    def _budget_pacing_ceiling(self, state: AuctionState, *, final_round: bool) -> int:
        rounds_left = max(1, state.total_rounds - state.round_index)
        remaining_after_this = rounds_left - 1
        if remaining_after_this == 0:
            return state.my_budget

        reserve = self._per_round_reserve(state)
        expected_future_need = remaining_after_this * reserve
        spendable = max(state.my_budget - expected_future_need, state.my_budget // rounds_left)

        item_quality = state.item.value / 16_000_000
        if item_quality >= 0.90:
            spendable += int(state.item.value * 0.42)
        elif item_quality <= 0.65:
            spendable -= int(state.item.value * 0.22)

        if self._is_category_live(state, state.my_items):
            spendable += int(state.item.value * 0.18)
        if final_round:
            spendable += MIN_BID_INCREMENT

        my_score = self._portfolio_score(state.my_items, state.my_budget)
        opp_score = self._portfolio_score(state.opponent_items, state.opponent_budget)
        if my_score + 18_000_000 < opp_score:
            spendable += 2_500_000
        elif my_score > opp_score + 18_000_000:
            spendable -= 2_000_000

        return self._clamp(spendable, 0, state.my_budget)

    def _future_category_option_value(self, state: AuctionState, owned_items: tuple[AuctionItem, ...]) -> int:
        future_same_category = self._remaining_category_count(state, state.item.category)
        if future_same_category == 0:
            return 0

        count = sum(1 for item in owned_items if item.category == state.item.category)
        if count == 0:
            return int(state.item.value * 0.07 * future_same_category)
        if count == 1:
            return int(state.item.value * 0.08 * future_same_category)
        if count == 2:
            return int(state.item.value * 0.05 * future_same_category)
        return int(state.item.value * 0.02 * future_same_category)

    def _remaining_category_count(self, state: AuctionState, category: str) -> int:
        return sum(
            1
            for future_round in range(state.round_index + 1, state.total_rounds)
            if self._CATEGORY_ORDER[future_round % len(self._CATEGORY_ORDER)] == category
        )

    def _is_category_live(self, state: AuctionState, owned_items: tuple[AuctionItem, ...]) -> bool:
        owned = sum(1 for item in owned_items if item.category == state.item.category)
        return owned >= 1 or self._remaining_category_count(state, state.item.category) >= 2

    def _score_pressure(self, state: AuctionState) -> int:
        my_score = self._portfolio_score(state.my_items, state.my_budget)
        opp_score = self._portfolio_score(state.opponent_items, state.opponent_budget)
        gap = my_score - opp_score
        rounds_left = state.total_rounds - state.round_index

        if gap <= -30_000_000:
            return min(4_000_000, (-gap) // max(3, rounds_left))
        if gap < 0:
            return min(2_000_000, (-gap) // 10)
        if gap >= 30_000_000:
            return -min(2_000_000, gap // 12)
        return 0

    def _endgame_pressure(self, state: AuctionState) -> int:
        rounds_left = state.total_rounds - state.round_index
        if rounds_left <= 2 and state.my_budget > state.opponent_budget:
            return min(2_500_000, (state.my_budget - state.opponent_budget) // 8)
        if rounds_left <= 3 and state.my_budget > 22_000_000:
            return 1_000_000
        return 0

    def _opener_rate(self, state: AuctionState) -> float:
        if state.total_rounds - state.round_index <= 4:
            return 0.75
        return 0.72

    def _per_round_reserve(self, state: AuctionState) -> int:
        rounds_left = state.total_rounds - state.round_index
        if rounds_left <= 4:
            return 7_000_000
        if state.my_budget < state.opponent_budget:
            return 8_500_000
        return 9_500_000

    def _marginal_category_bonus(self, items: tuple[AuctionItem, ...], item: AuctionItem) -> int:
        category_value = 0
        category_count = 0
        for owned in items:
            if owned.category == item.category:
                category_value += owned.value
                category_count += 1

        current_bonus = int(category_value * self._category_bonus_rate(category_count))
        next_bonus = int((category_value + item.value) * self._category_bonus_rate(category_count + 1))
        return next_bonus - current_bonus

    def _portfolio_score(self, items: tuple[AuctionItem, ...], budget: int) -> int:
        item_value = sum(item.value for item in items)
        category_values: dict[str, int] = {}
        category_counts: dict[str, int] = {}
        for item in items:
            category_values[item.category] = category_values.get(item.category, 0) + item.value
            category_counts[item.category] = category_counts.get(item.category, 0) + 1

        bonus = 0
        for category, total_value in category_values.items():
            bonus += int(total_value * self._category_bonus_rate(category_counts[category]))
        return item_value + bonus + budget

    def _observe_opponent_bid(self, state: AuctionState, opponent_bid: int) -> None:
        if opponent_bid > self._opponent_effective_value(state) + 2_000_000:
            self._opponent_overpay_events += 1

    @staticmethod
    def _category_bonus_rate(item_count: int) -> float:
        raw_rate = 0.06 * max(0, item_count - 1) + 0.02 * max(0, item_count - 3)
        return min(raw_rate, 0.30)

    @staticmethod
    def _clamp(value: int | float, lower: int, upper: int) -> int:
        return int(min(max(value, lower), upper))


BOT_CLASS = B2Bot
