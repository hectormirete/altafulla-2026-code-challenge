from auction_game.interfaces import AuctionBot, AuctionState, MIN_BID_INCREMENT


def _percentage_of(value: int, percent: int) -> int:
    return value * percent // 100


class ValueHunterBot(AuctionBot):
    def _ceiling(self, state: AuctionState) -> int:
        return min(_percentage_of(state.item.value, 75), state.my_budget)

    def choose_bid_round_1(self, state: AuctionState) -> int:
        return min(_percentage_of(state.item.value, 52), self._ceiling(state))

    def _follow_up_bid(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        candidate_bid = opponent_bid + MIN_BID_INCREMENT
        if candidate_bid <= my_bid:
            return my_bid
        if candidate_bid > self._ceiling(state):
            return my_bid
        return min(candidate_bid, state.my_budget)

    def choose_bid_round_2(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        return self._follow_up_bid(state, my_bid, opponent_bid)

    def choose_bid_round_3(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        return self._follow_up_bid(state, my_bid, opponent_bid)


BOT_CLASS = ValueHunterBot
