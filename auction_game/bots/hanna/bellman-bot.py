from __future__ import annotations

from auction_game.interfaces import AuctionBot, AuctionItem, AuctionState, MIN_BID_INCREMENT

EXPECTED_ITEM_VALUE = 12_000_000
CATEGORY_ORDER = ("ai", "web", "brand", "cloud", "dev", "data")


class BellmanBot(AuctionBot):
    """Approximate Bellman bidder with category-aware continuation values."""

    def __init__(self) -> None:
        self._seen_items: list[AuctionItem] = []

    def choose_bid_round_1(self, state: AuctionState) -> int:
        self._remember_item(state)
        reservation = self._reservation_price(state, my_bid=0, opponent_bid=0, phase=1)
        if reservation <= 0:
            return 0

        opener = reservation * self._opening_fraction(state) // 100
        opener = max(0, min(opener, reservation, state.my_budget))
        if opener >= reservation and reservation >= MIN_BID_INCREMENT:
            opener = max(0, reservation - MIN_BID_INCREMENT)
        return opener

    def choose_bid_round_2(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        return self._follow_up_bid(state, my_bid, opponent_bid, phase=2)

    def choose_bid_round_3(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        return self._follow_up_bid(state, my_bid, opponent_bid, phase=3)

    def _follow_up_bid(self, state: AuctionState, my_bid: int, opponent_bid: int, *, phase: int) -> int:
        reservation = self._reservation_price(state, my_bid=my_bid, opponent_bid=opponent_bid, phase=phase)
        if opponent_bid < my_bid:
            return my_bid
        required_bid = opponent_bid + MIN_BID_INCREMENT
        if required_bid > reservation or required_bid > state.my_budget:
            return my_bid
        return max(my_bid, required_bid)

    def _reservation_price(self, state: AuctionState, *, my_bid: int, opponent_bid: int, phase: int) -> int:
        if state.my_budget <= 0:
            return 0

        my_counts, my_values = self._category_summary(state.my_items)
        opp_counts, opp_values = self._category_summary(state.opponent_items)
        category = state.item.category
        my_count = my_counts.get(category, 0)
        opp_count = opp_counts.get(category, 0)
        my_category_value = my_values.get(category, 0)
        opp_category_value = opp_values.get(category, 0)

        immediate_gain = state.item.value + self._incremental_bonus(my_count, my_category_value, state.item.value)
        denial_gain = self._denial_gain(opp_count, opp_category_value, state.item.value)
        future_gain = self._continuation_gain(state, my_count, opp_count)

        opponent_pressure = self._opponent_pressure(state, phase=phase)
        tie_gain = self._tie_break_gain(state, phase=phase, my_count=my_count, opp_count=opp_count)

        base_value = immediate_gain + denial_gain + future_gain + tie_gain
        adjusted = int(base_value * opponent_pressure)
        adjusted = min(adjusted, state.my_budget)

        budget_anchor = self._budget_anchor(state, category_count=my_count, phase=phase)
        adjusted = min(adjusted, budget_anchor)

        return max(0, adjusted)

    def _continuation_gain(self, state: AuctionState, my_count: int, opp_count: int) -> int:
        remaining_same_category = self._remaining_category_count(state)
        if remaining_same_category <= 0:
            return 0

        future_bonus = remaining_same_category * self._future_bonus_edge(my_count)
        denial_future = remaining_same_category * self._future_denial_edge(opp_count)
        urgency = 1.0 + 0.15 * min(2, my_count) + 0.10 * min(2, opp_count)
        if remaining_same_category == 1:
            urgency += 0.18
        elif remaining_same_category >= 3:
            urgency += 0.10
        return int((future_bonus + denial_future) * urgency)

    def _future_bonus_edge(self, count: int) -> int:
        current_rate = self._category_bonus_rate(count)
        next_rate = self._category_bonus_rate(count + 1)
        return int(EXPECTED_ITEM_VALUE * (1.0 + next_rate) - EXPECTED_ITEM_VALUE * (1.0 + current_rate))

    def _future_denial_edge(self, opp_count: int) -> int:
        if opp_count <= 0:
            return 0
        current_rate = self._category_bonus_rate(opp_count)
        next_rate = self._category_bonus_rate(opp_count + 1)
        return int(EXPECTED_ITEM_VALUE * (next_rate - current_rate) * 0.8)

    def _denial_gain(self, opp_count: int, opp_category_value: int, item_value: int) -> int:
        if opp_count <= 0:
            return 0
        current_bonus = self._category_bonus_value(opp_count, opp_category_value)
        future_bonus = self._category_bonus_value(opp_count + 1, opp_category_value + item_value)
        return int((future_bonus - current_bonus) * 0.65)

    def _tie_break_gain(self, state: AuctionState, *, phase: int, my_count: int, opp_count: int) -> int:
        if phase != 3:
            return 0
        if my_count >= 1 or opp_count >= 2:
            return MIN_BID_INCREMENT
        if state.total_rounds - state.round_index <= 3:
            return MIN_BID_INCREMENT
        return 0

    def _budget_anchor(self, state: AuctionState, *, category_count: int, phase: int) -> int:
        rounds_left = max(1, state.total_rounds - state.round_index)
        share = state.my_budget // rounds_left
        anchor = share + state.item.value // 2
        if category_count >= 1:
            anchor += state.item.value // 5
        if phase == 3:
            anchor += MIN_BID_INCREMENT
        if rounds_left <= 4:
            anchor += share // 2
        return min(state.my_budget, max(anchor, state.item.value // 2))

    def _opening_fraction(self, state: AuctionState) -> int:
        pressure = self._opponent_pressure(state, phase=1)
        if pressure >= 1.12:
            return 78
        if pressure <= 0.95:
            return 64
        return 71

    def _opponent_pressure(self, state: AuctionState, *, phase: int) -> float:
        past_items = self._seen_items[:-1]
        if not past_items:
            return 1.0 if phase == 1 else 1.03

        aggression_scores: list[float] = []
        for item, final_bid in zip(past_items, state.opponent_bids):
            if item.value <= 0:
                continue
            aggression_scores.append(final_bid / item.value)

        if not aggression_scores:
            return 1.0

        average = sum(aggression_scores) / len(aggression_scores)
        if average >= 1.02:
            return 1.16 if phase >= 2 else 1.08
        if average >= 0.90:
            return 1.08 if phase >= 2 else 1.02
        if average <= 0.65:
            return 0.94
        return 1.0

    def _remaining_category_count(self, state: AuctionState) -> int:
        current_index = self._category_index(state.item.category)
        remaining = 0
        for future_round in range(state.round_index + 1, state.total_rounds):
            if future_round % len(CATEGORY_ORDER) == current_index:
                remaining += 1
        return remaining

    def _category_index(self, category: str) -> int:
        try:
            return CATEGORY_ORDER.index(category)
        except ValueError:
            return 0

    def _category_summary(self, items: tuple[AuctionItem, ...]) -> tuple[dict[str, int], dict[str, int]]:
        counts: dict[str, int] = {}
        values: dict[str, int] = {}
        for item in items:
            counts[item.category] = counts.get(item.category, 0) + 1
            values[item.category] = values.get(item.category, 0) + item.value
        return counts, values

    def _incremental_bonus(self, count: int, current_category_value: int, item_value: int) -> int:
        current_bonus = self._category_bonus_value(count, current_category_value)
        next_bonus = self._category_bonus_value(count + 1, current_category_value + item_value)
        return next_bonus - current_bonus

    def _category_bonus_value(self, count: int, total_value: int) -> int:
        return int(total_value * self._category_bonus_rate(count))

    def _category_bonus_rate(self, item_count: int) -> float:
        raw_rate = 0.06 * max(0, item_count - 1) + 0.02 * max(0, item_count - 3)
        return min(raw_rate, 0.30)

    def _remember_item(self, state: AuctionState) -> None:
        if len(self._seen_items) == state.round_index:
            self._seen_items.append(state.item)


BOT_CLASS = BellmanBot
