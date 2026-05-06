from typing import List, Dict
from auction_game.interfaces import AuctionBot, AuctionState, MIN_BID_INCREMENT
from auction_game.engine import (
    MIN_ITEM_VALUE,
    MAX_ITEM_VALUE,
    _score_items,
)

EXPECTED_ITEM_VALUE = (MIN_ITEM_VALUE + MAX_ITEM_VALUE) / 2  # 12_000_000
OPPONENT_THRESHOLD = 1.0 * EXPECTED_ITEM_VALUE  # Opponent's budget per item threshold
OPPONENT_THRESHOLD_DECAY = (
    0.2  # Decay we apply to our bid index if opponent's threshold is smaller
)
MAX_NORM_BUDGET = EXPECTED_ITEM_VALUE * 2


class PurelyHumanBot(AuctionBot):
    # sum(won item values) + category bonuses + money left

    def __init__(self) -> None:
        pass

    def _no_buy_value(self, state: AuctionState):
        """Calculates the score of not buying any item"""
        no_buy_score, _ = _score_items(state.my_items, state.my_budget)
        return no_buy_score

    def _buy_value(self, state: AuctionState, bid: int) -> float:
        """Calculates the score of buying the current item with the provided bid"""
        buy_score, _ = _score_items(
            list(state.my_items) + [state.item], max(state.my_budget - bid, 0)
        )
        return buy_score

    def _budget_per_item(self, budget: int, round_index: int, rounds: int) -> float:
        """Calculates a budget per item left

        If this is higher than expected, it means that we are under spending and if lower,
        over spending
        """
        items_left = rounds - round_index + 1
        return budget / items_left

    def _possible_bids(
        self, state: AuctionState, min_bid: int = 1
    ) -> List[Dict[str, int]]:
        """Calculates a list of possible bids. These bids are calculated using score values. Negative
        values are discarded as it makes it more interesting to not bid.
        """
        bid_ratios = [b / 100 for b in range(1, 100)]

        no_bid_value = self._no_buy_value(state)

        bids = []

        for br in bid_ratios:
            candidate_bid = br * state.item.value
            if candidate_bid <= min_bid:
                continue
            if candidate_bid > state.my_budget:
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
        """I don't care about round 1 really"""
        return 5

    def choose_bid_round_2(
        self, state: AuctionState, my_bid: int, opponent_bid: int
    ) -> int:
        """Also not about round 2, as likely we can't learn much from it"""
        if my_bid >= opponent_bid:
            return my_bid
        else:
            possible_bids = self._possible_bids(
                state, max(my_bid + MIN_BID_INCREMENT, opponent_bid)
            )
            if len(possible_bids) > 0:
                return int(possible_bids[0]["candidate_bid"])
            else:
                return my_bid

    def choose_bid_round_3(
        self, state: AuctionState, my_bid: int, opponent_bid: int
    ) -> int:
        """For this round, we have to be smart!

        The general idea is simple:

        - Calculate all possible bids, ordered from smallest to greatest bid.
        - If we have no possible bid, we just return the previous bid.
        - If our opponents budget is lower than some of our candidate bids, return the smallest bid that fulfills it.
        - Otherwise, pick a good bid that maximizes value we get out of it (low bid, high return)
            - Picking this is a bit tricky: if we have a lot of budget per item, means we are underspending it
                - We then increase our bidding as buying things helps us achieving our objectives
                - If the opponent budget per item is very low, it means that they have spent a lot of money already
                  and we consider that we can lower our bids so to also extract the biggest value

        """
        possible_bids = self._possible_bids(
            state, max(my_bid + MIN_BID_INCREMENT, opponent_bid)
        )

        if len(possible_bids) == 0:
            return my_bid

        if state.opponent_budget < possible_bids[-1]["candidate_bid"]:
            for possible_bid in possible_bids:
                if state.opponent_budget < possible_bid["candidate_bid"]:
                    return int(possible_bid["candidate_bid"])

        my_budget_per_item = self._budget_per_item(
            state.my_budget, state.round_index, state.total_rounds
        )

        opponent_budget_per_item = self._budget_per_item(
            state.opponent_budget, state.round_index, state.total_rounds
        )

        norm_budget = min(my_budget_per_item, MAX_NORM_BUDGET) / (MAX_NORM_BUDGET)

        if opponent_budget_per_item < OPPONENT_THRESHOLD:
            norm_budget *= OPPONENT_THRESHOLD_DECAY

        possible_idx = min(
            int(round(norm_budget * len(possible_bids))), len(possible_bids) - 1
        )

        return int(possible_bids[possible_idx]["candidate_bid"])

        # return int(possible_bids[-1]["candidate_bid"])

        # return int(possible_bids[len(possible_bids) // 2]["candidate_bid"])


BOT_CLASS = PurelyHumanBot
