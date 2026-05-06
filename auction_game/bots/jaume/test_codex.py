from __future__ import annotations

from collections import defaultdict

from auction_game.interfaces import AuctionBot, AuctionItem, AuctionState, MIN_BID_INCREMENT


class TestCodexBot(AuctionBot):
    _CATEGORY_ORDER = ("ai", "web", "brand", "cloud", "dev", "data")

    def choose_bid_round_1(self, state: AuctionState) -> int:
        ceiling = self._ceiling(state, phase=1)
        if ceiling <= 0:
            return 0
        opener = min(ceiling, max(MIN_BID_INCREMENT, ceiling // 3))
        return self._clamp_bid(opener, state.my_budget)

    def choose_bid_round_2(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        return self._follow_up_bid(state, my_bid, opponent_bid, phase=2)

    def choose_bid_round_3(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        return self._follow_up_bid(state, my_bid, opponent_bid, phase=3)

    def _follow_up_bid(self, state: AuctionState, my_bid: int, opponent_bid: int, *, phase: int) -> int:
        ceiling = self._ceiling(state, phase=phase)
        if ceiling <= my_bid:
            return my_bid
        if opponent_bid >= ceiling:
            return my_bid
        if opponent_bid >= my_bid:
            return min(opponent_bid + MIN_BID_INCREMENT, ceiling, state.my_budget)
        target = min(ceiling, max(my_bid, opponent_bid + MIN_BID_INCREMENT))
        return self._clamp_bid(target, state.my_budget)

    def _ceiling(self, state: AuctionState, *, phase: int) -> int:
        rounds_left = state.total_rounds - state.round_index
        if rounds_left <= 0 or state.my_budget <= 0:
            return 0

        category = state.item.category
        my_summary = self._category_summary(state.my_items)
        opponent_summary = self._category_summary(state.opponent_items)
        my_count, my_value = my_summary.get(category, (0, 0))
        opponent_count, opponent_value = opponent_summary.get(category, (0, 0))
        total_in_category = self._category_total_count(state.total_rounds, category)
        remaining_after = self._remaining_category_count(state, category)

        own_delta = state.item.value + self._bonus_delta(my_count, my_value, state.item.value)
        opponent_delta = state.item.value + self._bonus_delta(opponent_count, opponent_value, state.item.value)

        milestone_bonus = 0
        if my_count == 0 and remaining_after >= 1:
            milestone_bonus += state.item.value * 0.08
        if my_count == 1:
            milestone_bonus += state.item.value * 0.20
        elif my_count == 2:
            milestone_bonus += state.item.value * 0.26
        elif my_count >= 3:
            milestone_bonus += state.item.value * 0.16

        scarcity_bonus = 0
        if total_in_category == 4:
            scarcity_bonus += state.item.value * 0.08
        if remaining_after == 0:
            scarcity_bonus += state.item.value * 0.14
        elif remaining_after == 1:
            scarcity_bonus += state.item.value * 0.08

        denial_bonus = opponent_delta * (0.55 if opponent_count >= my_count else 0.35)
        raw_ceiling = own_delta + milestone_bonus + scarcity_bonus + denial_bonus

        budget_cap = self._budget_cap(state, total_in_category=total_in_category, my_count=my_count, phase=phase)
        return self._clamp_bid(int(min(raw_ceiling, budget_cap)), state.my_budget)

    def _budget_cap(self, state: AuctionState, *, total_in_category: int, my_count: int, phase: int) -> int:
        rounds_left = max(1, state.total_rounds - state.round_index)
        base = state.my_budget / rounds_left

        if total_in_category == 4:
            multiplier = 2.1
        else:
            multiplier = 1.8

        if my_count >= 1:
            multiplier += 0.35
        if my_count >= 2:
            multiplier += 0.30
        if phase == 3:
            multiplier += 0.25

        # Keep enough budget to remain competitive in later rounds.
        reserve = max(0, rounds_left - 1) * max(4_000_000, int(base * 0.42))
        available = max(0, state.my_budget - reserve)
        soft_cap = int(base * multiplier)
        return max(MIN_BID_INCREMENT, min(state.my_budget, max(soft_cap, available)))

    def _remaining_category_count(self, state: AuctionState, category: str) -> int:
        remaining = 0
        for future_round in range(state.round_index + 1, state.total_rounds):
            if self._CATEGORY_ORDER[future_round % len(self._CATEGORY_ORDER)] == category:
                remaining += 1
        return remaining

    def _category_total_count(self, total_rounds: int, category: str) -> int:
        return sum(
            1
            for round_index in range(total_rounds)
            if self._CATEGORY_ORDER[round_index % len(self._CATEGORY_ORDER)] == category
        )

    def _category_summary(self, items: tuple[AuctionItem, ...]) -> dict[str, tuple[int, int]]:
        summary: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for item in items:
            summary[item.category][0] += 1
            summary[item.category][1] += item.value
        return {category: (count, value) for category, (count, value) in summary.items()}

    def _bonus_delta(self, count: int, value: int, item_value: int) -> int:
        current_bonus = self._category_bonus(count, value)
        next_bonus = self._category_bonus(count + 1, value + item_value)
        return next_bonus - current_bonus

    def _category_bonus(self, count: int, value: int) -> int:
        rate = min(0.06 * max(0, count - 1) + 0.02 * max(0, count - 3), 0.30)
        return int(value * rate)

    def _clamp_bid(self, bid: int, budget: int) -> int:
        return max(0, min(int(bid), budget))


BOT_CLASS = TestCodexBot
