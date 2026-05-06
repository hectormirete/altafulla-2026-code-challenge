from typing import List
from auction_game.interfaces import AuctionBot, AuctionState, MIN_BID_INCREMENT
from auction_game.engine import (
    MIN_ITEM_VALUE,
    MAX_ITEM_VALUE,
    DEFAULT_ITEM_COUNT,
    _score_items,
)

EXPECTED_ITEM_VALUE = (MIN_ITEM_VALUE + MAX_ITEM_VALUE) / 2  # 12_000_000
EXPECTED_TOTAL_VALUE = EXPECTED_ITEM_VALUE * DEFAULT_ITEM_COUNT  # 240_000_000


class NotYourAverageRobot(AuctionBot):
    # sum(won item values) + category bonuses + money left

    def __init__(self) -> None:
        pass

    def _no_buy_value(self, state: AuctionState):
        no_buy_score, _ = _score_items(state.my_items, state.my_budget)
        return no_buy_score

    def _buy_value(self, state: AuctionState, bid: int) -> float:
        buy_score, _ = _score_items(
            list(state.my_items) + [state.item], max(state.my_budget - bid, 0)
        )
        print(buy_score)
        return buy_score

    def _budget_per_item(self, budget: int, round_index: int, rounds: int) -> float:
        items_left = rounds - round_index + 1
        return budget / items_left

    def _possible_bids(self, state: AuctionState, min_bid: int = 1) -> List[int]:
        bid_ratios = [b / 10 for b in range(1, 14)]
        no_bid_value = self._no_buy_value(state)

        bids = []

        for br in bid_ratios:
            candidate_bid = br * state.item.value
            if candidate_bid <= min_bid:
                continue
            if candidate_bid <= state.my_budget:
                break
            bid_value = self._buy_value(state, candidate_bid)
            if bid_value > no_bid_value:
                bids.append({"candidate_bid": candidate_bid, "bid_score": bid_value})

        if (
            len(bids) <= 0
            and state.my_budget > 0
            and (budget_value := self._buy_value(state, state.my_budget)) > no_bid_value
        ):
            bids.append({"candidate_bid": state.my_budget, "bid_score": budget_value})
        return bids

    def choose_bid_round_1(self, state: AuctionState) -> int:
        return 5

    def choose_bid_round_2(
        self, state: AuctionState, my_bid: int, opponent_bid: int
    ) -> int:
        if my_bid >= opponent_bid:
            return my_bid
        else:
            possible_bids = self._possible_bids(
                state, max(my_bid + MIN_BID_INCREMENT, opponent_bid)
            )
            if len(possible_bids) > 0:
                return possible_bids[0]
            else:
                return my_bid

    def choose_bid_round_3(
        self, state: AuctionState, my_bid: int, opponent_bid: int
    ) -> int:
        possible_bids = self._possible_bids(
            state, max(my_bid + MIN_BID_INCREMENT, opponent_bid)
        )

        if len(possible_bids) == 0:
            return my_bid

        if state.opponent_budget < possible_bids[-1]:
            for possible_bid in possible_bids:
                if state.opponent_budget < possible_bid:
                    return possible_bid

        budget_per_item = self._budget_per_item(
            state.my_budget, state.round_index, state.total_rounds
        )

        norm_budget = (
            min(budget_per_item, EXPECTED_ITEM_VALUE * 2) / EXPECTED_ITEM_VALUE * 2
        )

        possible_idx = int(round(norm_budget))

        possible_bids[possible_idx]


BOT_CLASS = NotYourAverageRobot
