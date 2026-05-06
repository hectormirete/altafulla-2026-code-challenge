from __future__ import annotations

from auction_game.interfaces import AuctionBot, AuctionState, MIN_BID_INCREMENT


class EarlyDominationBot(AuctionBot):
    """
    Aggressive early-round bidder.

    The bot spends more freely on high-value items in the first part of the match
    to pressure the opponent into reactive bidding, while keeping a reserve for
    later rounds and never exceeding available budget.
    """

    EARLY_WINDOW_FRACTION = 0.40
    HIGH_VALUE_THRESHOLD = 14_000_000
    VERY_HIGH_VALUE_THRESHOLD = 15_500_000

    def _round_progress(self, state: AuctionState) -> float:
        if state.total_rounds <= 1:
            return 1.0
        return state.round_index / (state.total_rounds - 1)

    def _early_pressure(self, state: AuctionState) -> float:
        progress = self._round_progress(state)
        if progress >= self.EARLY_WINDOW_FRACTION:
            return 0.0
        return (self.EARLY_WINDOW_FRACTION - progress) / self.EARLY_WINDOW_FRACTION

    def _item_pressure(self, state: AuctionState) -> float:
        value = state.item.value
        if value >= self.VERY_HIGH_VALUE_THRESHOLD:
            return 1.0
        if value >= self.HIGH_VALUE_THRESHOLD:
            return 0.75
        if value >= 12_000_000:
            return 0.45
        return 0.15

    def _reserve_budget(self, state: AuctionState) -> int:
        rounds_left = max(1, state.total_rounds - state.round_index)
        base_reserve = state.my_budget // max(3, rounds_left // 2 + 1)
        late_game_floor = 4_000_000 if state.total_rounds >= 6 else 2_000_000
        return max(base_reserve, late_game_floor)

    def _spend_cap(self, state: AuctionState) -> int:
        rounds_left = max(1, state.total_rounds - state.round_index)
        budget_share = state.my_budget // rounds_left
        reserve = self._reserve_budget(state)
        if rounds_left > 4:
            reserve += budget_share // 2
        if rounds_left <= 2:
            reserve -= budget_share // 3
        return max(0, state.my_budget - max(0, reserve))

    def _target_bid(self, state: AuctionState) -> int:
        rounds_left = max(1, state.total_rounds - state.round_index)
        budget_share = state.my_budget // rounds_left
        base = max(state.item.value, budget_share)

        pressure = self._early_pressure(state)
        item_pressure = self._item_pressure(state)
        opponent_lead = max(0, state.opponent_budget - state.my_budget)

        aggression = 0.18 + (0.42 * pressure) + (0.30 * item_pressure)
        target = int(base * (1.0 + aggression))

        if pressure > 0.0:
            target += int(state.item.value * (0.10 + 0.10 * item_pressure))

        if state.item.value >= self.VERY_HIGH_VALUE_THRESHOLD:
            target = max(target, int(state.item.value * 1.35))
        elif state.item.value >= self.HIGH_VALUE_THRESHOLD:
            target = max(target, int(state.item.value * 1.20))

        if opponent_lead > 0 and pressure > 0.0:
            target += min(opponent_lead // 4, state.item.value // 2)

        reserve = self._reserve_budget(state)
        ceiling = max(0, state.my_budget - reserve)
        spend_cap = self._spend_cap(state)
        return min(max(target, state.item.value), ceiling if ceiling > 0 else state.my_budget, spend_cap if spend_cap > 0 else state.my_budget)

    def _follow_up_bid(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        target = self._target_bid(state)
        if opponent_bid >= target:
            target = opponent_bid + MIN_BID_INCREMENT
        else:
            target = max(target, opponent_bid + MIN_BID_INCREMENT if opponent_bid >= my_bid else target)
        spend_cap = self._spend_cap(state)
        if spend_cap <= my_bid:
            return my_bid
        return min(max(my_bid, target), state.my_budget, spend_cap)

    def choose_bid_round_1(self, state: AuctionState) -> int:
        return self._target_bid(state)

    def choose_bid_round_2(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        return self._follow_up_bid(state, my_bid, opponent_bid)

    def choose_bid_round_3(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        return self._follow_up_bid(state, my_bid, opponent_bid)


BOT_CLASS = EarlyDominationBot
