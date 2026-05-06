from __future__ import annotations

from auction_game import AuctionState, MIN_BID_INCREMENT
from auction_game.bots.jaume.codex_optimal_4 import CodexOptimal4Bot


class CodexOptimal7Bot(CodexOptimal4Bot):
    """CodexOptimal4 valuation with a stronger final-round tie breaker."""

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
            tie_break = my_bid + 2 * MIN_BID_INCREMENT
            if tie_break <= ceiling and tie_break <= state.my_budget:
                return tie_break

            minimum_tie_break = my_bid + MIN_BID_INCREMENT
            if minimum_tie_break <= ceiling and minimum_tie_break <= state.my_budget:
                return minimum_tie_break
            return min(my_bid, state.my_budget)

        if opponent_bid <= my_bid:
            return min(my_bid, state.my_budget)

        required = opponent_bid + MIN_BID_INCREMENT
        if required > state.my_budget:
            return min(my_bid, state.my_budget)

        if required <= ceiling:
            return required
        return min(my_bid, state.my_budget)


BOT_CLASS = CodexOptimal7Bot
