from auction_game.interfaces import AuctionBot, AuctionState


class SteadyBidderBot(AuctionBot):
    def choose_bid(self, state: AuctionState) -> int:
        rounds_left = state.total_rounds - state.round_index
        anchor_bid = state.my_budget // max(1, rounds_left)
        if state.item.value >= 18_000_000:
            return min(max(anchor_bid, 16_000_000), state.my_budget)
        if state.item.value >= 14_000_000:
            return min(max(anchor_bid, 12_000_000), state.my_budget)
        return min(max(anchor_bid // 2, 6_000_000), state.my_budget)


BOT_CLASS = SteadyBidderBot
