from auction_game.interfaces import AuctionBot, AuctionState


class GreedyValueBot(AuctionBot):
    def choose_bid(self, state: AuctionState) -> int:
        rounds_left = state.total_rounds - state.round_index
        target_bid = max(state.item.value, state.my_budget // max(1, rounds_left))
        return min(target_bid, state.my_budget)


BOT_CLASS = GreedyValueBot
