from auction_game.interfaces import AuctionBot, AuctionState, MIN_BID_INCREMENT


def _percentage_of(value: int, percent: int) -> int:
    return value * percent // 100


def _budget_per_remaining_round(state: AuctionState) -> int:
    rounds_left = max(1, state.total_rounds - state.round_index)
    return state.my_budget // rounds_left


class ZeroIntelligenceConstrainerBot(AuctionBot):
    def _ceiling(self, state: AuctionState) -> int:
        return min(
            _percentage_of(state.item.value, 90),
            _budget_per_remaining_round(state) * 12 // 10,
            state.my_budget,
        )

    def _state_signal(self, state: AuctionState, my_bid: int = 0, opponent_bid: int = 0) -> int:
        item_name_score = sum(ord(char) for char in state.item.name)
        category_score = sum(ord(char) for char in state.item.category)
        return (
            item_name_score
            + category_score * 3
            + state.item.value * 5
            + state.round_index * 7
            + state.total_rounds * 11
            + state.my_budget * 13
            + state.opponent_budget * 17
            + sum(item.value for item in state.my_items) * 19
            + sum(item.value for item in state.opponent_items) * 23
            + sum(state.my_bids) * 29
            + sum(state.opponent_bids) * 31
            + my_bid * 37
            + opponent_bid * 41
        )

    def choose_bid_round_1(self, state: AuctionState) -> int:
        opening_cap = _percentage_of(self._ceiling(state), 70)
        if opening_cap <= 0:
            return 0
        return self._state_signal(state) % (opening_cap + 1)

    def _follow_up_bid(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        ceiling = self._ceiling(state)
        if my_bid >= ceiling:
            return my_bid
        if self._state_signal(state, my_bid, opponent_bid) % 2 == 0:
            return my_bid

        candidate_bid = opponent_bid + MIN_BID_INCREMENT
        if candidate_bid > ceiling:
            return my_bid
        return min(max(my_bid, candidate_bid), state.my_budget)

    def choose_bid_round_2(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        return self._follow_up_bid(state, my_bid, opponent_bid)

    def choose_bid_round_3(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        return self._follow_up_bid(state, my_bid, opponent_bid)


BOT_CLASS = ZeroIntelligenceConstrainerBot
