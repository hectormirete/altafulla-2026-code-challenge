from auction_game.engine import DEFAULT_BUDGET, DEFAULT_ITEM_COUNT
from auction_game.interfaces import AuctionBot, AuctionState, MIN_BID_INCREMENT


BASELINE_BUDGET_PER_ITEM = DEFAULT_BUDGET // DEFAULT_ITEM_COUNT


def _percentage_of(value: int, percent: int) -> int:
    return value * percent // 100


def _reserve_after_current_item(state: AuctionState) -> int:
    rounds_after_current = max(0, state.total_rounds - state.round_index - 1)
    return rounds_after_current * BASELINE_BUDGET_PER_ITEM


class BudgetAwareBidderBot(AuctionBot):
    def _dynamic_percent(self, state: AuctionState) -> int:
        surplus = state.my_budget - _reserve_after_current_item(state)
        if surplus <= 0:
            return 35
        if surplus <= BASELINE_BUDGET_PER_ITEM:
            return 45
        if surplus <= BASELINE_BUDGET_PER_ITEM * 3:
            return 60
        if surplus <= BASELINE_BUDGET_PER_ITEM * 6:
            return 80
        return 92

    def _ceiling(self, state: AuctionState) -> int:
        return min(_percentage_of(state.item.value, self._dynamic_percent(state)), state.my_budget)

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


BOT_CLASS = BudgetAwareBidderBot
