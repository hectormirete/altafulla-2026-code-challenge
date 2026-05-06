from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from math import exp
from statistics import fmean

from auction_game.interfaces import AuctionBot, AuctionState, MIN_BID_INCREMENT

EXPECTED_FUTURE_VALUE = 12_000_000
LOOKAHEAD_DEPTH = 5
CATEGORIES = ("ai", "web", "brand", "cloud", "dev", "data")
CATEGORY_TO_INDEX = {category: index for index, category in enumerate(CATEGORIES)}


@dataclass(slots=True)
class SimState:
    round_index: int
    total_rounds: int
    my_budget: int
    opp_budget: int
    my_counts: list[int]
    my_values: list[int]
    opp_counts: list[int]
    opp_values: list[int]

    def clone(self) -> "SimState":
        return SimState(
            round_index=self.round_index,
            total_rounds=self.total_rounds,
            my_budget=self.my_budget,
            opp_budget=self.opp_budget,
            my_counts=self.my_counts.copy(),
            my_values=self.my_values.copy(),
            opp_counts=self.opp_counts.copy(),
            opp_values=self.opp_values.copy(),
        )


@dataclass(slots=True)
class OpponentBidModel:
    weights: list[float]
    bias: float = 0.24
    error_ema: float = 0.0
    seen_rounds: int = 0
    snapshots: dict[int, tuple[list[float], int]] = field(default_factory=dict)


class LookaheadPlannerBot(AuctionBot):
    def __init__(self) -> None:
        self._opponent_model = OpponentBidModel(
            weights=[
                0.20,  # value
                0.09,  # budget balance
                0.05,  # progress
                0.11,  # history ratio
                0.08,  # history pressure
                0.15,  # category gain
                0.08,  # opponent category gain
                0.08,  # recent opponent ratio
                0.06,  # recent advantage
                0.03,  # category share diff
                0.02,  # my category share
                0.02,  # opp category share
            ],
        )

    def _rounds_left(self, state: AuctionState) -> int:
        return max(1, state.total_rounds - state.round_index)

    def _budget_share(self, state: AuctionState) -> int:
        return max(1, state.my_budget // self._rounds_left(state))

    def _counts_and_values(self, items: tuple) -> tuple[list[int], list[int]]:
        counts = [0] * len(CATEGORIES)
        values = [0] * len(CATEGORIES)
        for item in items:
            index = CATEGORY_TO_INDEX[item.category]
            counts[index] += 1
            values[index] += item.value
        return counts, values

    def _category_bonus_rate(self, item_count: int) -> float:
        raw_rate = 0.06 * max(0, item_count - 1) + 0.02 * max(0, item_count - 3)
        return min(raw_rate, 0.30)

    def _marginal_bonus_gain(self, current_count: int, current_value: int, item_value: int) -> int:
        before = int(current_value * self._category_bonus_rate(current_count))
        after = int((current_value + item_value) * self._category_bonus_rate(current_count + 1))
        return after - before

    def _bonus_total(self, counts: list[int], values: list[int]) -> int:
        total = 0
        for count, value in zip(counts, values):
            if count:
                total += int(value * self._category_bonus_rate(count))
        return total

    def _category_summary(self, items: tuple) -> dict[str, tuple[int, int]]:
        counts = defaultdict(lambda: [0, 0])
        for item in items:
            counts[item.category][0] += 1
            counts[item.category][1] += item.value
        return {category: (count, value) for category, (count, value) in counts.items()}

    def _category_bonus(self, count: int, value: int) -> int:
        return int(value * self._category_bonus_rate(count))

    def _bonus_gain(self, count: int, value: int, item_value: int) -> int:
        return self._category_bonus(count + 1, value + item_value) - self._category_bonus(count, value)

    def _remaining_category_count(self, state: AuctionState, category: str) -> int:
        return sum(
            1
            for future_round in range(state.round_index + 1, state.total_rounds)
            if CATEGORIES[future_round % len(CATEGORIES)] == category
        )

    def _category_total_count(self, total_rounds: int, category: str) -> int:
        return sum(
            1
            for round_index in range(total_rounds)
            if CATEGORIES[round_index % len(CATEGORIES)] == category
        )

    def _score_my_state(self, sim: SimState) -> int:
        return sum(sim.my_values) + self._bonus_total(sim.my_counts, sim.my_values) + sim.my_budget

    def _state_from_auction(self, state: AuctionState) -> SimState:
        my_counts, my_values = self._counts_and_values(state.my_items)
        opp_counts, opp_values = self._counts_and_values(state.opponent_items)
        return SimState(
            round_index=state.round_index,
            total_rounds=state.total_rounds,
            my_budget=state.my_budget,
            opp_budget=state.opponent_budget,
            my_counts=my_counts,
            my_values=my_values,
            opp_counts=opp_counts,
            opp_values=opp_values,
        )

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
        return fmean(ratios)

    def _recent_ratios(self, state: AuctionState, window: int = 4) -> tuple[float, float]:
        if not state.my_bids or not state.opponent_bids:
            return 1.0, 0.0
        pairs = list(zip(state.my_bids[-window:], state.opponent_bids[-window:]))
        ratios = [opp / max(1, my) for my, opp in pairs]
        advantages = [(opp - my) / max(1, state.item.value) for my, opp in pairs]
        return fmean(ratios), fmean(advantages)

    def _style(self, state: AuctionState, category_gain: int) -> str:
        pressure = self._history_pressure(state)
        ratio = self._history_ratio(state)
        if self._bullyish_opponent(state):
            return "bully"
        if self._kingish_opponent(state, category_gain):
            return "king"
        if pressure >= 0.60 and ratio >= 0.95:
            return "copycat"
        if ratio < 0.78 and state.opponent_budget >= state.my_budget:
            return "cash"
        if category_gain > state.item.value // 8:
            return "category"
        if ratio >= 1.02 or state.opponent_budget > state.my_budget * 11 // 10:
            return "aggressive"
        return "balanced"

    def _kingish_opponent(self, state: AuctionState, category_gain: int = 0) -> bool:
        if len(state.opponent_bids) < 4:
            return False
        if self._bullyish_opponent(state):
            return False
        pressure = self._history_pressure(state)
        ratio = self._history_ratio(state)
        recent_ratio, recent_advantage = self._recent_ratios(state)
        return (
            pressure >= 0.42
            and 0.88 <= ratio <= 1.22
            and recent_ratio >= 0.90
            and recent_advantage >= -0.03
            and state.opponent_budget >= state.my_budget * 2 // 3
            and (category_gain > state.item.value // 12 or state.item.value >= 12_000_000 or self._rounds_left(state) <= 3)
        )

    def _bullyish_opponent(self, state: AuctionState) -> bool:
        if len(state.opponent_bids) < 3:
            return False
        pressure = self._history_pressure(state)
        ratio = self._history_ratio(state)
        recent_ratio, recent_advantage = self._recent_ratios(state)
        return (
            pressure >= 0.50
            and 0.80 <= ratio <= 1.15
            and recent_ratio >= 0.84
            and recent_advantage >= -0.05
            and state.opponent_budget >= state.my_budget * 2 // 3
        )

    def _aggressive_bully_bid(self, state: AuctionState) -> int:
        category_index = CATEGORY_TO_INDEX[state.item.category]
        opp_counts, _ = self._counts_and_values(state.opponent_items)
        owned_count = opp_counts[category_index]
        if owned_count >= 3:
            percent = 108
        elif owned_count >= 1:
            percent = 92
        else:
            percent = 80
        ceiling = min(int(state.item.value * 1.10), state.opponent_budget)
        return max(0, min(ceiling, int(state.item.value * percent / 100)))

    def _opponent_ratio(self, state: AuctionState, category_gain: int) -> float:
        value = state.item.value
        my_counts, my_values = self._counts_and_values(state.my_items)
        opp_counts, opp_values = self._counts_and_values(state.opponent_items)
        my_count = my_counts[CATEGORY_TO_INDEX[state.item.category]]
        my_value = my_values[CATEGORY_TO_INDEX[state.item.category]]
        opp_count = opp_counts[CATEGORY_TO_INDEX[state.item.category]]
        opp_value = opp_values[CATEGORY_TO_INDEX[state.item.category]]
        opp_category_gain = self._marginal_bonus_gain(opp_count, opp_value, value)
        style = self._style(state, category_gain)
        history_ratio = self._history_ratio(state)
        pressure = self._history_pressure(state)

        ratio = 0.26
        ratio += 0.18 * (value / 16_000_000)
        ratio += 0.10 * (state.opponent_budget / max(1, state.my_budget + state.opponent_budget))
        ratio += 0.10 * (state.round_index / max(1, state.total_rounds - 1))
        ratio += 0.11 * history_ratio
        ratio += 0.06 * pressure
        if value >= 14_000_000:
            ratio += 0.06
        if state.opponent_budget > state.my_budget:
            ratio += 0.05
        if opp_category_gain > category_gain:
            ratio += min(0.10, (opp_category_gain - category_gain) / max(1, value) * 0.85)
        if opp_count > my_count:
            ratio += 0.02 * min(3, opp_count - my_count)
        if self._bullyish_opponent(state):
            ratio += 0.08 if opp_count >= 1 else 0.03
        if style == "copycat":
            ratio += 0.03
        elif style == "cash":
            ratio -= 0.05
        elif style == "category":
            ratio += 0.04
        elif style == "aggressive":
            ratio += 0.05
        elif style == "bully":
            ratio += 0.09
        elif style == "king":
            ratio += 0.07
        return max(0.05, min(0.95, ratio))

    def _model_features(self, state: AuctionState, category_gain: int) -> list[float]:
        my_counts, my_values = self._counts_and_values(state.my_items)
        opp_counts, opp_values = self._counts_and_values(state.opponent_items)
        category_index = CATEGORY_TO_INDEX[state.item.category]
        my_count = my_counts[category_index]
        my_value = my_values[category_index]
        opp_count = opp_counts[category_index]
        opp_value = opp_values[category_index]
        opp_category_gain = self._marginal_bonus_gain(opp_count, opp_value, state.item.value)
        recent_ratio, recent_advantage = self._recent_ratios(state)
        total_budget = max(1, state.my_budget + state.opponent_budget)
        rounds_seen = max(1, state.round_index + 1)

        return [
            state.item.value / 16_000_000,
            state.opponent_budget / total_budget,
            state.round_index / max(1, state.total_rounds - 1),
            self._history_ratio(state),
            self._history_pressure(state),
            category_gain / max(1, state.item.value),
            opp_category_gain / max(1, state.item.value),
            recent_ratio,
            recent_advantage,
            (opp_count - my_count) / rounds_seen,
            my_count / rounds_seen,
            opp_count / rounds_seen,
        ]

    def _sync_opponent_model(self, state: AuctionState) -> None:
        model = self._opponent_model
        while model.seen_rounds < len(state.my_bids):
            round_index = model.seen_rounds
            snapshot = model.snapshots.pop(round_index, None)
            if snapshot is not None:
                features, value = snapshot
                target = min(1.25, max(0.0, state.opponent_bids[round_index] / max(1, value)))
                prediction = self._predict_ratio(features)
                error = target - prediction
                model.bias += 0.07 * error
                model.error_ema = 0.85 * model.error_ema + 0.15 * abs(error)
                for idx, feature in enumerate(features):
                    update = 0.07 * (error * feature - 0.015 * model.weights[idx])
                    model.weights[idx] = max(-0.5, min(0.9, model.weights[idx] + update))
            model.seen_rounds += 1

    def _remember_round_snapshot(self, state: AuctionState, category_gain: int) -> None:
        model = self._opponent_model
        if state.round_index in model.snapshots:
            return
        model.snapshots[state.round_index] = (self._model_features(state, category_gain), state.item.value)

    def _predict_ratio(self, features: list[float]) -> float:
        model = self._opponent_model
        score = model.bias
        for weight, feature in zip(model.weights, features):
            score += weight * feature
        score += max(-0.08, min(0.08, model.error_ema * 0.25))
        return max(0.05, min(1.25, score))

    def _current_value_weight(self, state: AuctionState) -> float:
        if state.item.value >= 15_000_000:
            return 0.72
        if state.item.value >= 13_500_000:
            return 0.64
        if state.item.value >= 11_500_000:
            return 0.56
        return 0.44

    def _candidate_bids(self, state: AuctionState, minimum_bid: int, category_gain: int, phase: int) -> list[int]:
        value = state.item.value
        budget_share = self._budget_share(state)
        opponent_kind = self._style(state, category_gain)
        candidates = {
            minimum_bid,
            int(value * self._current_value_weight(state)),
            int(value * 0.30),
            int(value * 0.42),
            int(value * 0.54),
            int(value * 0.66),
            budget_share,
            budget_share + MIN_BID_INCREMENT,
        }

        if category_gain > 0:
            candidates.add(int((value + category_gain) * 0.58))
            candidates.add(int((value + category_gain) * 0.70))
            candidates.add(min(state.my_budget, self._predict_opponent_bid(state, category_gain, phase) + MIN_BID_INCREMENT))
        if opponent_kind == "king" and phase == 3:
            candidates.add(int(value * 0.72))
            candidates.add(int(value * 0.84))
            king_target = self._reference_target_price(
                state,
                phase=phase,
                my_bid=state.opponent_bids[-1] if state.opponent_bids else 0,
                opponent_bid=state.my_bids[-1] if state.my_bids else 0,
            )
            if king_target > 0 and (category_gain > value // 12 or value >= 12_500_000 or self._rounds_left(state) <= 3):
                candidates.add(min(state.my_budget, king_target + MIN_BID_INCREMENT))
                candidates.add(min(state.my_budget, king_target + 2 * MIN_BID_INCREMENT))
                candidates.add(min(state.my_budget, king_target + 3 * MIN_BID_INCREMENT))
        if value >= 14_500_000:
            candidates.add(int(value * 0.76))
        if self._rounds_left(state) <= 3:
            candidates.add(int(value * 0.82))
        if state.my_budget <= budget_share * 2:
            candidates.add(minimum_bid)
            candidates.add(max(minimum_bid, budget_share // 2))

        return sorted(max(minimum_bid, min(state.my_budget, bid)) for bid in candidates)

    def _predict_opponent_bid(self, state: AuctionState, category_gain: int, phase: int) -> int:
        if self._bullyish_opponent(state):
            return self._aggressive_bully_bid(state)
        opponent_kind = self._style(state, category_gain)
        if opponent_kind == "king" and phase == 3:
            modeled = self._reference_target_price(
                state,
                phase=phase,
                my_bid=state.opponent_bids[-1] if state.opponent_bids else 0,
                opponent_bid=state.my_bids[-1] if state.my_bids else 0,
            )
            if modeled > 0:
                return min(state.opponent_budget, max(modeled, modeled + 2 * MIN_BID_INCREMENT))
        features = self._model_features(state, category_gain)
        ratio = self._predict_ratio(features)
        if state.opponent_budget < state.my_budget:
            ratio = min(ratio, 0.98)
        if state.item.value >= 14_500_000:
            ratio += 0.04
        predicted = int(state.item.value * ratio)
        return min(state.opponent_budget, max(0, predicted))

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
            if CATEGORIES[index % len(CATEGORIES)] == category
        ]
        category_average = (sum(same_category_bids) / len(same_category_bids)) if same_category_bids else average
        blended = average * 0.45 + peak * 0.20 + category_average * 0.35
        return int(min(state.opponent_budget, max(MIN_BID_INCREMENT, blended)))

    def _clamp(self, bid: int | float, budget: int) -> int:
        return max(0, min(int(bid), budget))

    def _simulate_our_future_bid(self, sim: SimState, category_index: int, value: int) -> int:
        my_count = sim.my_counts[category_index]
        my_value = sim.my_values[category_index]
        opp_count = sim.opp_counts[category_index]
        opp_value = sim.opp_values[category_index]
        gain = self._marginal_bonus_gain(my_count, my_value, value)
        opp_gain = self._marginal_bonus_gain(opp_count, opp_value, value)
        rounds_left = max(1, sim.total_rounds - sim.round_index)
        budget_share = max(1, sim.my_budget // rounds_left)

        ratio = 0.34
        ratio += 0.12 * (value / 16_000_000)
        ratio += 0.08 * min(1.0, gain / max(1, value))
        ratio += 0.04 * min(my_count, 4)
        ratio += 0.05 if rounds_left <= 3 else 0.0
        if gain > value // 8:
            ratio += 0.12
        if gain > value // 5:
            ratio += 0.08
        if opp_gain > gain:
            ratio += 0.04
        if sim.my_budget <= budget_share * 2:
            ratio -= 0.08
        if sim.my_budget <= budget_share:
            ratio -= 0.12
        if value >= 14_000_000:
            ratio += 0.06

        bid = int(value * ratio)
        if gain > 0:
            bid = max(bid, value + gain // 3)
        if gain > value // 8:
            bid = max(bid, value + gain // 2)
        if rounds_left <= 2 and value >= 13_500_000:
            bid = max(bid, int(value * 0.70))
        if opp_gain > gain and value >= 12_000_000:
            bid = max(bid, int(value * 0.55))
        return max(0, min(sim.my_budget, bid))

    def _simulate_opponent_future_bid(self, sim: SimState, category_index: int, value: int, opponent_kind: str) -> int:
        my_count = sim.my_counts[category_index]
        my_value = sim.my_values[category_index]
        opp_count = sim.opp_counts[category_index]
        opp_value = sim.opp_values[category_index]
        gain = self._marginal_bonus_gain(opp_count, opp_value, value)
        my_gain = self._marginal_bonus_gain(my_count, my_value, value)
        style = opponent_kind
        if style not in {"bully", "king"}:
            style = "balanced"
            if opp_count > my_count + 1 and gain > my_gain:
                style = "category"
            elif sim.opp_budget < sim.my_budget // 2:
                style = "cash"
            elif value >= 14_000_000 and sim.opp_budget > sim.my_budget:
                style = "aggressive"
            elif sim.opp_budget >= sim.my_budget * 2 // 3 and sim.opp_budget >= value * 2 // 3:
                if opp_count >= 3 or (opp_count >= 1 and value >= 11_000_000):
                    style = "bully"

        if style == "bully":
            percent = 108 if opp_count >= 3 else 92 if opp_count >= 1 else 80
            return max(0, min(sim.opp_budget, int(value * percent / 100)))

        if style == "king":
            ratio = 0.30
            ratio += 0.16 * (value / 16_000_000)
            ratio += 0.08 * (sim.opp_budget / max(1, sim.my_budget + sim.opp_budget))
            ratio += 0.09 * min(1.0, gain / max(1, value))
            ratio += 0.05 * (sim.round_index / max(1, sim.total_rounds - 1))
            if value >= 14_000_000:
                ratio += 0.07
            if sim.opp_budget > sim.my_budget:
                ratio += 0.06
            if gain > value // 8:
                ratio += 0.05
            if gain > value // 5:
                ratio += 0.04
            bid = int(value * ratio)
            if gain > 0:
                bid = max(bid, value + gain // 2)
            if sim.opp_budget <= value:
                bid = min(bid, sim.opp_budget)
            return max(0, min(sim.opp_budget, bid))

        ratio = 0.28
        ratio += 0.14 * (value / 16_000_000)
        ratio += 0.06 * (sim.opp_budget / max(1, sim.my_budget + sim.opp_budget))
        ratio += 0.08 * min(1.0, gain / max(1, value))
        ratio += 0.04 * (sim.round_index / max(1, sim.total_rounds - 1))
        if style == "cash":
            ratio -= 0.06
        elif style == "category":
            ratio += 0.08
        elif style == "aggressive":
            ratio += 0.10
        elif style == "king":
            ratio += 0.08
        if gain > value // 8:
            ratio += 0.05
        if gain > value // 5:
            ratio += 0.04
        bid = int(value * ratio)
        if gain > 0:
            bid = max(bid, value + gain // 2)
        if sim.opp_budget <= value:
            bid = min(bid, sim.opp_budget)
        return max(0, min(sim.opp_budget, bid))

    def _simulate_tail(self, sim: SimState, depth: int, opponent_kind: str) -> int:
        if depth <= 0 or sim.round_index >= sim.total_rounds:
            return self._score_my_state(sim)

        category_index = sim.round_index % len(CATEGORIES)
        value = EXPECTED_FUTURE_VALUE
        my_bid = self._simulate_our_future_bid(sim, category_index, value)
        opp_bid = self._simulate_opponent_future_bid(sim, category_index, value, opponent_kind)

        next_state = sim.clone()
        next_state.round_index += 1

        if my_bid > opp_bid:
            next_state.my_budget = max(0, next_state.my_budget - my_bid)
            next_state.my_counts[category_index] += 1
            next_state.my_values[category_index] += value
        elif opp_bid > my_bid:
            next_state.opp_budget = max(0, next_state.opp_budget - opp_bid)
            next_state.opp_counts[category_index] += 1
            next_state.opp_values[category_index] += value

        return self._simulate_tail(next_state, depth - 1, opponent_kind)

    def _win_probability(self, candidate_bid: int, predicted_opp: int, value: int) -> float:
        margin = candidate_bid - (predicted_opp + MIN_BID_INCREMENT)
        scale = max(1.0, value * 0.06)
        return 1.0 / (1.0 + exp(-margin / scale))

    def _rollout_value(self, state: AuctionState, candidate_bid: int) -> float:
        sim = self._state_from_auction(state)
        category_index = CATEGORY_TO_INDEX[state.item.category]
        my_count = sim.my_counts[category_index]
        my_value = sim.my_values[category_index]
        opp_count = sim.opp_counts[category_index]
        opp_value = sim.opp_values[category_index]
        category_gain = self._marginal_bonus_gain(my_count, my_value, state.item.value)
        opponent_kind = self._style(state, category_gain)
        predicted_opp = self._predict_opponent_bid(state, category_gain, phase=3 if self._rounds_left(state) <= 3 else 2)
        win_prob = self._win_probability(candidate_bid, predicted_opp, state.item.value)
        bullyish = opponent_kind == "bully"
        kingish = opponent_kind == "king"

        win_state = sim.clone()
        win_state.my_budget = max(0, win_state.my_budget - candidate_bid)
        win_state.my_counts[category_index] += 1
        win_state.my_values[category_index] += state.item.value
        win_state.round_index += 1

        lose_state = sim.clone()
        lose_state.round_index += 1
        if predicted_opp > candidate_bid:
            lose_state.opp_budget = max(0, lose_state.opp_budget - predicted_opp)
            lose_state.opp_counts[category_index] += 1
            lose_state.opp_values[category_index] += state.item.value

        current_win = self._simulate_tail(
            win_state,
            min(LOOKAHEAD_DEPTH, state.total_rounds - state.round_index - 1),
            opponent_kind,
        )
        current_lose = self._simulate_tail(
            lose_state,
            min(LOOKAHEAD_DEPTH, state.total_rounds - state.round_index - 1),
            opponent_kind,
        )
        if bullyish and category_gain > state.item.value // 10:
            current_win += int(state.item.value * 0.04)
            current_lose -= int(state.item.value * 0.02)
        if kingish and (category_gain > state.item.value // 12 or self._rounds_left(state) <= 3):
            current_win += int(state.item.value * 0.06)
            current_lose -= int(state.item.value * 0.02)
        return win_prob * current_win + (1.0 - win_prob) * current_lose

    def _choose_bid(self, state: AuctionState, minimum_bid: int, phase: int) -> int:
        category_index = CATEGORY_TO_INDEX[state.item.category]
        my_counts, my_values = self._counts_and_values(state.my_items)
        opp_counts, opp_values = self._counts_and_values(state.opponent_items)
        category_gain = self._marginal_bonus_gain(my_counts[category_index], my_values[category_index], state.item.value)
        self._sync_opponent_model(state)
        self._remember_round_snapshot(state, category_gain)

        if self._style(state, category_gain) == "king" and phase == 3:
            king_target = self._reference_target_price(
                state,
                phase=phase,
                my_bid=state.opponent_bids[-1] if state.opponent_bids else 0,
                opponent_bid=state.my_bids[-1] if state.my_bids else 0,
            )
            if king_target > 0 and (category_gain > state.item.value // 12 or state.item.value >= 12_500_000 or self._rounds_left(state) <= 3):
                minimum_bid = max(minimum_bid, min(state.my_budget, king_target + MIN_BID_INCREMENT))
        candidates = self._candidate_bids(state, minimum_bid, category_gain, phase)
        best_bid = minimum_bid
        best_score = float("-inf")
        for bid in candidates:
            score = self._rollout_value(state, bid)
            if score > best_score or (score == best_score and bid < best_bid):
                best_score = score
                best_bid = bid

        if best_score == float("-inf"):
            return minimum_bid
        return best_bid

    def choose_bid_round_1(self, state: AuctionState) -> int:
        return self._choose_bid(state, 0, phase=1)

    def choose_bid_round_2(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        minimum_bid = max(my_bid, 0)
        if opponent_bid > my_bid and self._rounds_left(state) > 3:
            minimum_bid = max(minimum_bid, opponent_bid + MIN_BID_INCREMENT)
        return self._choose_bid(state, minimum_bid, phase=2)

    def choose_bid_round_3(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        minimum_bid = max(my_bid, 0)
        if opponent_bid > my_bid:
            minimum_bid = max(minimum_bid, opponent_bid + MIN_BID_INCREMENT)
        if state.item.value >= 14_000_000:
            minimum_bid = max(minimum_bid, int(state.item.value * 0.52))
        return self._choose_bid(state, minimum_bid, phase=3)


BOT_CLASS = LookaheadPlannerBot
