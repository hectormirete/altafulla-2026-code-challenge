from __future__ import annotations

import random

from auction_game.interfaces import AuctionBot, AuctionState, MIN_BID_INCREMENT


class NoisyOpportunistBot(AuctionBot):
    """
    Opportunistic bidder with small controlled randomness.

    The bot starts from a value-aware baseline, then jitters its targets a bit
    so its behavior is less predictable while still staying within budget and
    respecting monotonic follow-up bids.
    """

    def _rng(self, state: AuctionState) -> random.Random:
        seed = (
            (state.round_index + 1) * 1_000_003
            + state.item.value * 97
            + state.my_budget * 17
            + len(state.my_items) * 53
            + len(state.opponent_items) * 31
        )
        return random.Random(seed)

    def _remaining_rounds(self, state: AuctionState) -> int:
        return max(1, state.total_rounds - state.round_index)

    def _spend_cap(self, state: AuctionState) -> int:
        rounds_left = self._remaining_rounds(state)
        budget_pace = state.my_budget // rounds_left
        reserve = budget_pace
        if rounds_left > 4:
            reserve += budget_pace // 2
        if rounds_left <= 2:
            reserve -= budget_pace // 3
        return max(0, state.my_budget - max(0, reserve))

    def _baseline(self, state: AuctionState) -> int:
        rounds_left = self._remaining_rounds(state)
        budget_pace = state.my_budget // rounds_left
        if state.item.value >= 15_000_000:
            target = int(state.item.value * 0.78)
        elif state.item.value >= 12_000_000:
            target = int(state.item.value * 0.66)
        else:
            target = int(state.item.value * 0.54)
        return min(max(target, budget_pace // 2), state.my_budget, self._spend_cap(state))

    def _noisy_target(self, state: AuctionState, base: int, spread: int) -> int:
        rng = self._rng(state)
        wobble = rng.randint(-spread, spread)
        target = base + wobble
        if rng.random() < 0.20 and state.item.value >= 13_000_000:
            target += rng.randint(0, min(spread, MIN_BID_INCREMENT * 2))
        return min(max(target, 0), state.my_budget)

    def _round_1_bid(self, state: AuctionState) -> int:
        base = self._baseline(state)
        spread = max(250_000, state.item.value // 16)
        return self._noisy_target(state, base, spread)

    def _follow_up_bid(self, state: AuctionState, my_bid: int, opponent_bid: int, round_index: int) -> int:
        if opponent_bid <= my_bid:
            return my_bid

        base = self._baseline(state)
        if round_index == 2:
            cap_ratio = 0.86
            spread = max(350_000, state.item.value // 18)
        else:
            cap_ratio = 0.92
            spread = max(500_000, state.item.value // 14)

        cap = min(state.my_budget, int(state.item.value * cap_ratio), self._spend_cap(state))
        target = self._noisy_target(state, max(base, opponent_bid + MIN_BID_INCREMENT), spread)
        target = min(target, cap)
        if target <= my_bid:
            return my_bid
        return target

    def choose_bid_round_1(self, state: AuctionState) -> int:
        return self._round_1_bid(state)

    def choose_bid_round_2(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        return self._follow_up_bid(state, my_bid, opponent_bid, round_index=2)

    def choose_bid_round_3(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        return self._follow_up_bid(state, my_bid, opponent_bid, round_index=3)


BOT_CLASS = NoisyOpportunistBot
