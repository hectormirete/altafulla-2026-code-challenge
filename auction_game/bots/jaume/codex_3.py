from __future__ import annotations

from collections import defaultdict

from auction_game.interfaces import AuctionBot, AuctionItem, AuctionState, MIN_BID_INCREMENT


class Codex3Bot(AuctionBot):
    _CATEGORY_ORDER = ("ai", "web", "brand", "cloud", "dev", "data")

    def choose_bid_round_1(self, state: AuctionState) -> int:
        target = self._target_price(state, phase=1, my_bid=0, opponent_bid=0)
        if target <= 0:
            return 0

        pressure = self._estimated_market_price(state)
        opener = min(target, max(MIN_BID_INCREMENT, int(pressure * 0.84)))
        if self._category_priority(state) >= 2.4:
            opener = min(target, max(opener, int(target * 0.60)))
        return self._clamp(opener, state.my_budget)

    def choose_bid_round_2(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        return self._respond(state, my_bid, opponent_bid, phase=2)

    def choose_bid_round_3(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        return self._respond(state, my_bid, opponent_bid, phase=3)

    def _respond(self, state: AuctionState, my_bid: int, opponent_bid: int, *, phase: int) -> int:
        target = self._target_price(state, phase=phase, my_bid=my_bid, opponent_bid=opponent_bid)
        if target <= my_bid or opponent_bid >= target:
            return my_bid
        if phase == 3 and opponent_bid == my_bid:
            return self._clamp(min(target, opponent_bid + 2 * MIN_BID_INCREMENT), state.my_budget)
        if opponent_bid >= my_bid:
            return self._clamp(min(target, opponent_bid + MIN_BID_INCREMENT), state.my_budget)
        return self._clamp(max(my_bid, min(target, my_bid + MIN_BID_INCREMENT)), state.my_budget)

    def _target_price(self, state: AuctionState, *, phase: int, my_bid: int, opponent_bid: int) -> int:
        rounds_left = state.total_rounds - state.round_index
        if rounds_left <= 0 or state.my_budget <= 0:
            return 0

        category = state.item.category
        my_count, my_value = self._category_summary(state.my_items).get(category, (0, 0))
        opp_count, opp_value = self._category_summary(state.opponent_items).get(category, (0, 0))
        remaining_same_category = self._remaining_category_count(state, category)
        category_total = self._category_total_count(state.total_rounds, category)

        own_gain = state.item.value + self._bonus_gain(my_count, my_value, state.item.value)
        deny_gain = self._denial_gain(opp_count, opp_value, state.item.value)
        future_tax = self._future_commitment_tax(state, category)
        priority = self._category_priority(state)

        urgency = 1.0
        if remaining_same_category == 0:
            urgency += 0.44
        elif remaining_same_category == 1:
            urgency += 0.24
        if category_total == 4:
            urgency += 0.10
        if my_count >= 2:
            urgency += 0.16
        if opp_count >= 2:
            urgency += 0.18

        market_price = self._estimated_market_price(state)
        value_ceiling = (own_gain + deny_gain) * urgency - future_tax
        pressure_adjusted = max(value_ceiling, market_price * (1.10 if phase == 3 else 1.02))

        if opponent_bid > 0:
            overpay_penalty = max(0, opponent_bid - own_gain) * 0.30
            pressure_adjusted -= overpay_penalty

        if priority < 1.0:
            pressure_adjusted *= 0.72
        elif priority < 1.8:
            pressure_adjusted *= 0.94
        elif priority > 2.6:
            pressure_adjusted *= 1.14

        budget_cap = self._budget_cap(state, phase=phase, priority=priority, rounds_left=rounds_left)
        target = int(min(pressure_adjusted, budget_cap))

        if phase == 1 and target > 0:
            target = min(target, max(market_price + MIN_BID_INCREMENT, int(target * 0.92)))

        if my_bid > target:
            return my_bid
        return self._clamp(target, state.my_budget)

    def _category_priority(self, state: AuctionState) -> float:
        category = state.item.category
        my_count, my_value = self._category_summary(state.my_items).get(category, (0, 0))
        opp_count, opp_value = self._category_summary(state.opponent_items).get(category, (0, 0))
        remaining = self._remaining_category_count(state, category)

        priority = 1.0
        priority += 0.55 * my_count
        priority += 0.25 * opp_count
        priority += 0.18 if remaining == 0 else 0.0
        priority += 0.10 if remaining == 1 else 0.0
        priority += 0.12 if my_value >= 24_000_000 else 0.0
        priority += 0.10 if opp_value >= 24_000_000 else 0.0
        return priority

    def _denial_gain(self, opp_count: int, opp_value: int, item_value: int) -> int:
        next_bonus = self._category_bonus(opp_count + 1, opp_value + item_value)
        current_bonus = self._category_bonus(opp_count, opp_value)
        blocked_bonus = next_bonus - current_bonus
        denial_weight = 0.52 + 0.12 * max(0, opp_count - 1)
        return int(item_value * 0.35 + blocked_bonus * denial_weight)

    def _future_commitment_tax(self, state: AuctionState, category: str) -> float:
        remaining = self._remaining_category_count(state, category)
        if remaining == 0:
            return 0.0
        avg_future_budget = state.my_budget / max(1, state.total_rounds - state.round_index)
        return avg_future_budget * 0.04 * remaining

    def _budget_cap(self, state: AuctionState, *, phase: int, priority: float, rounds_left: int) -> int:
        baseline = state.my_budget / max(1, rounds_left)
        reserve_per_round = max(4_000_000, int(baseline * 0.42))
        reserve = max(0, rounds_left - 1) * reserve_per_round
        available = max(0, state.my_budget - reserve)

        multiplier = 1.55 + min(priority, 3.0) * 0.48
        if phase == 3:
            multiplier += 0.24

        soft_cap = int(baseline * multiplier)
        hard_cap = int(state.item.value * (1.70 if priority >= 2.5 else 1.35))
        return max(MIN_BID_INCREMENT, min(state.my_budget, max(soft_cap, min(hard_cap, available))))

    def _estimated_market_price(self, state: AuctionState) -> int:
        if not state.opponent_bids:
            return min(
                state.item.value,
                max(MIN_BID_INCREMENT, state.my_budget // max(1, state.total_rounds - state.round_index)),
            )

        recent = list(state.opponent_bids[-4:])
        average = sum(recent) / len(recent)
        peak = max(recent)
        category = state.item.category
        same_category_bids = [
            bid
            for index, bid in enumerate(state.opponent_bids)
            if self._CATEGORY_ORDER[index % len(self._CATEGORY_ORDER)] == category
        ]
        category_average = (sum(same_category_bids) / len(same_category_bids)) if same_category_bids else average
        blended = average * 0.45 + peak * 0.20 + category_average * 0.35
        return int(min(state.my_budget, max(MIN_BID_INCREMENT, blended)))

    def _remaining_category_count(self, state: AuctionState, category: str) -> int:
        return sum(
            1
            for future_round in range(state.round_index + 1, state.total_rounds)
            if self._CATEGORY_ORDER[future_round % len(self._CATEGORY_ORDER)] == category
        )

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

    def _bonus_gain(self, count: int, value: int, item_value: int) -> int:
        return self._category_bonus(count + 1, value + item_value) - self._category_bonus(count, value)

    def _category_bonus(self, count: int, value: int) -> int:
        rate = min(0.06 * max(0, count - 1) + 0.02 * max(0, count - 3), 0.30)
        return int(value * rate)

    def _clamp(self, bid: int | float, budget: int) -> int:
        return max(0, min(int(bid), budget))


BOT_CLASS = Codex3Bot
