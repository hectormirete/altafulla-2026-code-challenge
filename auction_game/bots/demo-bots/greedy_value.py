from auction_game.interfaces import AuctionBot, AuctionState, MIN_BID_INCREMENT


class GreedyValueBot(AuctionBot):
    def _value_anchor(self, state: AuctionState) -> int:
        rounds_left = state.total_rounds - state.round_index
        return min(max(state.item.value, state.my_budget // max(1, rounds_left)), state.my_budget)

    def choose_bid_round_1(self, state: AuctionState) -> int:
        return self._value_anchor(state)

    def choose_bid_round_2(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        target = self._value_anchor(state)
        if opponent_bid <= state.item.value and opponent_bid >= my_bid:
            target = max(target, opponent_bid + MIN_BID_INCREMENT)
        return min(max(my_bid, target), state.my_budget)

    def choose_bid_round_3(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        if opponent_bid > my_bid and opponent_bid <= state.item.value:
            return min(opponent_bid + MIN_BID_INCREMENT, state.my_budget)
        return my_bid


BOT_CLASS = GreedyValueBot
