from __future__ import annotations

from auction_game.interfaces import AuctionBot, AuctionState, MIN_BID_INCREMENT


class LateRaiserBot(AuctionBot):
    def _remaining_rounds(self, state: AuctionState) -> int:
        return max(1, state.total_rounds - state.round_index)

    def _budget_share(self, state: AuctionState) -> int:
        return max(1, state.my_budget // self._remaining_rounds(state))

    def _spend_cap(self, state: AuctionState) -> int:
        rounds_left = self._remaining_rounds(state)
        budget_share = self._budget_share(state)
        reserve = budget_share
        if rounds_left > 4:
            reserve += budget_share // 2
        if rounds_left <= 2:
            reserve -= budget_share // 3
        return max(0, state.my_budget - max(0, reserve))

    def _round_1_bid(self, state: AuctionState) -> int:
        value = state.item.value
        budget_share = self._budget_share(state)

        if value >= 15_000_000:
            target = value * 37 // 100
        elif value >= 13_000_000:
            target = value * 33 // 100
        else:
            target = value * 27 // 100

        target = max(target, 3_500_000)
        target = min(target, max(3_500_000, budget_share // 2))
        return min(target, state.my_budget, self._spend_cap(state))

    def _should_press_round_2(self, state: AuctionState, my_bid: int, opponent_bid: int) -> bool:
        value = state.item.value
        if opponent_bid <= my_bid:
            return False
        if value >= 14_500_000:
            return True
        if opponent_bid >= value * 2 // 5:
            return True
        if state.opponent_budget > state.my_budget and value >= 12_500_000:
            return True
        return opponent_bid >= my_bid + 2_000_000

    def choose_bid_round_1(self, state: AuctionState) -> int:
        return self._round_1_bid(state)

    def choose_bid_round_2(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        if not self._should_press_round_2(state, my_bid, opponent_bid):
            return my_bid

        value = state.item.value
        budget_share = self._budget_share(state)
        target_floor = max(my_bid, opponent_bid + MIN_BID_INCREMENT)

        if value >= 15_000_000:
            ceiling = min(state.my_budget, max(value * 72 // 100, budget_share))
        elif value >= 13_500_000:
            ceiling = min(state.my_budget, max(value * 64 // 100, budget_share))
        else:
            ceiling = min(state.my_budget, max(value * 56 // 100, budget_share // 2))

        if state.opponent_budget > state.my_budget:
            ceiling = min(state.my_budget, ceiling + 1_000_000)

        target = min(ceiling, max(target_floor, value * 52 // 100))
        if target <= my_bid:
            return my_bid
        spend_cap = self._spend_cap(state)
        if spend_cap <= my_bid:
            return my_bid
        return min(target, spend_cap)

    def choose_bid_round_3(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        value = state.item.value
        if opponent_bid <= my_bid:
            return my_bid

        high_value = value >= 15_000_000
        medium_value = value >= 13_500_000
        desperate_matchup = state.opponent_budget >= state.my_budget and opponent_bid >= value * 2 // 5
        serious_pressure = opponent_bid >= value * 45 // 100 or opponent_bid >= my_bid + 1_000_000

        if not (high_value or medium_value or desperate_matchup or serious_pressure):
            return my_bid

        budget_share = self._budget_share(state)
        target_floor = max(my_bid, opponent_bid + MIN_BID_INCREMENT)

        if high_value:
            ceiling = min(state.my_budget, max(value * 92 // 100, budget_share + 1_000_000))
        elif medium_value:
            ceiling = min(state.my_budget, max(value * 82 // 100, budget_share))
        else:
            ceiling = min(state.my_budget, max(value * 70 // 100, budget_share // 2))

        if state.opponent_budget > state.my_budget:
            ceiling = min(state.my_budget, ceiling + 1_000_000)

        target = min(ceiling, max(target_floor, value * 60 // 100))
        if target <= my_bid:
            return my_bid
        spend_cap = self._spend_cap(state)
        if spend_cap <= my_bid:
            return my_bid
        return min(target, spend_cap)


BOT_CLASS = LateRaiserBot
