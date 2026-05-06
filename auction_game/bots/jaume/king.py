from __future__ import annotations

from collections import defaultdict

from auction_game.interfaces import AuctionBot, AuctionItem, AuctionState, MIN_BID_INCREMENT


class Codex5Bot(AuctionBot):
    _CATEGORY_ORDER = ("ai", "web", "brand", "cloud", "dev", "data")

    def __init__(self) -> None:
        self._seen_items: list[AuctionItem] = []
        self._trap_round: int | None = None

    def choose_bid_round_1(self, state: AuctionState) -> int:
        self._remember_item(state)
        self._trap_round = None
        target = self._target_price(state, phase=1, my_bid=0, opponent_bid=0)
        if target <= 0:
            return 0

        trap = self._trap_opener(state, target)
        if trap is not None:
            self._trap_round = state.round_index
            return trap

        market = self._estimated_market_price(state)
        priority = self._category_priority(state)
        style = self._opponent_style(state)

        opener_ratio = 0.80
        if style["passive"]:
            opener_ratio = 0.70
        elif style["mirror"]:
            opener_ratio = 0.84
        opener = min(target, max(MIN_BID_INCREMENT, int(market * opener_ratio)))
        if priority >= 2.35:
            opener = min(target, max(opener, int(target * (0.57 if style["passive"] else 0.60))))
        if style["chaser"] and state.item.value <= 10_500_000 and priority < 1.7:
            opener = min(target, max(opener, int(state.item.value * 1.04)))
        if style["tight"] and priority >= 2.0:
            opener = min(target, max(opener, int(target * 0.62)))
        return self._clamp(opener, state.my_budget)

    def choose_bid_round_2(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        return self._respond(state, my_bid, opponent_bid, phase=2)

    def choose_bid_round_3(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        return self._respond(state, my_bid, opponent_bid, phase=3)

    def _respond(self, state: AuctionState, my_bid: int, opponent_bid: int, *, phase: int) -> int:
        if self._trap_round == state.round_index and opponent_bid > my_bid:
            return my_bid

        target = self._target_price(state, phase=phase, my_bid=my_bid, opponent_bid=opponent_bid)
        if target <= my_bid or opponent_bid >= target:
            return my_bid

        snipe_bid = self._modeled_snipe_bid(state, phase=phase, my_bid=my_bid, opponent_bid=opponent_bid, target=target)
        if snipe_bid is not None:
            return snipe_bid

        if phase == 3 and opponent_bid == my_bid:
            tie_break = opponent_bid + self._tie_break_increment(state, target)
            return self._clamp(min(target, tie_break), state.my_budget)
        if opponent_bid >= my_bid:
            return self._clamp(min(target, opponent_bid + MIN_BID_INCREMENT), state.my_budget)
        if phase == 3 and self._opponent_style(state)["passive"]:
            return my_bid
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
        priority = self._category_priority(state)
        style = self._opponent_style(state)

        urgency = 1.0
        if remaining_same_category == 0:
            urgency += 0.42
        elif remaining_same_category == 1:
            urgency += 0.23
        if category_total == 4:
            urgency += 0.10
        if my_count >= 2:
            urgency += 0.18
        if opp_count >= 2:
            urgency += 0.19

        market_price = self._estimated_market_price(state)
        strategic_value = own_gain * urgency + deny_gain * self._denial_weight(state, style)
        strategic_value += self._future_synergy(state, my_count, my_value, remaining_same_category)
        pressure_adjusted = strategic_value - self._future_commitment_tax(state, category)
        pressure_adjusted = max(pressure_adjusted, market_price * (1.08 if phase == 3 else 1.00))

        score_gap = self._score(state.my_items, state.my_budget) - self._score(state.opponent_items, state.opponent_budget)
        rounds_after = max(0, rounds_left - 1)
        if score_gap < 0:
            pressure_adjusted += min(state.item.value * 0.22, (-score_gap) / max(2, rounds_after + 2) * 0.34)
        elif score_gap > 18_000_000 and rounds_after > 2:
            pressure_adjusted *= 0.88 if style["passive"] else 0.93

        if opponent_bid > 0:
            overpay_penalty = max(0, opponent_bid - own_gain) * self._overpay_penalty(style, phase)
            pressure_adjusted -= overpay_penalty

        if priority < 1.0:
            pressure_adjusted *= 0.70
        elif priority < 1.8:
            pressure_adjusted *= 0.94 if style["passive"] else 0.97
        elif priority > 2.6:
            pressure_adjusted *= 1.16

        if style["chaser"] and state.item.value <= 10_500_000 and priority < 1.7:
            pressure_adjusted *= 0.80
        if style["tight"] and priority >= 2.0:
            pressure_adjusted *= 1.04
        if style["passive"] and my_count == 0 and remaining_same_category > 0:
            pressure_adjusted *= 0.88
        if remaining_same_category == 0 and my_count >= 1:
            pressure_adjusted += state.item.value * 0.08
        elif remaining_same_category == 1 and my_count >= 1:
            pressure_adjusted += state.item.value * 0.04

        ev_cap = own_gain + int(deny_gain * self._denial_weight(state, style)) + self._future_synergy(
            state,
            my_count,
            my_value,
            remaining_same_category,
        )
        if score_gap < 0 or remaining_same_category <= 1 or opp_count >= 2:
            ev_cap += min(6_000_000, max(0, -score_gap) // max(2, rounds_left))
        if style["passive"] and score_gap >= -4_000_000:
            pressure_adjusted = min(pressure_adjusted, ev_cap + 1_000_000)

        budget_cap = self._budget_cap(state, phase=phase, priority=priority, rounds_left=rounds_left, style=style)
        target = int(min(pressure_adjusted, budget_cap))

        if phase == 1 and target > 0:
            target = min(target, max(market_price + MIN_BID_INCREMENT, int(target * 0.91)))

        if my_bid > target:
            return my_bid
        return self._clamp(target, state.my_budget)

    def _modeled_snipe_bid(
        self,
        state: AuctionState,
        *,
        phase: int,
        my_bid: int,
        opponent_bid: int,
        target: int,
    ) -> int | None:
        if phase != 3:
            return None

        modeled = self._reference_target_price(state, phase=phase, my_bid=opponent_bid, opponent_bid=my_bid)
        candidate = modeled + MIN_BID_INCREMENT
        if candidate <= my_bid or candidate > target or candidate > state.my_budget:
            return None
        if modeled < opponent_bid:
            return None

        category = state.item.category
        my_count, my_value = self._category_summary(state.my_items).get(category, (0, 0))
        opp_count, opp_value = self._category_summary(state.opponent_items).get(category, (0, 0))
        remaining = self._remaining_category_count(state, category)
        own_gain = state.item.value + self._bonus_gain(my_count, my_value, state.item.value)
        deny_gain = self._denial_gain(opp_count, opp_value, state.item.value)
        score_gap = self._score(state.my_items, state.my_budget) - self._score(state.opponent_items, state.opponent_budget)

        leverage = remaining <= 1 or my_count >= 1 or opp_count >= 2 or score_gap < 0
        if not leverage:
            return None
        net = own_gain + self._future_synergy(state, my_count, my_value, remaining) + int(deny_gain * 0.40) - candidate
        if score_gap < 0:
            net += min(4_500_000, -score_gap // max(2, state.total_rounds - state.round_index))
        if self._opponent_style(state)["passive"]:
            net -= 1_500_000
        if net < 900_000:
            return None
        return self._clamp(candidate, state.my_budget)

    def _trap_opener(self, state: AuctionState, target: int) -> int | None:
        style = self._opponent_style(state)
        if state.round_index < 4 or not style["chaser"]:
            return None

        category = state.item.category
        my_count, _ = self._category_summary(state.my_items).get(category, (0, 0))
        opp_count, _ = self._category_summary(state.opponent_items).get(category, (0, 0))
        remaining = self._remaining_category_count(state, category)
        priority = self._category_priority(state)
        if priority >= 1.65 or remaining == 0 or state.item.value > 10_250_000:
            return None
        if opp_count < my_count and my_count > 0:
            return None

        opener = min(target, int(state.item.value * 1.04))
        if opener + MIN_BID_INCREMENT > state.my_budget:
            return None
        if opener < MIN_BID_INCREMENT:
            return None
        return self._clamp(opener, state.my_budget)

    def _tie_break_increment(self, state: AuctionState, target: int) -> int:
        style = self._opponent_style(state)
        if style["passive"]:
            return MIN_BID_INCREMENT
        category = state.item.category
        my_count, _ = self._category_summary(state.my_items).get(category, (0, 0))
        opp_count, _ = self._category_summary(state.opponent_items).get(category, (0, 0))
        if target >= state.item.value * 1.4 or my_count >= 1 or opp_count >= 2:
            return 2 * MIN_BID_INCREMENT
        return MIN_BID_INCREMENT

    def _denial_weight(self, state: AuctionState, style: dict[str, bool]) -> float:
        if style["passive"]:
            return 0.42
        if style["chaser"]:
            return 0.35
        score_gap = self._score(state.my_items, state.my_budget) - self._score(state.opponent_items, state.opponent_budget)
        if score_gap < 0:
            return 0.58
        return 0.50

    def _overpay_penalty(self, style: dict[str, bool], phase: int) -> float:
        if style["chaser"]:
            return 0.42
        if style["passive"]:
            return 0.40 if phase == 3 else 0.32
        if style["overpays"]:
            return 0.36
        return 0.27

    def _future_synergy(self, state: AuctionState, count: int, value: int, remaining: int) -> int:
        if remaining <= 0:
            return 0
        current_path = self._category_bonus(count, value + remaining * 12_000_000)
        upgraded_path = self._category_bonus(count + 1, value + state.item.value + remaining * 12_000_000)
        immediate_gain = self._bonus_gain(count, value, state.item.value)
        return max(0, int((upgraded_path - current_path - immediate_gain) * 0.35))

    def _category_priority(self, state: AuctionState) -> float:
        category = state.item.category
        my_count, my_value = self._category_summary(state.my_items).get(category, (0, 0))
        opp_count, opp_value = self._category_summary(state.opponent_items).get(category, (0, 0))
        remaining = self._remaining_category_count(state, category)

        priority = 1.0
        priority += 0.58 * my_count
        priority += 0.27 * opp_count
        priority += 0.20 if remaining == 0 else 0.0
        priority += 0.11 if remaining == 1 else 0.0
        priority += 0.12 if my_value >= 24_000_000 else 0.0
        priority += 0.11 if opp_value >= 24_000_000 else 0.0
        return priority

    def _denial_gain(self, opp_count: int, opp_value: int, item_value: int) -> int:
        next_bonus = self._category_bonus(opp_count + 1, opp_value + item_value)
        current_bonus = self._category_bonus(opp_count, opp_value)
        blocked_bonus = next_bonus - current_bonus
        denial_weight = 0.54 + 0.13 * max(0, opp_count - 1)
        return int(item_value * 0.34 + blocked_bonus * denial_weight)

    def _future_commitment_tax(self, state: AuctionState, category: str) -> float:
        remaining = self._remaining_category_count(state, category)
        if remaining == 0:
            return 0.0
        avg_future_budget = state.my_budget / max(1, state.total_rounds - state.round_index)
        return avg_future_budget * 0.041 * remaining

    def _budget_cap(
        self,
        state: AuctionState,
        *,
        phase: int,
        priority: float,
        rounds_left: int,
        style: dict[str, bool],
    ) -> int:
        baseline = state.my_budget / max(1, rounds_left)
        reserve_factor = 0.40 if priority >= 2.4 else 0.44
        if style["passive"]:
            reserve_factor += 0.03
        reserve_per_round = max(4_000_000, int(baseline * reserve_factor))
        reserve = max(0, rounds_left - 1) * reserve_per_round
        available = max(0, state.my_budget - reserve)

        multiplier = 1.52 + min(priority, 3.1) * 0.48
        if phase == 3:
            multiplier += 0.22
        if style["passive"]:
            multiplier -= 0.10

        soft_cap = int(baseline * multiplier)
        hard_cap = int(state.item.value * (1.72 if priority >= 2.5 else 1.34))
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
        blended = average * 0.42 + peak * 0.18 + category_average * 0.40
        style = self._opponent_style(state)
        if style["passive"]:
            blended *= 0.86
        elif style["tight"]:
            blended *= 0.91
        elif style["overpays"]:
            blended *= 0.95
        return int(min(state.my_budget, max(MIN_BID_INCREMENT, blended)))

    def _opponent_style(self, state: AuctionState) -> dict[str, bool]:
        empty = {"chaser": False, "overpays": False, "tight": False, "passive": False, "mirror": False}
        if len(state.opponent_bids) < 3 or len(self._seen_items) < len(state.opponent_bids):
            return empty

        ratios: list[float] = []
        low_value_overpays = 0
        low_value_seen = 0
        ties = 0
        for index, (item, bid) in enumerate(zip(self._seen_items[: len(state.opponent_bids)], state.opponent_bids)):
            if item.value > 0:
                ratios.append(bid / item.value)
            if index < len(state.my_bids) and abs(state.my_bids[index] - bid) <= MIN_BID_INCREMENT:
                ties += 1
            if item.value <= 10_500_000:
                low_value_seen += 1
                if bid >= item.value + MIN_BID_INCREMENT:
                    low_value_overpays += 1

        if not ratios:
            return empty

        avg_ratio = sum(ratios) / len(ratios)
        recent_ratio = sum(ratios[-3:]) / min(3, len(ratios))
        overpays = avg_ratio >= 1.12 or low_value_overpays >= 2
        tight = avg_ratio <= 0.72 and recent_ratio <= 0.84
        passive = avg_ratio <= 0.90 and recent_ratio <= 0.92 and state.opponent_budget >= state.my_budget + 12_000_000
        mirror = ties >= max(2, len(state.opponent_bids) // 3) and 0.90 <= avg_ratio <= 1.20
        chaser = overpays and low_value_seen >= 2
        return {"chaser": chaser, "overpays": overpays, "tight": tight, "passive": passive, "mirror": mirror}

    def _reference_target_price(self, state: AuctionState, *, phase: int, my_bid: int, opponent_bid: int) -> int:
        rounds_left = state.total_rounds - state.round_index
        if rounds_left <= 0 or state.opponent_budget <= 0:
            return 0

        category = state.item.category
        my_count, my_value = self._category_summary(state.opponent_items).get(category, (0, 0))
        opp_count, opp_value = self._category_summary(state.my_items).get(category, (0, 0))
        remaining_same_category = self._remaining_category_count(state, category)
        category_total = self._category_total_count(state.total_rounds, category)

        own_gain = state.item.value + self._bonus_gain(my_count, my_value, state.item.value)
        deny_gain = self._reference_denial_gain(opp_count, opp_value, state.item.value)
        priority = self._reference_priority(my_count, my_value, opp_count, opp_value, remaining_same_category)

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

        market_price = self._reference_market_price(state, category)
        value_ceiling = (own_gain + deny_gain) * urgency - self._reference_future_tax(
            state.opponent_budget,
            rounds_left,
            remaining_same_category,
        )
        pressure_adjusted = max(value_ceiling, market_price * (1.10 if phase == 3 else 1.02))

        if opponent_bid > 0:
            pressure_adjusted -= max(0, opponent_bid - own_gain) * 0.30

        if priority < 1.0:
            pressure_adjusted *= 0.72
        elif priority < 1.8:
            pressure_adjusted *= 0.94
        elif priority > 2.6:
            pressure_adjusted *= 1.14

        budget_cap = self._reference_budget_cap(
            state.opponent_budget,
            phase=phase,
            priority=priority,
            rounds_left=rounds_left,
            item_value=state.item.value,
        )
        target = int(min(pressure_adjusted, budget_cap))
        if phase == 1 and target > 0:
            target = min(target, max(market_price + MIN_BID_INCREMENT, int(target * 0.92)))
        if my_bid > target:
            return my_bid
        return self._clamp(target, state.opponent_budget)

    def _reference_priority(
        self,
        my_count: int,
        my_value: int,
        opp_count: int,
        opp_value: int,
        remaining: int,
    ) -> float:
        priority = 1.0
        priority += 0.55 * my_count
        priority += 0.25 * opp_count
        priority += 0.18 if remaining == 0 else 0.0
        priority += 0.10 if remaining == 1 else 0.0
        priority += 0.12 if my_value >= 24_000_000 else 0.0
        priority += 0.10 if opp_value >= 24_000_000 else 0.0
        return priority

    def _reference_denial_gain(self, opp_count: int, opp_value: int, item_value: int) -> int:
        next_bonus = self._category_bonus(opp_count + 1, opp_value + item_value)
        current_bonus = self._category_bonus(opp_count, opp_value)
        blocked_bonus = next_bonus - current_bonus
        denial_weight = 0.52 + 0.12 * max(0, opp_count - 1)
        return int(item_value * 0.35 + blocked_bonus * denial_weight)

    def _reference_future_tax(self, budget: int, rounds_left: int, remaining: int) -> float:
        if remaining == 0:
            return 0.0
        avg_future_budget = budget / max(1, rounds_left)
        return avg_future_budget * 0.04 * remaining

    def _reference_budget_cap(
        self,
        budget: int,
        *,
        phase: int,
        priority: float,
        rounds_left: int,
        item_value: int,
    ) -> int:
        baseline = budget / max(1, rounds_left)
        reserve_per_round = max(4_000_000, int(baseline * 0.42))
        reserve = max(0, rounds_left - 1) * reserve_per_round
        available = max(0, budget - reserve)

        multiplier = 1.55 + min(priority, 3.0) * 0.48
        if phase == 3:
            multiplier += 0.24

        soft_cap = int(baseline * multiplier)
        hard_cap = int(item_value * (1.70 if priority >= 2.5 else 1.35))
        return max(MIN_BID_INCREMENT, min(budget, max(soft_cap, min(hard_cap, available))))

    def _reference_market_price(self, state: AuctionState, category: str) -> int:
        if not state.my_bids:
            return min(
                state.item.value,
                max(MIN_BID_INCREMENT, state.opponent_budget // max(1, state.total_rounds - state.round_index)),
            )
        recent = list(state.my_bids[-4:])
        average = sum(recent) / len(recent)
        peak = max(recent)
        same_category_bids = [
            bid
            for index, bid in enumerate(state.my_bids)
            if self._CATEGORY_ORDER[index % len(self._CATEGORY_ORDER)] == category
        ]
        category_average = (sum(same_category_bids) / len(same_category_bids)) if same_category_bids else average
        blended = average * 0.45 + peak * 0.20 + category_average * 0.35
        return int(min(state.opponent_budget, max(MIN_BID_INCREMENT, blended)))

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

    def _score(self, items: tuple[AuctionItem, ...], budget: int) -> int:
        item_value = sum(item.value for item in items)
        summary = self._category_summary(items)
        bonus = sum(self._category_bonus(count, value) for count, value in summary.values())
        return item_value + bonus + budget

    def _remember_item(self, state: AuctionState) -> None:
        if state.round_index == len(self._seen_items):
            self._seen_items.append(state.item)

    def _clamp(self, bid: int | float, budget: int) -> int:
        return max(0, min(int(bid), budget))


BOT_CLASS = Codex5Bot
