import random

from auction_game.interfaces import AuctionBot, AuctionState


class RandomBidderBot(AuctionBot):
    def choose_bid_round_1(self, state: AuctionState) -> int:
        return random.randint(0, state.my_budget)

    def choose_bid_round_2(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        return random.randint(my_bid, state.my_budget)

    def choose_bid_round_3(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        return random.randint(my_bid, state.my_budget)


BOT_CLASS = RandomBidderBot
