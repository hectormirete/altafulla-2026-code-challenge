import random

from auction_game.interfaces import AuctionBot, AuctionItem, AuctionState, MIN_BID_INCREMENT


def _percentage_of(value: int, percent: int) -> int:
    return value * percent // 100


def _budget_per_remaining_round(state: AuctionState) -> int:
    rounds_left = max(1, state.total_rounds - state.round_index)
    return state.my_budget // rounds_left


def _category_count(items: tuple[AuctionItem, ...], category: str) -> int:
    return sum(1 for item in items if item.category == category)


class ZeroIntelligenceConstrainerRngBot(AuctionBot):
    def __init__(self) -> None:
        self._rng = random.Random()

    def _ceiling(self, state: AuctionState) -> int:
        return min(
            _percentage_of(state.item.value, 90),
            _budget_per_remaining_round(state) * 12 // 10,
            state.my_budget,
        )

    def _owned_count(self, state: AuctionState) -> int:
        return _category_count(state.my_items, state.item.category)

    def choose_bid_round_1(self, state: AuctionState) -> int:
        ceiling = self._ceiling(state)
        owned_count = self._owned_count(state)
        if owned_count >= 1:
            low = _percentage_of(ceiling, 20)
            high = _percentage_of(ceiling, 85)
            return self._rng.randint(low, high)
        high = _percentage_of(ceiling, 70)
        return self._rng.randint(0, high)

    def _follow_up_bid(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        ceiling = self._ceiling(state)
        if my_bid >= ceiling:
            return my_bid
        owned_count = self._owned_count(state)
        should_hold = (
            self._rng.randint(1, 3) == 1
            if owned_count >= 1
            else self._rng.choice((True, False))
        )
        if should_hold:
            return my_bid
        candidate_bid = opponent_bid + MIN_BID_INCREMENT
        if candidate_bid > ceiling:
            return my_bid
        return min(max(my_bid, candidate_bid), state.my_budget)

    def choose_bid_round_2(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        return self._follow_up_bid(state, my_bid, opponent_bid)

    def choose_bid_round_3(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        return self._follow_up_bid(state, my_bid, opponent_bid)


BOT_CLASS = ZeroIntelligenceConstrainerRngBot
