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


class CategoryHarvesterV2Bot(AuctionBot):
    _CATEGORY_ORDER = ("ai", "web", "brand", "cloud", "dev", "data")

    def _reset_match_state(self) -> None:
        self._opp_bid_ratios: list[float] = []

    def _record_opponent_bid(self, state: AuctionState, opponent_bid: int) -> None:
        self._opp_bid_ratios.append(opponent_bid / max(1, state.item.value))

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
        ratios = [opp / max(1, my) for my, opp in zip(state.my_bids, state.opponent_bids)]
        return sum(ratios) / len(ratios)

    def _recent_ratios(self, state: AuctionState, window: int = 4) -> tuple[float, float]:
        if not state.my_bids or not state.opponent_bids:
            return 1.0, 0.0
        pairs = list(zip(state.my_bids[-window:], state.opponent_bids[-window:]))
        ratios = [opp / max(1, my) for my, opp in pairs]
        advantages = [(opp - my) / max(1, state.item.value) for my, opp in pairs]
        return sum(ratios) / len(ratios), sum(advantages) / len(advantages)

    def _bully_signature_score(self, state: AuctionState) -> float:
        samples = self._opp_bid_ratios[-5:]
        if len(samples) < 2:
            return 0.0

        anchors = (0.80, 0.92, 1.08, 1.10)
        anchor_hits = sum(1 for ratio in samples if min(abs(ratio - anchor) for anchor in anchors) <= 0.05)
        average = sum(samples) / len(samples)
        spread = max(samples) - min(samples)
        pressure = self._history_pressure(state)

        anchor_score = anchor_hits / len(samples)
        average_score = 1.0 - min(1.0, abs(average - 0.98) / 0.30)
        spread_score = max(0.0, 0.16 - spread) / 0.16
        return min(1.0, 0.42 * pressure + 0.28 * anchor_score + 0.18 * average_score + 0.12 * spread_score)

    def _bullyish_opponent(self, state: AuctionState) -> bool:
        if len(state.opponent_bids) < 2:
            return False
        recent_ratio, recent_advantage = self._recent_ratios(state)
        signature = self._bully_signature_score(state)
        return (
            signature >= 0.46
            and 0.76 <= recent_ratio <= 1.20
            and recent_advantage >= -0.10
            and state.opponent_budget >= state.my_budget * 3 // 5
        )

    def _opponent_category_focus(self, state: AuctionState) -> tuple[str | None, float]:
        opp_counts, opp_values = _category_totals(state.opponent_items)
        if not opp_counts:
            return None, 0.0

        focus_category = max(
            opp_counts,
            key=lambda category: (
                opp_counts[category],
                opp_values[category],
            ),
        )
        total_items = len(state.opponent_items)
        total_value = sum(opp_values.values())
        focus_count = opp_counts[focus_category]
        focus_value = opp_values[focus_category]
        second_best = max(
            (count for category, count in opp_counts.items() if category != focus_category),
            default=0,
        )

        concentration = focus_count / max(1, total_items)
        spread = max(0, focus_count - second_best) / 3.0
        value_share = focus_value / max(1, total_value)
        score = 0.5 * concentration + 0.3 * spread + 0.2 * value_share
        return focus_category, min(1.0, score)

    def _bully_score(self, state: AuctionState) -> float:
        if self._bullyish_opponent(state):
            return 1.0
        opp_counts, opp_values = _category_totals(state.opponent_items)
        total_items = len(state.opponent_items)
        if total_items == 0:
            return 0.0

        focus_category = max(
            opp_counts,
            key=lambda category: (
                opp_counts[category],
                opp_values[category],
            ),
        )
        focus_count = opp_counts[focus_category]
        focus_value = opp_values[focus_category]
        concentration = focus_count / max(1, total_items)
        value_share = focus_value / max(1, sum(opp_values.values()))
        spread = 1.0 - min(1.0, 0.5 * concentration + 0.5 * value_share)

        samples = getattr(self, "_opp_bid_ratios", [])
        if samples:
            avg_ratio = sum(samples) / len(samples)
            bid_pressure = min(1.0, max(0.0, (avg_ratio - 0.65) / 0.45))
        else:
            bid_pressure = 0.0

        activity = min(1.0, total_items / 4)
        return min(1.0, 0.55 * bid_pressure + 0.30 * spread + 0.15 * activity)

    def _reserve_floor(self, state: AuctionState, my_count: int) -> int:
        rounds_left = max(1, state.total_rounds - state.round_index)
        paced_budget = max(1, state.my_budget // rounds_left)

        reserve = paced_budget
        reserve += state.item.value // 10

        if state.round_index == 0 and state.item.value >= 13_000_000:
            reserve = max(0, reserve - state.item.value // 3)
        elif rounds_left > 4:
            reserve += state.item.value // 8
        elif rounds_left > 2:
            reserve += state.item.value // 12
        else:
            reserve //= 2

        if my_count > 0:
            reserve -= min(paced_budget // 4, state.item.value // 9)
        else:
            reserve += paced_budget // 4

        if state.item.value >= 15_000_000:
            reserve -= min(paced_budget // 5, state.item.value // 12)

        bullyish = self._bullyish_opponent(state)
        if bullyish:
            reserve = max(0, reserve - state.item.value // 8)
            if my_count == 0:
                reserve = max(0, reserve - state.item.value // 12)

        return max(0, min(state.my_budget, reserve))

    def _spend_cap(self, state: AuctionState, my_count: int) -> int:
        focus_category, focus_score = self._opponent_category_focus(state)
        bullyish = self._bullyish_opponent(state)
        if focus_category is not None and focus_category == state.item.category:
            if focus_score >= 0.70:
                return state.my_budget
            if focus_score >= 0.45:
                reserve = self._reserve_floor(state, my_count)
                reserve = max(0, reserve - state.item.value // 10)
                return max(0, state.my_budget - reserve)
        reserve = self._reserve_floor(state, my_count)
        if bullyish:
            if focus_category is not None and focus_category == state.item.category:
                reserve = max(0, reserve - state.item.value // 10)
            else:
                reserve = max(0, reserve - state.item.value // 14)
        if state.round_index == 0 and state.item.value >= 13_000_000:
            reserve = max(0, reserve - state.item.value // 2)
        return max(0, state.my_budget - reserve)

    def _category_pressure(self, state: AuctionState) -> tuple[float, bool]:
        focus_category, focus_score = self._opponent_category_focus(state)
        if focus_category is None:
            return 0.0, False
        return focus_score, focus_category == state.item.category

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

    def _category_priority(self, state: AuctionState) -> float:
        category = state.item.category
        my_count, my_value, opp_count, opp_value = self._category_state(state)
        remaining = self._remaining_category_count(state, category)
        total = self._category_total_count(state.total_rounds, category)

        priority = 1.0
        priority += 0.54 * my_count
        priority += 0.24 * opp_count
        priority += 0.14 if remaining == 0 else 0.0
        priority += 0.08 if remaining == 1 else 0.0
        priority += 0.08 if total >= 4 else 0.0
        priority += 0.10 if my_value >= 24_000_000 else 0.0
        priority += 0.08 if opp_value >= 24_000_000 else 0.0
        return priority

    def _bully_denial_bid(self, state: AuctionState, my_count: int, opp_count: int, category_priority: float) -> int | None:
        bullyish = self._bullyish_opponent(state)
        if not bullyish:
            return None
        if state.round_index <= 3 and state.item.value >= 11_000_000:
            target = int(state.item.value * 1.11)
            if my_count > 0:
                target += state.item.value // 30
            if opp_count > my_count:
                target += state.item.value // 40
            return min(state.my_budget, target)
        if state.round_index > 4 and category_priority < 1.6:
            return None
        if category_priority < 1.05 and my_count == 0 and opp_count == 0:
            return None

        target = int(state.item.value * (1.11 + 0.01 * min(my_count, 2)))
        if category_priority >= 2.0:
            target += state.item.value // 20
        elif category_priority >= 1.5:
            target += state.item.value // 30
        if my_count > 0:
            target += state.item.value // 25
        if opp_count > my_count:
            target += state.item.value // 30
        if category_priority >= 1.5 and state.item.value >= 12_000_000:
            target = max(target, int(state.item.value * 1.12))
        return min(state.my_budget, target)

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
            return 0.60

        multiplier = 0.64 + 0.09 * min(my_count, 4)
        if my_count > 0:
            multiplier += 0.03 * min(max(my_count - 1, 0), 3)
        if opp_count > my_count:
            multiplier += 0.04 * min(opp_count - my_count, 3)
        return min(multiplier, 0.90)

    def _budget_guard(self, state: AuctionState, my_count: int, opp_count: int) -> int:
        rounds_left = max(1, state.total_rounds - state.round_index)
        paced_budget = state.my_budget // rounds_left
        bullyish = self._bullyish_opponent(state)

        if my_count > 0:
            paced_budget += int(state.item.value * (0.20 + 0.05 * min(my_count, 3)))
        else:
            paced_budget += int(state.item.value * 0.08)

        if state.round_index <= 4:
            if state.item.value >= 15_000_000:
                paced_budget += state.item.value // 5
            elif state.item.value >= 13_000_000:
                paced_budget += state.item.value // 7

        if state.round_index == 1 and state.item.value >= 13_000_000:
            return min(state.my_budget, max(int(state.item.value * 1.15), paced_budget))

        if opp_count > my_count:
            paced_budget += int(state.item.value * 0.04 * min(opp_count - my_count, 3))

        if bullyish:
            paced_budget += int(state.item.value * (0.25 + 0.05 * min(my_count, 3)))
            floor = int(state.item.value * (0.82 + 0.03 * min(my_count, 2)))
            return min(state.my_budget, max(floor, paced_budget))

        return min(state.my_budget, max(state.item.value // 2, paced_budget))

    def _opening_bid(self, state: AuctionState) -> int:
        my_count, my_value, opp_count, opp_value, harvest_value = self._harvest_value(state)
        multiplier = self._concentration_multiplier(my_count, opp_count)
        focus_score, matches_focus = self._category_pressure(state)
        bullyish = self._bullyish_opponent(state)
        category_priority = self._category_priority(state)
        bonus_gain = harvest_value - state.item.value

        if my_count > 0:
            multiplier += 0.03 * min(my_count, 3)
        if opp_count > my_count:
            multiplier += 0.02 * min(opp_count - my_count, 2)
        if state.item.value >= 15_000_000:
            multiplier += 0.04
        if focus_score >= 0.70 and matches_focus:
            multiplier += 0.08 + 0.02 * min(my_count, 3)
        elif focus_score >= 0.45 and matches_focus:
            multiplier += 0.04
        elif focus_score >= 0.70:
            multiplier -= 0.03

        if bullyish and not matches_focus:
            multiplier += 0.10
        elif bullyish and matches_focus:
            multiplier += 0.18 + 0.03 * min(my_count, 2)
        if bullyish and category_priority < 1.2 and my_count == 0 and opp_count == 0:
            multiplier -= 0.08
        elif bullyish and category_priority >= 2.0:
            multiplier += 0.14

        multiplier = min(multiplier, 0.94)
        raw_bid = int(harvest_value * multiplier)

        if my_count >= 2:
            raw_bid += int((harvest_value - state.item.value) * 0.35)
        elif my_count == 1:
            raw_bid += int((harvest_value - state.item.value) * 0.20)
        if state.round_index <= 4 and (my_count > 0 or opp_count > 0 or focus_score >= 0.70):
            if state.item.value >= 15_000_000:
                raw_bid = max(raw_bid, int(state.item.value * 0.90))
            elif state.item.value >= 13_000_000:
                raw_bid = max(raw_bid, int(state.item.value * 0.84))
        if state.round_index == 0 and state.item.value >= 13_000_000:
            raw_bid = max(raw_bid, int(state.item.value * 1.12))

        if focus_score >= 0.70 and matches_focus:
            raw_bid += state.item.value // 10
        if opp_count > my_count and opp_value >= my_value:
            raw_bid += 2 * state.item.value // 25

        if bullyish and not matches_focus:
            raw_bid = max(raw_bid, int(state.item.value * (0.82 + 0.05 * min(my_count, 2))))
        elif bullyish and matches_focus:
            raw_bid = max(raw_bid, int(harvest_value * 0.90))

        denial_bid = self._bully_denial_bid(state, my_count, opp_count, category_priority)
        if denial_bid is not None:
            raw_bid = max(raw_bid, denial_bid)

        cap = min(self._budget_guard(state, my_count, opp_count), self._spend_cap(state, my_count))
        return min(max(raw_bid, 0), cap)

    def _follow_up_bid(self, state: AuctionState, my_bid: int, opponent_bid: int, stage: int) -> int:
        my_count, my_value, opp_count, opp_value, harvest_value = self._harvest_value(state)
        if opponent_bid <= my_bid:
            return my_bid

        focus_score, matches_focus = self._category_pressure(state)
        bullyish = self._bullyish_opponent(state)
        category_priority = self._category_priority(state)
        bonus_gain = harvest_value - state.item.value

        if bullyish and not matches_focus:
            return my_bid
        if bullyish and category_priority < 1.2 and focus_score < 0.70 and my_count == 0 and opp_count == 0:
            return my_bid

        protection_multiplier = 0.20 + 0.06 * min(my_count, 4)
        if my_count >= 2:
            protection_multiplier += 0.06
        if opp_count >= my_count:
            protection_multiplier += 0.04 * min(opp_count - my_count + 1, 3)
        if stage == 3:
            protection_multiplier += 0.05
        if state.item.value >= 15_000_000:
            protection_multiplier += 0.05
        if focus_score >= 0.70 and matches_focus:
            protection_multiplier += 0.08
        elif focus_score >= 0.45 and matches_focus:
            protection_multiplier += 0.04
        elif focus_score >= 0.70:
            protection_multiplier -= 0.03
        if bullyish and matches_focus:
            protection_multiplier += 0.12
        if bullyish and category_priority >= 2.0:
            protection_multiplier += 0.12

        ceiling = int(state.item.value + bonus_gain * protection_multiplier)
        if my_count > 0:
            ceiling += int(state.item.value * (0.05 + 0.02 * min(my_count, 3)))
        if opp_count > my_count and opp_value >= my_value:
            ceiling += int(state.item.value * 0.04)
        if focus_score >= 0.70 and matches_focus:
            ceiling += int(state.item.value * 0.08)
        if bullyish and not matches_focus:
            ceiling = max(ceiling, int(state.item.value * (0.92 + 0.03 * min(my_count, 2))))
        elif bullyish and matches_focus:
            ceiling = max(ceiling, int(harvest_value * 0.98))

        denial_bid = self._bully_denial_bid(state, my_count, opp_count, category_priority)
        if denial_bid is not None:
            ceiling = max(ceiling, denial_bid)

        ceiling = min(ceiling, self._budget_guard(state, my_count, opp_count), self._spend_cap(state, my_count))
        candidate = min(opponent_bid + MIN_BID_INCREMENT, ceiling, state.my_budget)
        if candidate <= my_bid:
            return my_bid
        return candidate

    def choose_bid_round_1(self, state: AuctionState) -> int:
        self._reset_match_state()
        return self._opening_bid(state)

    def choose_bid_round_2(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        self._record_opponent_bid(state, opponent_bid)
        return self._follow_up_bid(state, my_bid, opponent_bid, stage=2)

    def choose_bid_round_3(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        self._record_opponent_bid(state, opponent_bid)
        return self._follow_up_bid(state, my_bid, opponent_bid, stage=3)


BOT_CLASS = CategoryHarvesterV2Bot
