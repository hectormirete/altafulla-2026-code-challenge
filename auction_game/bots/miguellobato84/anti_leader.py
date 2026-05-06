from __future__ import annotations

from auction_game.interfaces import AuctionBot, AuctionState, MIN_BID_INCREMENT


class AntiLeaderBot(AuctionBot):
    """
    Bid conservatively by default, but raise pressure when the opponent is
    ahead in score, inventory value, or available budget.

    The bot tries to avoid bidding into low-value noise. When the rival is
    carrying momentum, it shifts toward stronger follow-up bids and is willing
    to clear the opponent by at least one increment.
    """

    def _rounds_left(self, state: AuctionState) -> int:
        return max(1, state.total_rounds - state.round_index)

    def _owned_value(self, state: AuctionState, mine: bool) -> int:
        items = state.my_items if mine else state.opponent_items
        return sum(item.value for item in items)

    def _recent_bid_gap(self, state: AuctionState, window: int = 2) -> int:
        my_window = state.my_bids[-window:]
        opponent_window = state.opponent_bids[-window:]
        return sum(opponent_window) - sum(my_window)

    def _pressure_score(self, state: AuctionState) -> float:
        scale = max(1, state.item.value)
        value_gap = max(0, self._owned_value(state, mine=False) - self._owned_value(state, mine=True))
        budget_gap = max(0, state.opponent_budget - state.my_budget)
        momentum_gap = max(0, self._recent_bid_gap(state))

        score = 0.55 * (value_gap / scale)
        score += 0.25 * (budget_gap / scale)
        score += 0.20 * (momentum_gap / scale)
        return score

    def _spend_cap(self, state: AuctionState) -> int:
        rounds_left = self._rounds_left(state)
        budget_pace = state.my_budget // rounds_left
        reserve = budget_pace
        if rounds_left > 4:
            reserve += budget_pace // 2
        if self._pressure_score(state) < 0.35:
            reserve += budget_pace // 3
        return max(0, state.my_budget - reserve)

    def _selective_anchor(self, state: AuctionState) -> int:
        rounds_left = self._rounds_left(state)
        budget_pace = state.my_budget // rounds_left
        value = state.item.value

        if value >= 18_000_000:
            anchor = max(budget_pace, int(value * 0.72))
        elif value >= 14_000_000:
            anchor = max(budget_pace, int(value * 0.60))
        elif value >= 10_000_000:
            anchor = max(budget_pace // 2, int(value * 0.50))
        else:
            anchor = max(budget_pace // 3, int(value * 0.40))

        return min(max(0, anchor), state.my_budget)

    def _target_bid(self, state: AuctionState) -> int:
        base = self._selective_anchor(state)
        pressure = self._pressure_score(state)
        value = state.item.value

        bonus_ratio = 0.08 + min(0.30, pressure * 0.22)
        target = base + int(value * bonus_ratio)

        if pressure >= 0.50:
            target += min(
                value // 10,
                max(0, state.opponent_budget - state.my_budget) // 3,
            )

        if pressure >= 1.00:
            target += value // 12

        if pressure < 0.20:
            cap = int(value * 0.86)
        elif pressure < 0.60:
            cap = int(value * 0.98)
        else:
            cap = int(value * (1.05 + min(0.15, pressure * 0.05)))

        spend_cap = self._spend_cap(state)
        return min(state.my_budget, max(base, min(target, cap), min(cap, spend_cap)))

    def _follow_up_bid(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        pressure = self._pressure_score(state)
        target = self._target_bid(state)

        if opponent_bid <= my_bid:
            if pressure >= 0.65 and target > my_bid:
                return min(target, state.my_budget)
            return my_bid

        if pressure < 0.35:
            if target <= opponent_bid:
                return my_bid
            chase = min(target, opponent_bid + MIN_BID_INCREMENT)
        else:
            chase = max(opponent_bid + MIN_BID_INCREMENT, target)
            if pressure >= 0.85:
                chase += MIN_BID_INCREMENT

        return min(state.my_budget, max(my_bid, chase))

    def choose_bid_round_1(self, state: AuctionState) -> int:
        return self._target_bid(state)

    def choose_bid_round_2(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        return self._follow_up_bid(state, my_bid, opponent_bid)

    def choose_bid_round_3(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        return self._follow_up_bid(state, my_bid, opponent_bid)


BOT_CLASS = AntiLeaderBot
