from __future__ import annotations

from auction_game import AuctionState, MIN_BID_INCREMENT
from auction_game.bots.jaume.codex_optimal_8 import CodexOptimal8Bot


class CodexOptimal9Bot(CodexOptimal8Bot):
    """CodexOptimal8 with a guard against first-round near-clone bait."""

    def choose_bid_round_2(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        opening_gap = opponent_bid - my_bid
        if state.round_index == 0 and opening_gap == 0:
            self._tie_increment = 3
        if state.round_index == 0 and 0 < opening_gap < MIN_BID_INCREMENT:
            self._tie_increment = 3
            return my_bid
        return super().choose_bid_round_2(state, my_bid, opponent_bid)


BOT_CLASS = CodexOptimal9Bot
