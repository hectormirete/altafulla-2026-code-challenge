from auction_game.interfaces import AuctionBot, AuctionItem, AuctionState, MIN_BID_INCREMENT


def _percentage_of(value: int, percent: int) -> int:
    return value * percent // 100


def _category_count(items: tuple[AuctionItem, ...], category: str) -> int:
    return sum(1 for item in items if item.category == category)


class AggressiveBullyBot(AuctionBot):
    def _ceiling(self, state: AuctionState) -> int:
        return min(_percentage_of(state.item.value, 110), state.my_budget)

    def choose_bid_round_1(self, state: AuctionState) -> int:
        owned_count = _category_count(state.my_items, state.item.category)
        if owned_count >= 3:
            percent = 108
        elif owned_count >= 1:
            percent = 92
        else:
            percent = 80
        return min(_percentage_of(state.item.value, percent), self._ceiling(state))

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


BOT_CLASS = AggressiveBullyBot
