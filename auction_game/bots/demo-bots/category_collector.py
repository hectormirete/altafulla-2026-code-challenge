from auction_game.interfaces import AuctionBot, AuctionState


class CategoryCollectorBot(AuctionBot):
    def choose_bid(self, state: AuctionState) -> int:
        same_category = sum(1 for entry in state.my_items if entry.category == state.item.category)
        rounds_left = state.total_rounds - state.round_index
        base_bid = max(state.item.value, state.my_budget // max(1, rounds_left))
        if same_category >= 1:
            base_bid += int(state.item.value * 0.15)
        elif state.item.value >= 16_000_000:
            base_bid += int(state.item.value * 0.08)
        return min(base_bid, state.my_budget)


BOT_CLASS = CategoryCollectorBot
