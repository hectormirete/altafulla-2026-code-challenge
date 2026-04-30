from auction_game.interfaces import AuctionBot, AuctionState, MIN_BID_INCREMENT


class CopycatBidderBot(AuctionBot):
    def choose_bid_round_1(self, state: AuctionState) -> int:
        if not state.opponent_bids:
            return min(state.item.value, state.my_budget)
        return min(state.opponent_bids[-1], state.my_budget)

    def choose_bid_round_2(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        if opponent_bid > my_bid:
            return min(opponent_bid + MIN_BID_INCREMENT, state.my_budget)
        return my_bid

    def choose_bid_round_3(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        if opponent_bid > my_bid:
            return min(opponent_bid + MIN_BID_INCREMENT, state.my_budget)
        return my_bid


BOT_CLASS = CopycatBidderBot
