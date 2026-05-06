from auction_game.interfaces import AuctionBot, AuctionState, MIN_BID_INCREMENT


def _percentage_of(value: int, percent: int) -> int:
    return value * percent // 100


class TitForTatBot(AuctionBot):
    def choose_bid_round_1(self, state: AuctionState) -> int:
        return min(_percentage_of(state.item.value, 20), state.my_budget)

    def _peaceful_response(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        candidate_bid = opponent_bid + MIN_BID_INCREMENT
        if candidate_bid <= _percentage_of(state.item.value, 35) and candidate_bid <= state.my_budget:
            return max(my_bid, candidate_bid)
        return my_bid

    def _retaliation(self, state: AuctionState, my_bid: int) -> int:
        return max(my_bid, min(_percentage_of(state.item.value, 95), state.my_budget))

    def choose_bid_round_2(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        if opponent_bid <= _percentage_of(state.item.value, 20):
            return self._peaceful_response(state, my_bid, opponent_bid)
        return self._retaliation(state, my_bid)

    def choose_bid_round_3(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        if opponent_bid <= _percentage_of(state.item.value, 20):
            return self._peaceful_response(state, my_bid, opponent_bid)
        return self._retaliation(state, my_bid)


BOT_CLASS = TitForTatBot
