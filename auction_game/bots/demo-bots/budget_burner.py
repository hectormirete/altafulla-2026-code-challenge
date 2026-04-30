from auction_game.interfaces import AuctionBot, AuctionState, MIN_BID_INCREMENT


class BudgetBurnerBot(AuctionBot):
    def _pressure_anchor(self, state: AuctionState) -> int:
        rounds_left = state.total_rounds - state.round_index
        return max(state.item.value, state.my_budget // max(1, rounds_left))

    def choose_bid_round_1(self, state: AuctionState) -> int:
        if state.round_index < 5:
            return min(max(self._pressure_anchor(state), int(state.item.value * 1.35)), state.my_budget)
        return min(max(state.item.value, state.my_budget // max(1, state.total_rounds - state.round_index)), state.my_budget)

    def choose_bid_round_2(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        if state.round_index < 5:
            if opponent_bid >= my_bid:
                return min(
                    max(my_bid, opponent_bid + max(MIN_BID_INCREMENT, int(state.item.value * 0.08))),
                    state.my_budget,
                )
            return my_bid

        target = max(state.item.value, state.my_budget // max(1, state.total_rounds - state.round_index))
        if opponent_bid <= state.item.value and opponent_bid >= my_bid:
            target = max(target, opponent_bid + MIN_BID_INCREMENT)
        return min(max(my_bid, target), state.my_budget)

    def choose_bid_round_3(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        if state.round_index < 5:
            if opponent_bid > my_bid:
                return min(
                    max(my_bid, opponent_bid + max(MIN_BID_INCREMENT, int(state.item.value * 0.12))),
                    state.my_budget,
                )
            return my_bid

        if opponent_bid > my_bid and opponent_bid <= state.item.value:
            return min(opponent_bid + MIN_BID_INCREMENT, state.my_budget)
        return my_bid


BOT_CLASS = BudgetBurnerBot
