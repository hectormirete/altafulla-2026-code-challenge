from auction_game.interfaces import AuctionBot, AuctionState, MIN_BID_INCREMENT


class ValueSniperBot(AuctionBot):
    def _spend_cap(self, state: AuctionState) -> int:
        rounds_left = max(1, state.total_rounds - state.round_index)
        budget_share = max(1, state.my_budget // rounds_left)
        reserve = budget_share if rounds_left > 2 else max(0, budget_share // 2)
        if state.item.value < 12_000_000:
            reserve += budget_share // 2
        return max(0, state.my_budget - reserve)

    def _value_fraction(self, state: AuctionState) -> float:
        if state.item.value >= 18_000_000:
            return 0.72
        if state.item.value >= 14_000_000:
            return 0.64
        if state.item.value >= 10_000_000:
            return 0.58
        return 0.50

    def _base_bid(self, state: AuctionState) -> int:
        rounds_left = max(1, state.total_rounds - state.round_index)
        budget_share = state.my_budget // rounds_left
        value_bid = int(state.item.value * self._value_fraction(state))
        conservative_bid = min(value_bid, budget_share, state.my_budget, self._spend_cap(state))
        return max(0, conservative_bid)

    def _sniping_cap(self, state: AuctionState, round_multiplier: float) -> int:
        base_bid = self._base_bid(state)
        value_cap = int(state.item.value * round_multiplier)
        return max(base_bid, min(value_cap, state.my_budget))

    def choose_bid_round_1(self, state: AuctionState) -> int:
        return self._base_bid(state)

    def choose_bid_round_2(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        if opponent_bid <= my_bid:
            return my_bid

        cap = self._sniping_cap(state, 0.88)
        cap = min(cap, self._spend_cap(state))
        if opponent_bid >= cap:
            return my_bid

        target = min(opponent_bid + MIN_BID_INCREMENT, cap, state.my_budget)
        return max(my_bid, target)

    def choose_bid_round_3(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        if opponent_bid <= my_bid:
            return my_bid

        cap = self._sniping_cap(state, 0.92)
        cap = min(cap, self._spend_cap(state))
        if opponent_bid >= cap:
            return my_bid

        target = min(opponent_bid + MIN_BID_INCREMENT, cap, state.my_budget)
        return max(my_bid, target)


BOT_CLASS = ValueSniperBot
