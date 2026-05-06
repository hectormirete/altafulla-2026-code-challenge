from auction_game.interfaces import AuctionBot, AuctionState, MIN_BID_INCREMENT
from auction_game.engine import DEFAULT_BUDGET

class TestSimpleBot(AuctionBot):
    def choose_bid_round_1(self, state: AuctionState) -> int:
        return self._bid(state)

    def choose_bid_round_2(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        return self._bid(state)

    def choose_bid_round_3(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        return self._bid(state)
    
    def _bid(self, state: AuctionState) -> int:
        if state.item.category in ("ai", "web"):
            return state.item.value
        
        return 0


BOT_CLASS = TestSimpleBot