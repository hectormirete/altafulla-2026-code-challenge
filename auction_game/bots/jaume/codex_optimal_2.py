from __future__ import annotations

from auction_game import AuctionBot, AuctionItem, AuctionState, MIN_BID_INCREMENT


class CodexOptimal2Bot(AuctionBot):
    """Mirror-safe successor to codex_optimal with adaptive scoring mode."""

    def __init__(self) -> None:
        self._opponent_overpay_events = 0
        self._opponent_chase_events = 0
        self._opponent_led_round_2 = False

    def choose_bid_round_1(self, state: AuctionState) -> int:
        ceiling = self._ceiling(state, opponent_bid=0, final_round=False)
        opener = min(ceiling, int(self._own_effective_value(state) * self._opener_rate(state)))
        if self._opponent_overpay_events:
            opener = min(opener, int(state.item.value * 0.82))
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
        if opponent_bid <= my_bid:
            return min(my_bid, state.my_budget)

        required = opponent_bid + MIN_BID_INCREMENT
        if required > state.my_budget:
            return min(my_bid, state.my_budget)

        ceiling = self._ceiling(state, opponent_bid=opponent_bid, final_round=final_round)
        if required <= ceiling:
            return required
        return min(my_bid, state.my_budget)

    def _ceiling(self, state: AuctionState, *, opponent_bid: int, final_round: bool) -> int:
        own_value = self._own_effective_value(state)
        opponent_value = self._opponent_effective_value(state)
        opponent_profit = max(0, opponent_value - opponent_bid)

        denial_weight = 0.48 if final_round else 0.22
        if self._opponent_overpay_events:
            denial_weight *= 0.55
        if self._opponent_chase_events >= 2:
            denial_weight *= 0.75

        ceiling = own_value + int(opponent_profit * denial_weight)
        ceiling = min(ceiling, self._budget_pacing_ceiling(state))
        return self._clamp(ceiling, 0, state.my_budget)

    def _own_effective_value(self, state: AuctionState) -> int:
        marginal = self._marginal_category_bonus(state.my_items, state.item)
        future = self._future_category_option_value(state, state.my_items)
        endgame = self._endgame_pressure(state)
        return state.item.value + marginal + future + endgame

    def _opponent_effective_value(self, state: AuctionState) -> int:
        marginal = self._marginal_category_bonus(state.opponent_items, state.item)
        future = self._future_category_option_value(state, state.opponent_items)
        return state.item.value + marginal + int(future * 0.75)

    def _budget_pacing_ceiling(self, state: AuctionState) -> int:
        rounds_left = max(1, state.total_rounds - state.round_index)
        remaining_after_this = rounds_left - 1

        if remaining_after_this == 0:
            return state.my_budget

        expected_future_need = remaining_after_this * 9_500_000
        spendable = max(state.my_budget - expected_future_need, state.my_budget // rounds_left)

        item_quality = state.item.value / 16_000_000
        if item_quality >= 0.88:
            spendable += int(state.item.value * 0.45)
        elif item_quality <= 0.62:
            spendable -= int(state.item.value * 0.25)

        if state.my_budget > state.opponent_budget + 20_000_000:
            spendable += 2_000_000
        elif state.my_budget + 20_000_000 < state.opponent_budget:
            spendable -= 2_000_000

        return self._clamp(spendable, 0, state.my_budget)

    def _future_category_option_value(self, state: AuctionState, owned_items: tuple[AuctionItem, ...]) -> int:
        future_same_category = 0
        index = state.round_index + 6
        while index < state.total_rounds:
            future_same_category += 1
            index += 6

        if future_same_category == 0:
            return 0

        count = sum(1 for item in owned_items if item.category == state.item.category)
        if count == 0:
            return int(state.item.value * 0.075 * future_same_category)
        if count == 1:
            return int(state.item.value * 0.060 * future_same_category)
        if count == 2:
            return int(state.item.value * 0.040 * future_same_category)
        return int(state.item.value * 0.015 * future_same_category)

    def _endgame_pressure(self, state: AuctionState) -> int:
        rounds_left = state.total_rounds - state.round_index
        if rounds_left <= 2 and state.my_budget > state.opponent_budget:
            return min(2_000_000, (state.my_budget - state.opponent_budget) // 8)
        if rounds_left <= 3 and state.my_budget > 25_000_000:
            return 1_000_000
        return 0

    def _mirror_candidate(self, state: AuctionState) -> bool:
        return (
            state.my_budget == state.opponent_budget
            and len(state.my_items) == len(state.opponent_items) == 0
            and state.my_bids == state.opponent_bids
        )

    def _opener_rate(self, state: AuctionState) -> float:
        if self._mirror_candidate(state):
            return 0.78
        return 0.776

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


BOT_CLASS = CodexOptimal2Bot
