from auction_game.interfaces import AuctionBot, AuctionItem, AuctionState, MIN_BID_INCREMENT


def _percentage_of(value: int, percent: int) -> int:
    return value * percent // 100


def _category_count(items: tuple[AuctionItem, ...], category: str) -> int:
    return sum(1 for item in items if item.category == category)


def _category_total_value(items: tuple[AuctionItem, ...], category: str) -> int:
    return sum(item.value for item in items if item.category == category)


def _category_bonus_rate(item_count: int) -> float:
    raw_rate = 0.06 * max(0, item_count - 1) + 0.02 * max(0, item_count - 3)
    return min(raw_rate, 0.30)


def _category_bonus(total_value: int, item_count: int) -> int:
    return int(total_value * _category_bonus_rate(item_count))


def _marginal_category_value(state: AuctionState) -> int:
    category = state.item.category
    current_count = _category_count(state.my_items, category)
    current_value = _category_total_value(state.my_items, category)
    next_count = current_count + 1
    next_value = current_value + state.item.value
    previous_bonus = _category_bonus(current_value, current_count)
    next_bonus = _category_bonus(next_value, next_count)
    return state.item.value + (next_bonus - previous_bonus)


class CategorySynergistBot(AuctionBot):
    def _ceiling(self, state: AuctionState) -> int:
        current_count = _category_count(state.my_items, state.item.category)
        if current_count == 0:
            return min(_percentage_of(state.item.value, 15), state.my_budget)

        completion_premium = 0
        if current_count in {1, 3}:
            completion_premium = _percentage_of(state.item.value, 5)
        return min(_marginal_category_value(state) + completion_premium, state.my_budget)

    def choose_bid_round_1(self, state: AuctionState) -> int:
        return self._ceiling(state)

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


BOT_CLASS = CategorySynergistBot
