from __future__ import annotations

from collections import defaultdict

from auction_game.interfaces import AuctionBot, AuctionState, MIN_BID_INCREMENT


def _category_bonus_rate(item_count: int) -> float:
    raw_rate = 0.06 * max(0, item_count - 1) + 0.02 * max(0, item_count - 3)
    return min(raw_rate, 0.30)


def _category_totals(items) -> tuple[dict[str, int], dict[str, int]]:
    counts: dict[str, int] = defaultdict(int)
    values: dict[str, int] = defaultdict(int)
    for item in items:
        counts[item.category] += 1
        values[item.category] += item.value
    return counts, values


def _marginal_bonus_gain(current_count: int, current_value: int, item_value: int) -> int:
    before = int(current_value * _category_bonus_rate(current_count))
    after = int((current_value + item_value) * _category_bonus_rate(current_count + 1))
    return after - before


class CategoryHarvesterBot(AuctionBot):
    def _history_pressure(self, state: AuctionState) -> float:
        if not state.my_bids or not state.opponent_bids:
            return 0.0
        pressure = 0
        for my_bid, opp_bid in zip(state.my_bids, state.opponent_bids):
            if opp_bid >= my_bid + MIN_BID_INCREMENT:
                pressure += 1
        return pressure / max(1, len(state.my_bids))

    def _history_ratio(self, state: AuctionState) -> float:
        if not state.my_bids or not state.opponent_bids:
            return 1.0
        return sum(opp / max(1, my) for my, opp in zip(state.my_bids, state.opponent_bids)) / max(1, len(state.my_bids))

    def _recent_ratios(self, state: AuctionState, window: int = 4) -> tuple[float, float]:
        if not state.my_bids or not state.opponent_bids:
            return 1.0, 0.0
        pairs = list(zip(state.my_bids[-window:], state.opponent_bids[-window:]))
        ratios = [opp / max(1, my) for my, opp in pairs]
        advantages = [(opp - my) / max(1, state.item.value) for my, opp in pairs]
        return sum(ratios) / max(1, len(ratios)), sum(advantages) / max(1, len(advantages))

    def _bullyish_opponent(self, state: AuctionState) -> bool:
        if len(state.opponent_bids) < 3:
            return False
        pressure = self._history_pressure(state)
        ratio = self._history_ratio(state)
        recent_ratio, recent_advantage = self._recent_ratios(state)
        return (
            pressure >= 0.55
            and 0.78 <= ratio <= 1.12
            and recent_ratio >= 0.82
            and recent_ratio <= 1.10
            and recent_advantage >= -0.08
            and recent_advantage <= 0.10
            and state.opponent_budget >= state.my_budget * 2 // 3
        )

    def _kingish_opponent(self, state: AuctionState) -> bool:
        if len(state.opponent_bids) < 4:
            return False
        pressure = self._history_pressure(state)
        ratio = self._history_ratio(state)
        recent_ratio, recent_advantage = self._recent_ratios(state)
        ties = sum(
            1
            for my_bid, opp_bid in zip(state.my_bids, state.opponent_bids)
            if abs(my_bid - opp_bid) <= MIN_BID_INCREMENT
        )
        return (
            pressure >= 0.40
            and 0.88 <= ratio <= 1.22
            and recent_ratio >= 0.92
            and abs(recent_advantage) <= 0.10
            and ties >= 1
            and state.opponent_budget >= state.my_budget * 4 // 5
        )

    def _opponent_profile(self, state: AuctionState) -> str:
        if self._bullyish_opponent(state):
            return "bully"
        if self._kingish_opponent(state):
            return "king"
        return "neutral"

    def _bully_focus_category(self, state: AuctionState) -> str | None:
        opp_counts, opp_values = _category_totals(state.opponent_items)
        if not opp_counts:
            return None
        return max(opp_counts, key=lambda category: (opp_counts[category], opp_values[category]))

    def _is_contested(self, my_count: int, opp_count: int) -> bool:
        return my_count > 0 or opp_count > 0

    def _is_strategic_item(self, state: AuctionState, my_count: int, opp_count: int, bonus_gain: int) -> bool:
        if bonus_gain >= state.item.value // 10:
            return True
        if my_count >= 2 or opp_count >= 2:
            return True
        if state.item.value >= 15_000_000 and self._is_contested(my_count, opp_count):
            return True
        bully_like = self._bullyish_opponent(state)
        if bully_like and self._bully_focus_category(state) == state.item.category:
            return True
        return False

    def _aggressive_bully_bid(self, state: AuctionState) -> int:
        opp_counts, _ = _category_totals(state.opponent_items)
        owned_count = opp_counts[state.item.category]
        if owned_count >= 3:
            percent = 108
        elif owned_count >= 1:
            percent = 92
        else:
            percent = 80
        ceiling = min(int(state.item.value * 1.10), state.opponent_budget)
        return max(0, min(ceiling, int(state.item.value * percent / 100)))

    def _spend_cap(self, state: AuctionState, my_count: int, opp_count: int, bonus_gain: int) -> int:
        rounds_left = max(1, state.total_rounds - state.round_index)
        budget_share = max(1, state.my_budget // rounds_left)
        reserve = budget_share
        bully_like = self._bullyish_opponent(state)
        king_like = self._kingish_opponent(state)
        bully_focus = self._bully_focus_category(state)
        bully_target = bully_like and bully_focus == state.item.category
        king_target = king_like and self._kingish_opponent(state) and (
            my_count > 0
            or opp_count > 0
            or bonus_gain >= state.item.value // 10
        )

        strategic = bonus_gain >= state.item.value // 10 or my_count > 0 or opp_count > 0

        if my_count > 0:
            reserve -= min(budget_share // 3, state.item.value // 8)
        if opp_count > 0:
            reserve -= min(budget_share // 4, state.item.value // 10 * min(opp_count, 3))
        if bully_like and strategic:
            reserve -= min(budget_share // 2, state.item.value // 6)
            if bully_target:
                reserve -= min(budget_share // 4, state.item.value // 10)
        elif bully_like and not strategic:
            reserve += budget_share // 4
        if king_like and strategic:
            reserve -= min(budget_share // 4, state.item.value // 10)
        elif king_like and not strategic:
            reserve += budget_share // 4
        if bully_target and bonus_gain > 0:
            reserve -= min(budget_share // 5, state.item.value // 12)
        if king_target and bonus_gain > 0:
            reserve -= min(budget_share // 6, state.item.value // 14)
        if rounds_left <= 3:
            reserve //= 2
        return max(0, state.my_budget - max(0, reserve))

    def _category_state(self, state: AuctionState) -> tuple[int, int, int, int]:
        my_counts, my_values = _category_totals(state.my_items)
        opp_counts, opp_values = _category_totals(state.opponent_items)

        my_count = my_counts[state.item.category]
        my_value = my_values[state.item.category]
        opp_count = opp_counts[state.item.category]
        opp_value = opp_values[state.item.category]
        return my_count, my_value, opp_count, opp_value

    def _harvest_value(self, state: AuctionState) -> tuple[int, int, int, int, int]:
        my_count, my_value, opp_count, opp_value = self._category_state(state)
        bonus_gain = _marginal_bonus_gain(my_count, my_value, state.item.value)
        harvest_value = state.item.value + bonus_gain
        return my_count, my_value, opp_count, opp_value, harvest_value

    def _concentration_multiplier(self, my_count: int, opp_count: int) -> float:
        if my_count == 0 and opp_count == 0:
            return 0.70

        multiplier = 0.72 + 0.09 * min(my_count, 4)
        if my_count > 0:
            multiplier += 0.04 * min(max(my_count - 1, 0), 3)
        if opp_count > 0:
            multiplier += 0.03 * min(opp_count, 3)
        if opp_count > my_count:
            multiplier += 0.05 * min(opp_count - my_count, 3)
        return min(multiplier, 0.90)

    def _budget_guard(self, state: AuctionState, my_count: int, opp_count: int) -> int:
        rounds_left = max(1, state.total_rounds - state.round_index)
        paced_budget = state.my_budget // rounds_left
        bully_like = self._bullyish_opponent(state)
        king_like = self._kingish_opponent(state)
        bonus_gain = _marginal_bonus_gain(my_count, sum(item.value for item in state.my_items if item.category == state.item.category), state.item.value)

        if bully_like and (my_count > 0 or opp_count > 0):
            paced_budget += int(state.item.value * (0.16 + 0.04 * min(my_count + opp_count, 4)))
        elif my_count > 0:
            paced_budget += int(state.item.value * (0.12 + 0.03 * min(my_count, 3)))
        else:
            paced_budget += int(state.item.value * 0.08)

        if bully_like and opp_count > 0:
            paced_budget += int(state.item.value * (0.08 + 0.02 * min(opp_count, 3)))
        elif opp_count > 0:
            paced_budget += int(state.item.value * (0.04 + 0.01 * min(opp_count, 3)))
        if bully_like and opp_count > my_count:
            paced_budget += int(state.item.value * 0.06 * min(opp_count - my_count, 3))
        elif opp_count > my_count:
            paced_budget += int(state.item.value * 0.03 * min(opp_count - my_count, 3))
        if bully_like and bonus_gain <= 0 and my_count == 0 and opp_count == 0:
            paced_budget -= int(state.item.value * 0.20)
        if king_like and bonus_gain <= 0 and my_count == 0 and opp_count == 0:
            paced_budget -= int(state.item.value * 0.10)
        if rounds_left <= 4:
            paced_budget += int(state.item.value * (0.08 if bully_like else 0.05))

        floor = state.item.value
        if bully_like and (my_count > 0 or opp_count > 0):
            floor = state.item.value * 11 // 10
        elif my_count > 0 or opp_count > 0:
            floor = state.item.value * 4 // 5
        if bully_like and my_count > 0 and opp_count > 0:
            floor = state.item.value * 12 // 10
        return min(state.my_budget, max(floor, paced_budget))

    def _opening_bid(self, state: AuctionState) -> int:
        my_count, my_value, opp_count, opp_value, harvest_value = self._harvest_value(state)
        bonus_gain = harvest_value - state.item.value
        multiplier = self._concentration_multiplier(my_count, opp_count)
        contested = self._is_contested(my_count, opp_count)
        bully_like = self._bullyish_opponent(state)
        king_like = self._kingish_opponent(state)
        bully_focus = self._bully_focus_category(state)
        strategic = self._is_strategic_item(state, my_count, opp_count, bonus_gain)

        if my_count > 0:
            multiplier += 0.03 * min(my_count, 3)
        if opp_count > my_count:
            multiplier += 0.02 * min(opp_count - my_count, 2)
        if state.item.value >= 15_000_000:
            multiplier += 0.08
        elif state.item.value >= 13_000_000:
            multiplier += 0.06
        elif state.item.value >= 11_000_000:
            multiplier += 0.04
        if state.round_index <= 4:
            multiplier += 0.03
        if bully_like and strategic:
            multiplier += 0.10
        elif bully_like and not strategic:
            multiplier -= 0.02
        elif king_like and strategic:
            multiplier += 0.06
        elif king_like and not strategic:
            multiplier -= 0.04
        elif strategic:
            multiplier += 0.03
        elif contested:
            multiplier += 0.01

        multiplier = min(multiplier, 0.94)
        raw_bid = int(harvest_value * multiplier)

        if bully_like and strategic:
            raw_bid = max(raw_bid, self._aggressive_bully_bid(state) + MIN_BID_INCREMENT)
            if bully_focus == state.item.category:
                raw_bid = max(raw_bid, int(state.item.value * 1.11))
                if bonus_gain > 0:
                    raw_bid = max(raw_bid, int(state.item.value * 1.14))
        elif bully_like and not strategic:
            if state.item.value >= 8_500_000:
                raw_bid = max(raw_bid, int(state.item.value * 0.88))
            else:
                raw_bid = min(raw_bid, int(state.item.value * 0.74))
        elif king_like and not strategic:
            raw_bid = min(raw_bid, int(state.item.value * 0.76))
        elif strategic and my_count > 0:
            raw_bid += int(bonus_gain * 0.25)
        elif strategic:
            raw_bid += int(bonus_gain * 0.15)

        if state.item.value >= 14_000_000:
            raw_bid = max(raw_bid, int(state.item.value * 0.82))
        elif state.item.value >= 12_000_000:
            raw_bid = max(raw_bid, int(state.item.value * 0.78))

        if opp_count > my_count and opp_value >= my_value:
            raw_bid += MIN_BID_INCREMENT
        if bully_like and bully_focus == state.item.category and strategic:
            raw_bid += MIN_BID_INCREMENT
        if king_like and strategic and opp_count > 0 and my_count > 0:
            raw_bid += MIN_BID_INCREMENT

        cap = min(self._budget_guard(state, my_count, opp_count), self._spend_cap(state, my_count, opp_count, bonus_gain))
        return min(max(raw_bid, 0), cap)

    def _follow_up_bid(self, state: AuctionState, my_bid: int, opponent_bid: int, stage: int) -> int:
        my_count, my_value, opp_count, opp_value, harvest_value = self._harvest_value(state)
        if opponent_bid <= my_bid:
            return my_bid

        bonus_gain = harvest_value - state.item.value
        contested = self._is_contested(my_count, opp_count)
        bully_like = self._bullyish_opponent(state)
        king_like = self._kingish_opponent(state)
        bully_focus = self._bully_focus_category(state)
        strategic = self._is_strategic_item(state, my_count, opp_count, bonus_gain)

        if bully_like and not strategic and state.item.value < 8_500_000:
            return my_bid
        if king_like and not strategic and stage < 3 and bonus_gain <= 0 and my_count == 0 and opp_count == 0:
            return my_bid

        if bully_like and strategic:
            ceiling = max(
                int(state.item.value * 1.11 + bonus_gain * 0.95),
                self._aggressive_bully_bid(state) + MIN_BID_INCREMENT,
            )
            if bully_focus == state.item.category:
                ceiling = max(ceiling, int(state.item.value * 1.12))
                if bonus_gain > 0:
                    ceiling = max(ceiling, int(state.item.value * 1.14))
            if my_count > 0:
                ceiling += int(state.item.value * 0.05)
            if opp_count > 0:
                ceiling += int(state.item.value * 0.04)
            if stage == 3:
                ceiling += int(state.item.value * 0.03)
        elif bully_like and not strategic:
            ceiling = int(state.item.value + bonus_gain * 0.50)
            if state.item.value >= 8_500_000:
                ceiling = max(ceiling, int(state.item.value * 1.11))
            if my_count > 0:
                ceiling += int(state.item.value * 0.03)
            if opp_count > 0:
                ceiling += int(state.item.value * 0.03)
        elif king_like and strategic:
            ceiling = int(state.item.value + bonus_gain * 0.82)
            if my_count > 0:
                ceiling += int(state.item.value * 0.05)
            if opp_count > 0:
                ceiling += int(state.item.value * 0.03)
            if stage == 3:
                ceiling += int(state.item.value * 0.05)
        elif strategic:
            ceiling = int(state.item.value + bonus_gain * 0.70)
            if my_count > 0:
                ceiling += int(state.item.value * 0.04)
            if opp_count > 0:
                ceiling += int(state.item.value * 0.03)
        else:
            ceiling = int(state.item.value + bonus_gain * 0.35)
            if stage == 3:
                ceiling += int(state.item.value * 0.02)
            if contested:
                ceiling += int(state.item.value * 0.02)

        ceiling = min(ceiling, self._budget_guard(state, my_count, opp_count), self._spend_cap(state, my_count, opp_count, bonus_gain))
        candidate = min(opponent_bid + MIN_BID_INCREMENT, ceiling, state.my_budget)
        if candidate <= my_bid:
            return my_bid
        return candidate

    def choose_bid_round_1(self, state: AuctionState) -> int:
        return self._opening_bid(state)

    def choose_bid_round_2(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        return self._follow_up_bid(state, my_bid, opponent_bid, stage=2)

    def choose_bid_round_3(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        return self._follow_up_bid(state, my_bid, opponent_bid, stage=3)


BOT_CLASS = CategoryHarvesterBot
