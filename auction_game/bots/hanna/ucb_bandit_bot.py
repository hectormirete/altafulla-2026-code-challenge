from __future__ import annotations

import math

from auction_game.interfaces import AuctionBot, AuctionItem, AuctionState, MIN_BID_INCREMENT

EXPECTED_ITEM_VALUE = 12_000_000
CATEGORY_ORDER = ("ai", "web", "brand", "cloud", "dev", "data")
ARM_MULTIPLIERS = (60, 75, 90, 100, 112, 125)
ARM_EXPLORATION_ORDER = (2, 3, 1, 4, 0, 5)
UCB_EXPLORATION_WEIGHT = 0.55


class UCBBanditBot(AuctionBot):
    """Treats bid aggression as a UCB bandit over reservation-price multipliers."""

    def __init__(self) -> None:
        self._seen_items: list[AuctionItem] = []
        self._chosen_arms: list[int] = []
        self._strategic_values: list[int] = []
        self._reservation_values: list[int] = []
        self._arm_counts = [0] * len(ARM_MULTIPLIERS)
        self._arm_reward_sums = [0.0] * len(ARM_MULTIPLIERS)
        self._resolved_rounds = 0

    def choose_bid_round_1(self, state: AuctionState) -> int:
        self._sync_history(state)
        self._remember_item(state)

        strategic_value = self._strategic_value(state)
        if strategic_value <= 0 or state.my_budget <= 0:
            self._chosen_arms.append(ARM_EXPLORATION_ORDER[0])
            self._strategic_values.append(0)
            self._reservation_values.append(0)
            return 0

        arm_index = self._select_arm()
        reservation = min(
            state.my_budget,
            self._budget_cap(state, strategic_value),
            strategic_value * ARM_MULTIPLIERS[arm_index] // 100,
        )
        opener = min(
            reservation,
            max(0, strategic_value * self._opening_fraction(state, arm_index) // 100),
        )

        if opener >= reservation and reservation >= MIN_BID_INCREMENT:
            opener = max(0, reservation - MIN_BID_INCREMENT)

        self._chosen_arms.append(arm_index)
        self._strategic_values.append(strategic_value)
        self._reservation_values.append(reservation)
        return opener

    def choose_bid_round_2(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        return self._follow_up_bid(state, my_bid, opponent_bid, phase=2)

    def choose_bid_round_3(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        return self._follow_up_bid(state, my_bid, opponent_bid, phase=3)

    def _follow_up_bid(self, state: AuctionState, my_bid: int, opponent_bid: int, *, phase: int) -> int:
        reservation = self._reservation_values[state.round_index]
        if reservation <= my_bid:
            return my_bid

        if opponent_bid > my_bid:
            required_bid = opponent_bid + MIN_BID_INCREMENT
        elif phase == 3 and opponent_bid == my_bid and self._should_break_tie(state):
            required_bid = my_bid + MIN_BID_INCREMENT
        else:
            return my_bid

        if required_bid > reservation or required_bid > state.my_budget:
            return my_bid
        return required_bid

    def _sync_history(self, state: AuctionState) -> None:
        while self._resolved_rounds < state.round_index:
            round_index = self._resolved_rounds
            arm_index = self._chosen_arms[round_index]
            strategic_value = self._strategic_values[round_index]
            item = self._seen_items[round_index]
            my_final_bid = state.my_bids[round_index]
            opponent_final_bid = state.opponent_bids[round_index]

            if my_final_bid > opponent_final_bid:
                realized_margin = strategic_value - my_final_bid
            elif opponent_final_bid > my_final_bid:
                if opponent_final_bid > strategic_value:
                    realized_margin = item.value // 4
                else:
                    realized_margin = -(strategic_value - opponent_final_bid) // 2
            else:
                realized_margin = 0

            reward = self._normalize_reward(realized_margin, item.value)
            self._arm_counts[arm_index] += 1
            self._arm_reward_sums[arm_index] += reward
            self._resolved_rounds += 1

    def _select_arm(self) -> int:
        for arm_index in ARM_EXPLORATION_ORDER:
            if self._arm_counts[arm_index] == 0:
                return arm_index

        total_pulls = sum(self._arm_counts)
        best_arm_index = 0
        best_score = float("-inf")
        log_total = math.log(total_pulls)
        for arm_index, pulls in enumerate(self._arm_counts):
            mean_reward = self._arm_reward_sums[arm_index] / pulls
            confidence = UCB_EXPLORATION_WEIGHT * math.sqrt(log_total / pulls)
            score = mean_reward + confidence
            if score > best_score:
                best_score = score
                best_arm_index = arm_index
        return best_arm_index

    def _strategic_value(self, state: AuctionState) -> int:
        category = state.item.category
        my_counts, my_values = self._category_summary(state.my_items)
        opp_counts, opp_values = self._category_summary(state.opponent_items)

        my_count = my_counts.get(category, 0)
        opp_count = opp_counts.get(category, 0)
        my_category_value = my_values.get(category, 0)
        opp_category_value = opp_values.get(category, 0)
        remaining_same_category = self._remaining_category_count(state)

        direct_value = state.item.value + self._incremental_bonus(my_count, my_category_value, state.item.value)
        denial_value = self._denial_gain(opp_count, opp_category_value, state.item.value)
        future_value = remaining_same_category * self._future_category_edge(my_count, opp_count)

        urgency_multiplier = 1.0
        if remaining_same_category == 0:
            urgency_multiplier += 0.28
        elif remaining_same_category == 1:
            urgency_multiplier += 0.14
        if my_count >= 1:
            urgency_multiplier += 0.08 * min(my_count, 2)
        if opp_count >= 2:
            urgency_multiplier += 0.10

        score_gap = self._score(state.my_items, state.my_budget) - self._score(
            state.opponent_items,
            state.opponent_budget,
        )
        if score_gap < 0:
            urgency_multiplier += min(0.20, (-score_gap) / 120_000_000)
        elif score_gap > 30_000_000:
            urgency_multiplier -= 0.08

        strategic_value = int((direct_value + denial_value + future_value) * urgency_multiplier)
        strategic_value = max(strategic_value, state.item.value // 3)
        return min(strategic_value, state.my_budget)

    def _budget_cap(self, state: AuctionState, strategic_value: int) -> int:
        rounds_left = max(1, state.total_rounds - state.round_index)
        baseline_share = state.my_budget // rounds_left
        anchor = baseline_share + state.item.value // 2

        category_count = sum(1 for item in state.my_items if item.category == state.item.category)
        if category_count >= 1:
            anchor += state.item.value // 4
        if rounds_left <= 4:
            anchor += baseline_share // 2

        return min(state.my_budget, max(anchor, strategic_value // 2))

    def _opening_fraction(self, state: AuctionState, arm_index: int) -> int:
        if state.round_index <= 2:
            return 60 + arm_index * 4
        if self._arm_counts[arm_index] >= 2:
            return 64 + arm_index * 4
        return 58 + arm_index * 4

    def _should_break_tie(self, state: AuctionState) -> bool:
        category = state.item.category
        my_count = sum(1 for item in state.my_items if item.category == category)
        opp_count = sum(1 for item in state.opponent_items if item.category == category)
        return my_count >= 1 or opp_count >= 2 or self._remaining_category_count(state) == 0

    def _remaining_category_count(self, state: AuctionState) -> int:
        category_index = self._category_index(state.item.category)
        remaining = 0
        for future_round in range(state.round_index + 1, state.total_rounds):
            if future_round % len(CATEGORY_ORDER) == category_index:
                remaining += 1
        return remaining

    def _category_index(self, category: str) -> int:
        try:
            return CATEGORY_ORDER.index(category)
        except ValueError:
            return 0

    def _future_category_edge(self, my_count: int, opp_count: int) -> int:
        my_next = self._category_bonus_rate(my_count + 1) - self._category_bonus_rate(my_count)
        opp_next = self._category_bonus_rate(opp_count + 1) - self._category_bonus_rate(opp_count)
        return int(EXPECTED_ITEM_VALUE * (my_next + 0.55 * opp_next))

    def _denial_gain(self, opp_count: int, opp_category_value: int, item_value: int) -> int:
        if opp_count <= 0:
            return 0
        current_bonus = self._category_bonus_value(opp_count, opp_category_value)
        next_bonus = self._category_bonus_value(opp_count + 1, opp_category_value + item_value)
        return int((next_bonus - current_bonus) * 0.50)

    def _incremental_bonus(self, count: int, current_value: int, item_value: int) -> int:
        current_bonus = self._category_bonus_value(count, current_value)
        next_bonus = self._category_bonus_value(count + 1, current_value + item_value)
        return next_bonus - current_bonus

    def _category_bonus_value(self, count: int, total_value: int) -> int:
        return int(total_value * self._category_bonus_rate(count))

    def _category_bonus_rate(self, count: int) -> float:
        raw_rate = 0.06 * max(0, count - 1) + 0.02 * max(0, count - 3)
        return min(raw_rate, 0.30)

    def _category_summary(self, items: tuple[AuctionItem, ...]) -> tuple[dict[str, int], dict[str, int]]:
        counts: dict[str, int] = {}
        values: dict[str, int] = {}
        for item in items:
            counts[item.category] = counts.get(item.category, 0) + 1
            values[item.category] = values.get(item.category, 0) + item.value
        return counts, values

    def _score(self, items: tuple[AuctionItem, ...], money_left: int) -> int:
        total_item_value = sum(item.value for item in items)
        category_values: dict[str, int] = {}
        category_counts: dict[str, int] = {}
        for item in items:
            category_values[item.category] = category_values.get(item.category, 0) + item.value
            category_counts[item.category] = category_counts.get(item.category, 0) + 1

        category_bonus = 0
        for category, total_value in category_values.items():
            category_bonus += int(total_value * self._category_bonus_rate(category_counts[category]))
        return total_item_value + category_bonus + money_left

    def _normalize_reward(self, realized_margin: int, item_value: int) -> float:
        if item_value <= 0:
            return 0.5
        scaled = 0.5 + (realized_margin / item_value) * 0.5
        return max(0.0, min(1.0, scaled))

    def _remember_item(self, state: AuctionState) -> None:
        if len(self._seen_items) == state.round_index:
            self._seen_items.append(state.item)


BOT_CLASS = UCBBanditBot
