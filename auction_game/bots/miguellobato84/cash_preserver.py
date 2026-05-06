from __future__ import annotations

from auction_game.interfaces import AuctionBot, AuctionState, MIN_BID_INCREMENT


class CashPreserverBot(AuctionBot):
    """Conservative bidder that protects cash early and only escalates on strong items."""

    _MINIMUM_BUFFER_PER_REMAINING_ROUND = 8_000_000

    def _rounds_left(self, state: AuctionState) -> int:
        return max(1, state.total_rounds - state.round_index)

    def _progress(self, state: AuctionState) -> float:
        if state.total_rounds <= 1:
            return 1.0
        return state.round_index / max(1, state.total_rounds - 1)

    def _reserve_for_future(self, state: AuctionState) -> int:
        rounds_left = self._rounds_left(state)
        return max(0, (rounds_left - 1) * self._MINIMUM_BUFFER_PER_REMAINING_ROUND)

    def _budget_pace(self, state: AuctionState) -> int:
        rounds_left = self._rounds_left(state)
        return max(1, state.my_budget // rounds_left)

    def _spend_cap(self, state: AuctionState) -> int:
        rounds_left = self._rounds_left(state)
        budget_pace = self._budget_pace(state)
        reserve = max(self._reserve_for_future(state), budget_pace)
        if rounds_left <= 2:
            reserve = max(0, reserve - budget_pace // 3)
        return max(0, state.my_budget - reserve)

    def _is_high_value(self, state: AuctionState) -> bool:
        rounds_left = self._rounds_left(state)
        item_value = state.item.value
        if item_value >= 14_500_000:
            return True
        if rounds_left <= 2 and item_value >= 11_500_000:
            return True
        if rounds_left <= 4 and item_value >= 12_500_000:
            return True
        return False

    def _should_press(self, state: AuctionState) -> bool:
        return self._is_high_value(state) or self._rounds_left(state) <= 4

    def _target_bid(self, state: AuctionState) -> int:
        rounds_left = self._rounds_left(state)
        pace = self._budget_pace(state)
        urgency = self._progress(state)
        item_value = state.item.value
        reserve_cap = max(0, state.my_budget - self._reserve_for_future(state))

        # Start from a restrained share of the per-round budget and only climb
        # when the item is clearly worth it.
        target = int(pace * (0.32 + 0.18 * urgency))
        target = max(target, 4_000_000 + int(urgency * 2_000_000))

        if item_value >= 14_500_000:
            target = max(target, int(item_value * (0.82 + 0.08 * urgency)))
        elif item_value >= 13_000_000:
            target = max(target, int(item_value * (0.68 + 0.08 * urgency)))
        elif rounds_left <= 4:
            target = max(target, int(item_value * (0.58 + 0.08 * urgency)))
        else:
            target = min(target, int(item_value * 0.55))

        if rounds_left <= 3:
            target = max(target, int(item_value * 0.72))
        if rounds_left <= 2:
            target = max(target, int(item_value * 0.84))

        spend_cap = self._spend_cap(state)
        return min(max(target, 0), state.my_budget, reserve_cap if reserve_cap > 0 else state.my_budget, spend_cap if spend_cap > 0 else state.my_budget)

    def _escalation_bid(self, state: AuctionState, current_bid: int, opponent_bid: int) -> int:
        target = self._target_bid(state)
        if target <= current_bid:
            return current_bid
        if not self._should_press(state):
            return current_bid

        required = opponent_bid + MIN_BID_INCREMENT
        if required > target:
            return current_bid
        spend_cap = self._spend_cap(state)
        if spend_cap <= current_bid:
            return current_bid
        return min(target, state.my_budget, spend_cap)

    def choose_bid_round_1(self, state: AuctionState) -> int:
        return self._target_bid(state)

    def choose_bid_round_2(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        if opponent_bid <= my_bid:
            return my_bid
        return self._escalation_bid(state, my_bid, opponent_bid)

    def choose_bid_round_3(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        if opponent_bid <= my_bid:
            return my_bid
        return self._escalation_bid(state, my_bid, opponent_bid)


BOT_CLASS = CashPreserverBot
