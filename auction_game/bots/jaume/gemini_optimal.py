from auction_game import AuctionBot, AuctionState
from auction_game.interfaces import MIN_BID_INCREMENT

class GeminiOptimalBot(AuctionBot):
    """
    An optimal sniper bot that carefully calculates the exact marginal score
    gained by winning an item (including the category bonus step-ups) and ensures 
    it never overpays. It bids minimally in early rounds and snipes the 
    opponent's previous bid plus a small safe margin in the final round.
    """

    def _get_category_bonus_rate(self, item_count: int) -> float:
        # Soft milestone curve up to 30%
        raw_rate = 0.06 * max(0, item_count - 1) + 0.02 * max(0, item_count - 3)
        return min(raw_rate, 0.30)

    def _calculate_marginal_value(self, state: AuctionState) -> int:
        cat = state.item.category
        
        # Calculate our current total value and item count in this category
        my_cat_items = [i for i in state.my_items if i.category == cat]
        current_count = len(my_cat_items)
        current_value = sum(i.value for i in my_cat_items)
        
        current_rate = self._get_category_bonus_rate(current_count)
        new_rate = self._get_category_bonus_rate(current_count + 1)
        
        current_bonus = current_value * current_rate
        new_bonus = (current_value + state.item.value) * new_rate
        bonus_delta = new_bonus - current_bonus
        
        # True value is the item's face value plus the boost it gives to our category bonus
        return int(state.item.value + bonus_delta)

    def choose_bid_round_1(self, state: AuctionState) -> int:
        # Round 1: Blind opening. Bid 0 to gather info on opponent's evaluation.
        return 0

    def choose_bid_round_2(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        # Round 2: Opponent's R1 bid is revealed.
        max_value = self._calculate_marginal_value(state)
        
        # Aim to cleanly beat their R1 bid
        target_bid = opponent_bid + MIN_BID_INCREMENT
        
        if target_bid <= max_value and target_bid <= state.my_budget:
            return target_bid
            
        return my_bid

    def choose_bid_round_3(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        # Round 3: Final bid. Opponent's R2 bid is revealed.
        max_value = self._calculate_marginal_value(state)
        
        # Double increments to edge out opponents bidding `our_r2 + min_increment`
        target_bid = opponent_bid + (2 * MIN_BID_INCREMENT)
        
        # Ensure we don't accidentally overpay beyond the item's true value
        target_bid = min(target_bid, max_value, state.my_budget)
        
        if target_bid >= opponent_bid + MIN_BID_INCREMENT:
            return target_bid
            
        # If we can't afford a valid raise or the item isn't worth it, don't raise
        return my_bid

BOT_CLASS = GeminiOptimalBot