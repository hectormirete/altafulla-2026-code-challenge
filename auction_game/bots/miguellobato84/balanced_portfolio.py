from __future__ import annotations

from auction_game.interfaces import AuctionBot, AuctionState, MIN_BID_INCREMENT


class BalancedPortfolioBot(AuctionBot):
    """Bid along a smooth spend curve and avoid sharp jumps between rounds."""

    def _rounds_left(self, state: AuctionState) -> int:
        return max(1, state.total_rounds - state.round_index)

    def _progress(self, state: AuctionState) -> float:
        if state.total_rounds <= 1:
            return 1.0
        return state.round_index / (state.total_rounds - 1)

    def _smoothstep(self, value: float) -> float:
        value = max(0.0, min(1.0, value))
        return value * value * (3.0 - 2.0 * value)

    def _recent_average(self, bids: tuple[int, ...], window: int = 3) -> int:
        if not bids:
            return 0
        slice_start = max(0, len(bids) - window)
        recent = bids[slice_start:]
        return sum(recent) // len(recent)

    def _spend_cap(self, state: AuctionState) -> int:
        rounds_left = self._rounds_left(state)
        pace = state.my_budget // rounds_left
        reserve = pace if rounds_left > 3 else max(0, pace // 2)
        if self._progress(state) < 0.5:
            reserve += pace // 2
        return max(0, state.my_budget - reserve)

    def _item_quality(self, state: AuctionState) -> float:
        value = state.item.value
        if value >= 16_000_000:
            return 1.0
        if value >= 14_000_000:
            return 0.75
        if value >= 12_000_000:
            return 0.45
        return 0.15

    def _target_bid(self, state: AuctionState) -> int:
        rounds_left = self._rounds_left(state)
        progress = self._progress(state)
        quality = self._item_quality(state)
        pace = state.my_budget // rounds_left

        # Keep the budget spread across the tournament: spend a little less than
        # pace early, then let the curve rise steadily as rounds disappear.
        curve = 0.36 + 0.34 * self._smoothstep(progress)
        if rounds_left <= 4:
            curve += 0.04 * (5 - rounds_left)
        if rounds_left <= 2:
            curve += 0.06

        pace_target = int(pace * curve)
        value_target = int(
            state.item.value * (0.22 + 0.18 * progress + 0.10 * quality)
        )
        blended = max(pace_target, value_target)

        # Smooth the path using recent own bids so the curve does not oscillate.
        recent_average = self._recent_average(state.my_bids)
        if recent_average > 0:
            blended = int(blended * 0.7 + recent_average * 0.3)

        # Keep some headroom for the remaining rounds while still allowing
        # stronger late-game bids on valuable items.
        reserve = int(pace * (0.85 + 0.25 * (1.0 - progress)))
        ceiling = max(0, state.my_budget - reserve)
        item_cap = int(
            state.item.value * (0.42 + 0.28 * progress + 0.10 * quality)
        )
        target = min(blended, item_cap, state.my_budget)
        if ceiling > 0:
            target = min(target, max(ceiling, pace_target))
        target = min(target, self._spend_cap(state))

        if state.opponent_budget > state.my_budget:
            target = min(state.my_budget, target + min(1_000_000, pace // 3))

        return max(0, target)

    def _follow_up_bid(self, state: AuctionState, my_bid: int, opponent_bid: int, step_fraction: float) -> int:
        if opponent_bid <= my_bid:
            return my_bid

        target = self._target_bid(state)
        required = opponent_bid + MIN_BID_INCREMENT
        if required > target:
            return my_bid

        max_step = max(MIN_BID_INCREMENT, int(state.item.value * step_fraction))
        step_limited = min(target, my_bid + max_step, state.my_budget)
        if required > step_limited:
            return my_bid
        spend_cap = self._spend_cap(state)
        if spend_cap <= my_bid:
            return my_bid
        return min(max(my_bid, required), spend_cap)

    def choose_bid_round_1(self, state: AuctionState) -> int:
        return self._target_bid(state)

    def choose_bid_round_2(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        progress = self._progress(state)
        return self._follow_up_bid(state, my_bid, opponent_bid, 0.06 + 0.03 * progress)

    def choose_bid_round_3(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        progress = self._progress(state)
        return self._follow_up_bid(state, my_bid, opponent_bid, 0.09 + 0.04 * progress)


BOT_CLASS = BalancedPortfolioBot
