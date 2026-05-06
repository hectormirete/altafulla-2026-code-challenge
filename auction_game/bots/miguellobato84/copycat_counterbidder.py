from __future__ import annotations

from auction_game.interfaces import AuctionBot, AuctionState, MIN_BID_INCREMENT


class CopycatCounterbidderBot(AuctionBot):
    """Mirror strong opponent bidding patterns and only punish real overbids when justified."""

    def _rounds_left(self, state: AuctionState) -> int:
        return max(1, state.total_rounds - state.round_index)

    def _progress(self, state: AuctionState) -> float:
        if state.total_rounds <= 1:
            return 1.0
        return state.round_index / max(1, state.total_rounds - 1)

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

    def _recent_opponent_bids(self, state: AuctionState, window: int = 3) -> tuple[int, ...]:
        return state.opponent_bids[-window:]

    def _recent_average(self, bids: tuple[int, ...]) -> int:
        if not bids:
            return 0
        return sum(bids) // len(bids)

    def _recent_spread(self, bids: tuple[int, ...]) -> int:
        if not bids:
            return 0
        return max(bids) - min(bids)

    def _recent_trend(self, bids: tuple[int, ...]) -> int:
        if len(bids) < 2:
            return 0
        return bids[-1] - bids[0]

    def _strong_opponent_pattern(self, state: AuctionState) -> bool:
        bids = self._recent_opponent_bids(state)
        if len(bids) < 2:
            return False

        average = self._recent_average(bids)
        spread = self._recent_spread(bids)
        trend = self._recent_trend(bids)

        if average < 7_500_000:
            return False
        if spread > 2_500_000:
            return False
        return trend >= -1_000_000

    def _value_supports_aggression(self, state: AuctionState) -> bool:
        value = state.item.value
        rounds_left = self._rounds_left(state)
        if value >= 16_000_000:
            return True
        if value >= 13_500_000:
            return True
        if rounds_left <= 3 and value >= 11_500_000:
            return True
        return False

    def _value_supports_countering(self, state: AuctionState) -> bool:
        value = state.item.value
        rounds_left = self._rounds_left(state)
        if value >= 15_000_000:
            return True
        if rounds_left <= 2 and value >= 12_000_000:
            return True
        if rounds_left <= 4 and value >= 13_500_000:
            return True
        return False

    def _base_bid(self, state: AuctionState) -> int:
        value = state.item.value
        rounds_left = self._rounds_left(state)
        progress = self._progress(state)
        budget_share = self._budget_share(state)

        if value >= 16_000_000:
            fraction = 0.74
        elif value >= 13_500_000:
            fraction = 0.64
        elif value >= 11_000_000:
            fraction = 0.54
        else:
            fraction = 0.42

        target = int(value * fraction)
        target = min(target, int(budget_share * (0.62 + 0.10 * progress)))

        if rounds_left <= 3:
            target = max(target, int(value * 0.60))
        if rounds_left <= 2:
            target = max(target, int(value * 0.70))

        return min(max(0, target), state.my_budget)

    def _mirror_target(self, state: AuctionState) -> int:
        base = self._base_bid(state)
        if not self._value_supports_aggression(state):
            return base

        if not self._strong_opponent_pattern(state):
            return base

        bids = self._recent_opponent_bids(state)
        if not bids:
            return base

        average = self._recent_average(bids)
        last_bid = bids[-1]
        trend = self._recent_trend(bids)

        mirrored = max(base, average)
        mirrored = max(mirrored, last_bid)
        if trend > 0:
            mirrored += min(MIN_BID_INCREMENT, trend // 2)

        return min(state.my_budget, mirrored)

    def _target_bid(self, state: AuctionState, my_bid: int | None = None, opponent_bid: int | None = None) -> int:
        target = self._base_bid(state)
        mirror_target = self._mirror_target(state)
        if mirror_target > target:
            target = mirror_target

        if opponent_bid is not None and opponent_bid > state.item.value and self._value_supports_countering(state):
            target = max(target, opponent_bid + MIN_BID_INCREMENT)
            target = max(target, int(state.item.value * 0.78))
        elif opponent_bid is not None and self._strong_opponent_pattern(state) and self._value_supports_aggression(state):
            recent_bids = self._recent_opponent_bids(state)
            if recent_bids:
                target = max(target, self._recent_average(recent_bids))
                if recent_bids[-1] >= recent_bids[0]:
                    target = max(target, recent_bids[-1] + MIN_BID_INCREMENT)

        if my_bid is not None:
            target = max(target, my_bid)

        return min(state.my_budget, target, self._spend_cap(state))

    def choose_bid_round_1(self, state: AuctionState) -> int:
        return self._target_bid(state)

    def choose_bid_round_2(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        target = self._target_bid(state, my_bid=my_bid, opponent_bid=opponent_bid)
        if target <= my_bid:
            return my_bid
        return target

    def choose_bid_round_3(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        target = self._target_bid(state, my_bid=my_bid, opponent_bid=opponent_bid)
        if target <= my_bid:
            return my_bid
        return target


BOT_CLASS = CopycatCounterbidderBot
