from auction_game.interfaces import AuctionBot, AuctionState, MIN_BID_INCREMENT


class SteadyBidderBot(AuctionBot):
    def _anchor_bid(self, state: AuctionState) -> int:
        rounds_left = state.total_rounds - state.round_index
        anchor_bid = state.my_budget // max(1, rounds_left)
        if state.item.value >= 18_000_000:
            return min(max(anchor_bid, 16_000_000), state.my_budget)
        if state.item.value >= 14_000_000:
            return min(max(anchor_bid, 12_000_000), state.my_budget)
        return min(max(anchor_bid // 2, 6_000_000), state.my_budget)

    def choose_bid_round_1(self, state: AuctionState) -> int:
        return self._anchor_bid(state)

    def choose_bid_round_2(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        if opponent_bid <= my_bid:
            return my_bid
        ceiling = self._anchor_bid(state) + int(state.item.value * 0.08)
        return min(max(my_bid, min(opponent_bid + MIN_BID_INCREMENT, ceiling)), state.my_budget)

    def choose_bid_round_3(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        if opponent_bid <= my_bid:
            return my_bid
        ceiling = self._anchor_bid(state) + int(state.item.value * 0.12)
        return min(max(my_bid, min(opponent_bid + MIN_BID_INCREMENT, ceiling)), state.my_budget)


BOT_CLASS = SteadyBidderBot
