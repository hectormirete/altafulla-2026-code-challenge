from __future__ import annotations

from auction_game import AuctionState, MIN_BID_INCREMENT
from auction_game.bots.jaume.codex_optimal_4 import CodexOptimal4Bot


class CodexOptimal8Bot(CodexOptimal4Bot):
    """CodexOptimal4 valuation with an assertive final tie-breaker."""

    def __init__(self) -> None:
        super().__init__()
        self._tie_increment = 2
        self._last_equal_round_2: int | None = None
        self._observed_bid_count = 0

    def choose_bid_round_1(self, state: AuctionState) -> int:
        self._observe_completed_rounds(state)
        return super().choose_bid_round_1(state)

    def choose_bid_round_2(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        opening_gap = abs(opponent_bid - my_bid)
        if state.round_index == 0 and 0 < opening_gap < MIN_BID_INCREMENT:
            self._tie_increment = 3
        return super().choose_bid_round_2(state, my_bid, opponent_bid)

    def _raise_if_worthwhile(
        self,
        state: AuctionState,
        my_bid: int,
        opponent_bid: int,
        *,
        final_round: bool,
    ) -> int:
        ceiling = self._ceiling(state, opponent_bid=opponent_bid, final_round=final_round)

        if final_round and opponent_bid == my_bid:
            self._last_equal_round_2 = my_bid
            for increment in (self._tie_increment, 2, 1):
                tie_break = my_bid + increment * MIN_BID_INCREMENT
                if tie_break <= ceiling and tie_break <= state.my_budget:
                    return tie_break
            return min(my_bid, state.my_budget)

        if final_round:
            self._last_equal_round_2 = None

        if opponent_bid <= my_bid:
            return min(my_bid, state.my_budget)

        required = opponent_bid + MIN_BID_INCREMENT
        if required > state.my_budget:
            return min(my_bid, state.my_budget)

        if required <= ceiling:
            return required
        return min(my_bid, state.my_budget)

    def _observe_completed_rounds(self, state: AuctionState) -> None:
        if len(state.opponent_bids) <= self._observed_bid_count:
            return

        if self._last_equal_round_2 is not None:
            opponent_raise = state.opponent_bids[-1] - self._last_equal_round_2
            if opponent_raise >= 2 * MIN_BID_INCREMENT:
                self._tie_increment = 3

        self._observed_bid_count = len(state.opponent_bids)


BOT_CLASS = CodexOptimal8Bot
