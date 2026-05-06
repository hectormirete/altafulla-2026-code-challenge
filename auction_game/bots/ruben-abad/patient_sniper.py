from auction_game.interfaces import AuctionBot, AuctionState, MIN_BID_INCREMENT


def _percentage_of(value: int, percent: int) -> int:
    return value * percent // 100


class PatientSniperBot(AuctionBot):
    def choose_bid_round_1(self, state: AuctionState) -> int:
        return 0

    def _snipe(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        if opponent_bid > _percentage_of(state.item.value, 50):
            return my_bid
        candidate_bid = opponent_bid + MIN_BID_INCREMENT
        if candidate_bid > _percentage_of(state.item.value, 65):
            return my_bid
        return min(max(my_bid, candidate_bid), state.my_budget)

    def choose_bid_round_2(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        return self._snipe(state, my_bid, opponent_bid)

    def choose_bid_round_3(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        return self._snipe(state, my_bid, opponent_bid)


BOT_CLASS = PatientSniperBot
