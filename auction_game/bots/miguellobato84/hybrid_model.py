from __future__ import annotations

from math import exp
from statistics import fmean

from auction_game.interfaces import AuctionBot, AuctionState, MIN_BID_INCREMENT


class HybridModelBot(AuctionBot):
    def __init__(self) -> None:
        self._weights = {
            "value_norm": 0.38,
            "progress": 0.10,
            "rounds_left": -0.05,
            "budget_edge": 0.08,
            "budget_share": 0.06,
            "my_cat_count": -0.03,
            "opp_cat_count": 0.07,
            "category_pressure": 0.12,
            "category_edge": 0.05,
            "opp_vs_me": 0.14,
            "opp_pressure_rate": 0.18,
            "inventory_gap": 0.04,
            "preferred_category_edge": 0.16,
            "preferred_category_count": 0.03,
        }
        self._bias = 0.20
        self._trained_rounds = 0
        self._last_features: dict[str, float] | None = None
        self._last_item_value: int | None = None
        self._seen_item_values: list[int] = []

    def _spend_cap(self, state: AuctionState, bonus_gain: int) -> int:
        rounds_left = self._rounds_left(state)
        budget_share = self._budget_share(state)
        reserve = budget_share
        score_gap = self._score(state.my_items, state.my_budget) - self._score(state.opponent_items, state.opponent_budget)
        if bonus_gain <= 0:
            reserve += budget_share // 2
        if rounds_left > 4:
            reserve += state.my_budget // 6
        if rounds_left > 10:
            reserve += state.my_budget // 12
        if rounds_left <= 2:
            reserve = max(0, reserve - budget_share // 3)
        pressure_mode = self._opponent_pressure_mode(state)
        if pressure_mode == "king":
            reserve = max(0, reserve - budget_share // 3)
            if rounds_left <= 5:
                reserve = max(0, reserve - budget_share // 3)
            if rounds_left <= 3:
                reserve = max(0, reserve - state.my_budget // 10)
        elif pressure_mode == "bully":
            if self._bully_strategic_press(state, bonus_gain):
                reserve = max(0, reserve - budget_share // 2)
                if rounds_left <= 4:
                    reserve = max(0, reserve - budget_share // 2)
                if rounds_left <= 2:
                    reserve = max(0, reserve - state.my_budget // 8)
            else:
                reserve += max(budget_share // 3, state.my_budget // 12)
                if rounds_left <= 6:
                    reserve += state.my_budget // 12
                if rounds_left <= 3:
                    reserve += state.my_budget // 10
            if score_gap > 0:
                reserve += min(state.my_budget // 4, max(0, score_gap) // 4)
            if score_gap < 0 and rounds_left <= 6:
                reserve = max(0, reserve - min(budget_share // 2, (-score_gap) // 6))
        return max(0, state.my_budget - reserve)

    def _rounds_left(self, state: AuctionState) -> int:
        return max(1, state.total_rounds - state.round_index)

    def _budget_share(self, state: AuctionState) -> int:
        return max(1, state.my_budget // self._rounds_left(state))

    def _category_state(self, items: tuple, category: str) -> tuple[int, int]:
        count = 0
        total_value = 0
        for item in items:
            if item.category == category:
                count += 1
                total_value += item.value
        return count, total_value

    def _category_bonus_rate(self, item_count: int) -> float:
        raw_rate = 0.06 * max(0, item_count - 1) + 0.02 * max(0, item_count - 3)
        return min(raw_rate, 0.30)

    def _marginal_bonus_gain(self, current_count: int, current_value: int, item_value: int) -> int:
        before = int(current_value * self._category_bonus_rate(current_count))
        after = int((current_value + item_value) * self._category_bonus_rate(current_count + 1))
        return after - before

    def _sigmoid(self, value: float) -> float:
        if value >= 16:
            return 1.0
        if value <= -16:
            return 0.0
        return 1.0 / (1.0 + exp(-value))

    def _kingish_opponent(self, state: AuctionState) -> bool:
        if len(state.opponent_bids) < 4 or not state.my_bids:
            return False
        bid_ratios = [opp / max(1, my) for my, opp in zip(state.my_bids, state.opponent_bids)]
        recent_ratios = bid_ratios[-4:]
        recent_advantages = [
            (opp - my) / max(1, state.item.value)
            for my, opp in zip(state.my_bids[-4:], state.opponent_bids[-4:])
        ]
        pressure_rate = sum(
            1 for my, opp in zip(state.my_bids, state.opponent_bids) if opp >= my + MIN_BID_INCREMENT
        ) / len(state.my_bids)
        return (
            pressure_rate >= 0.42
            and 0.88 <= sum(bid_ratios) / len(bid_ratios) <= 1.22
            and sum(recent_ratios) / len(recent_ratios) >= 0.92
            and sum(recent_advantages) / len(recent_advantages) >= -0.02
            and state.opponent_budget >= state.my_budget * 3 // 4
        )

    def _bullyish_opponent(self, state: AuctionState) -> bool:
        return False

    def _opponent_pressure_mode(self, state: AuctionState) -> str:
        if self._kingish_opponent(state):
            return "king"
        return "none"

    def _bully_strategic_press(self, state: AuctionState, bonus_gain: int) -> bool:
        opp_count, _ = self._category_state(state.opponent_items, state.item.category)
        rounds_left = self._rounds_left(state)
        return opp_count > 0 or bonus_gain > state.item.value // 6 or rounds_left <= 4

    def _early_bully_hint(self, state: AuctionState) -> bool:
        return False

    def _bully_override_hint(self, state: AuctionState) -> bool:
        if len(state.opponent_bids) < 2 or len(self._seen_item_values) < 2 or not state.my_bids:
            return False
        ratios = [opp / max(1, value) for opp, value in zip(state.opponent_bids, self._seen_item_values)]
        recent = ratios[-2:]
        pressure_rate = sum(
            1 for my, opp in zip(state.my_bids, state.opponent_bids) if opp >= my + MIN_BID_INCREMENT
        ) / len(state.my_bids)
        return (
            0.72 <= sum(recent) / len(recent) <= 1.15
            and recent[-1] >= 0.76
            and pressure_rate >= 0.45
            and state.opponent_budget >= state.my_budget * 3 // 5
        )

    def _bully_opening_bid(self, state: AuctionState) -> int:
        opponent_count, _ = self._category_state(state.opponent_items, state.item.category)
        if opponent_count >= 3:
            percent = 108
        elif opponent_count >= 1:
            percent = 92
        else:
            percent = 80
        ceiling = min(state.item.value * 110 // 100, state.opponent_budget)
        return min(state.item.value * percent // 100, ceiling)

    def _bully_follow_up_bid(self, state: AuctionState, our_previous_bid: int, bully_previous_bid: int) -> int:
        candidate = our_previous_bid + MIN_BID_INCREMENT
        ceiling = min(state.item.value * 110 // 100, state.opponent_budget)
        if candidate <= bully_previous_bid or candidate > ceiling:
            return bully_previous_bid
        return candidate

    def _bully_ceiling(self, state: AuctionState) -> int:
        return min(state.item.value * 110 // 100, state.opponent_budget, state.my_budget)

    def _category_bonus(self, item_count: int, total_value: int) -> int:
        return int(total_value * self._category_bonus_rate(item_count))

    def _score(self, items: tuple, budget: int) -> int:
        category_values: dict[str, tuple[int, int]] = {}
        total_value = 0
        for item in items:
            count, value = category_values.get(item.category, (0, 0))
            category_values[item.category] = (count + 1, value + item.value)
            total_value += item.value
        bonus = sum(self._category_bonus(count, value) for count, value in category_values.values())
        return total_value + bonus + budget

    def _aggressive_floor(self, state: AuctionState, bonus_gain: int) -> int:
        pressure_mode = self._opponent_pressure_mode(state)
        if pressure_mode == "none":
            return 0

        rounds_left = self._rounds_left(state)
        my_count, my_value = self._category_state(state.my_items, state.item.category)
        opp_count, _ = self._category_state(state.opponent_items, state.item.category)
        strategic_press = opp_count > 0 or bonus_gain > state.item.value // 10 or state.item.value >= 13_000_000

        if pressure_mode == "king":
            floor = 0.82 if strategic_press else 0.72
            if rounds_left <= 4:
                floor += 0.08
        else:
            floor = 0.86 if strategic_press else 0.68
            if rounds_left <= 4:
                floor += 0.08

        if my_count >= 1 and bonus_gain > 0:
            floor += 0.04
        if my_count >= 2:
            floor += 0.02
        if pressure_mode == "bully" and my_value > 0:
            floor += 0.01
        return int(state.item.value * min(1.10, floor))

    def _pressure_bid(self, state: AuctionState, minimum_bid: int, bonus_gain: int, pressure_mode: str) -> int:
        value = state.item.value
        rounds_left = self._rounds_left(state)
        my_count, my_value = self._category_state(state.my_items, state.item.category)
        opp_count, opp_value = self._category_state(state.opponent_items, state.item.category)
        score_gap = self._score(state.my_items, state.my_budget) - self._score(state.opponent_items, state.opponent_budget)

        own_gain = value + bonus_gain
        denial_gain = self._marginal_bonus_gain(opp_count, opp_value, value)
        strategic = opp_count > 0 or bonus_gain > value // 8 or value >= 13_500_000

        if pressure_mode == "king":
            base = own_gain + int(denial_gain * 0.42)
            if strategic:
                base = max(base, int(value * (0.76 if rounds_left > 4 else 0.86)))
            else:
                base = max(base, int(value * (0.56 if score_gap > 0 else 0.62)))
            if score_gap > 0 and not strategic:
                base = min(base, int(value * 0.55))
        else:
            base = own_gain + int(denial_gain * 0.30)
            if strategic:
                base = max(base, int(value * (0.72 if rounds_left > 4 else 0.82)))
            else:
                base = max(base, int(value * (0.50 if score_gap > 0 else 0.58)))
            if score_gap > 0 and not strategic:
                base = min(base, int(value * 0.52))

        ceiling = self._bully_ceiling(state) if pressure_mode == "bully" else state.my_budget
        return max(minimum_bid, min(state.my_budget, min(ceiling, int(base))))

    def _bully_direct_bid(self, state: AuctionState, minimum_bid: int, bonus_gain: int) -> int:
        value = state.item.value
        rounds_left = self._rounds_left(state)
        score_gap = self._score(state.my_items, state.my_budget) - self._score(state.opponent_items, state.opponent_budget)
        strategic = self._bully_strategic_press(state, bonus_gain)

        if not strategic and score_gap > 0 and rounds_left > 6:
            return minimum_bid

        floor = 0.84 if strategic else 0.62
        if rounds_left <= 4:
            floor += 0.08 if strategic else 0.10
        target = int(value * floor) + bonus_gain // 6
        if score_gap < 0:
            target += min(value // 8, (-score_gap) // 12)
        if strategic:
            target = max(target, minimum_bid + MIN_BID_INCREMENT)
        return max(minimum_bid, min(state.my_budget, target))

    def _feature_vector(self, state: AuctionState) -> dict[str, float]:
        value = state.item.value
        total_budget = state.my_budget + state.opponent_budget
        rounds_left = self._rounds_left(state)
        progress = state.round_index / max(1, state.total_rounds - 1)

        my_cat_count, my_cat_value = self._category_state(state.my_items, state.item.category)
        opp_cat_count, opp_cat_value = self._category_state(state.opponent_items, state.item.category)
        my_gain = self._marginal_bonus_gain(my_cat_count, my_cat_value, value)
        opp_gain = self._marginal_bonus_gain(opp_cat_count, opp_cat_value, value)

        my_counts: dict[str, int] = {}
        my_values: dict[str, int] = {}
        for item in state.my_items:
            my_counts[item.category] = my_counts.get(item.category, 0) + 1
            my_values[item.category] = my_values.get(item.category, 0) + item.value

        best_category_bonus = 0
        best_category_count = 0
        for category, count in my_counts.items():
            current_value = my_values[category]
            gain = self._marginal_bonus_gain(count, current_value, value)
            if gain > best_category_bonus:
                best_category_bonus = gain
                best_category_count = count

        preferred_category_edge = best_category_bonus / max(1, value)

        if state.my_bids and state.opponent_bids:
            bid_ratios = [opp / max(1, my) for my, opp in zip(state.my_bids, state.opponent_bids)]
            pressure_rate = sum(1 for my, opp in zip(state.my_bids, state.opponent_bids) if opp >= my + MIN_BID_INCREMENT) / len(state.my_bids)
            opp_vs_me = fmean(bid_ratios)
        else:
            pressure_rate = 0.0
            opp_vs_me = 1.0

        inventory_gap = (len(state.my_items) - len(state.opponent_items)) / max(1, state.total_rounds)

        return {
            "value_norm": value / 16_000_000,
            "progress": progress,
            "rounds_left": rounds_left / max(1, state.total_rounds),
            "budget_edge": (state.my_budget - state.opponent_budget) / max(1, total_budget),
            "budget_share": self._budget_share(state) / max(1, value),
            "my_cat_count": my_cat_count / max(1, state.total_rounds),
            "opp_cat_count": opp_cat_count / max(1, state.total_rounds),
            "category_pressure": (my_gain - max(0, opp_gain // 2)) / max(1, value),
            "category_edge": (my_gain - opp_gain) / max(1, value),
            "preferred_category_edge": preferred_category_edge,
            "preferred_category_count": best_category_count / max(1, state.total_rounds),
            "opp_vs_me": min(3.0, opp_vs_me) / 3.0,
            "opp_pressure_rate": pressure_rate,
            "inventory_gap": inventory_gap,
        }

    def _predict_opp_ratio(self, state: AuctionState) -> float:
        features = self._feature_vector(state)
        raw = self._bias
        for name, value in features.items():
            raw += self._weights[name] * value
        return max(0.05, min(0.95, raw))

    def _maybe_train(self, state: AuctionState) -> None:
        completed_rounds = len(state.opponent_bids)
        if completed_rounds <= self._trained_rounds:
            return
        if self._last_features is None or self._last_item_value is None:
            self._trained_rounds = completed_rounds
            return

        observed_bid = state.opponent_bids[-1]
        target_ratio = max(0.0, min(1.0, observed_bid / max(1, self._last_item_value)))
        predicted_ratio = self._bias
        for name, value in self._last_features.items():
            predicted_ratio += self._weights[name] * value
        predicted_ratio = max(0.05, min(0.95, predicted_ratio))

        error = predicted_ratio - target_ratio
        learning_rate = 0.18
        for name, value in self._last_features.items():
            updated = self._weights[name] - learning_rate * error * value
            self._weights[name] = max(-1.5, min(1.5, updated))
        self._bias = max(-0.8, min(0.8, self._bias - learning_rate * error))
        self._trained_rounds = completed_rounds

    def _update_memory(self, state: AuctionState) -> None:
        self._last_features = self._feature_vector(state)
        self._last_item_value = state.item.value
        self._seen_item_values.append(state.item.value)

    def _candidate_bids(self, state: AuctionState, minimum_bid: int, predicted_opp: int, bonus_gain: int) -> list[int]:
        value = state.item.value
        rounds_left = self._rounds_left(state)
        budget_share = self._budget_share(state)
        progress = state.round_index / max(1, state.total_rounds - 1)
        my_count, my_value = self._category_state(state.my_items, state.item.category)
        opp_count, _ = self._category_state(state.opponent_items, state.item.category)
        strategic_press = opp_count > 0 or bonus_gain >= MIN_BID_INCREMENT or value >= 15_000_000
        pressure_mode = self._opponent_pressure_mode(state)

        ratios = [0.28, 0.36, 0.44, 0.52, 0.60]
        if value >= 14_000_000:
            ratios.append(0.68)
        if rounds_left <= 3:
            ratios.append(0.74)
        if bonus_gain > value // 10:
            ratios.append(0.66)
        if bonus_gain > value // 7:
            ratios.append(0.78)
        if bonus_gain > value // 5:
            ratios.append(0.84)
        if pressure_mode == "king":
            ratios.extend([0.82, 0.90, 0.98, 1.04, 1.08, 1.12])
            if bonus_gain > value // 10 or opp_count > 0:
                ratios.extend([1.00, 1.06])
        elif pressure_mode == "bully":
            ratios.extend([0.88, 0.95, 1.00, 1.06, 1.11, 1.14])
            if strategic_press:
                ratios.extend([1.04, 1.10])

        candidates = {minimum_bid}
        for ratio in ratios:
            candidates.add(int(value * ratio))

        candidates.add(budget_share)
        candidates.add(int((value + max(0, bonus_gain)) * 0.55))
        candidates.add(predicted_opp + MIN_BID_INCREMENT)
        candidates.add(predicted_opp + 2 * MIN_BID_INCREMENT)
        if bonus_gain > 0:
            candidates.add(predicted_opp + max(MIN_BID_INCREMENT, bonus_gain // 3))
        if self._bullyish_opponent(state) or state.opponent_items:
            bully_opening = self._bully_opening_bid(state)
            bully_ceiling = self._bully_ceiling(state)
            candidates.add(bully_opening + MIN_BID_INCREMENT)
            candidates.add(self._bully_follow_up_bid(state, max(0, minimum_bid), bully_opening) + MIN_BID_INCREMENT)
            candidates.add(bully_ceiling + MIN_BID_INCREMENT)
        if self._kingish_opponent(state):
            candidates.add(int(value * 0.72))
            candidates.add(int(value * 0.86))
            if bonus_gain > value // 10:
                candidates.add(min(state.my_budget, predicted_opp + 2 * MIN_BID_INCREMENT))
                candidates.add(int((value + max(0, bonus_gain)) * 0.78))
        if self._bullyish_opponent(state):
            bully_strategic_press = self._bully_strategic_press(state, bonus_gain)
            if bully_strategic_press:
                candidates.add(int(value * 0.81))
                candidates.add(int(value * 0.87))
                candidates.add(int(value * 0.89))
                candidates.add(int(value * 0.95))
                candidates.add(int(value * 1.01))
                candidates.add(int(value * 1.06))
                candidates.add(int(value * 1.11))
                candidates.add(int(value * 1.12))
                candidates.add(int((value + max(0, bonus_gain)) * 0.92))
                if rounds_left <= 3:
                    candidates.add(int(value * 1.08))
            else:
                candidates.add(int(value * 0.32))
                candidates.add(int(value * 0.44))
                candidates.add(int(value * 0.56))

        if progress >= 0.5:
            candidates.add(int(value * 0.75))

        return sorted(max(minimum_bid, min(state.my_budget, bid)) for bid in candidates)

    def _expected_utility(self, state: AuctionState, bid: int, predicted_opp: int, bonus_gain: int) -> float:
        value = state.item.value
        win_scale = max(1.0, value * 0.06)
        margin = bid - (predicted_opp + MIN_BID_INCREMENT)
        win_prob = self._sigmoid(margin / win_scale)
        gain_value = value + max(0, bonus_gain)
        rounds_left = self._rounds_left(state)
        budget_share = self._budget_share(state)
        reserve_ratio = max(0.0, min(1.0, state.my_budget / max(1, budget_share * rounds_left)))
        category_aggression = max(0.0, bonus_gain / max(1, value))

        cash_weight = 1.06 + 0.14 * (rounds_left / max(1, state.total_rounds))
        if reserve_ratio < 1.0:
            cash_weight += (1.0 - reserve_ratio) * 0.65

        reserve_penalty = 0.0
        if bid > budget_share:
            reserve_penalty = (bid - budget_share) * (0.22 + 0.12 * (1.0 - reserve_ratio))
        spend_cap = self._spend_cap(state, bonus_gain)
        if bid > spend_cap:
            reserve_penalty += (bid - spend_cap) * (0.28 + 0.10 * (1.0 - reserve_ratio))

        category_multiplier = 1.0 + min(0.28, category_aggression * 0.9)
        if bonus_gain > 0 and state.item.category in {item.category for item in state.my_items}:
            category_multiplier += 0.05
        pressure_mode = self._opponent_pressure_mode(state)
        if pressure_mode == "king":
            category_multiplier += 0.10
            cash_weight = max(0.92, cash_weight - 0.02)
        if pressure_mode == "bully":
            my_count, my_value = self._category_state(state.my_items, state.item.category)
            bully_strategic_press = self._bully_strategic_press(state, bonus_gain)
            if bully_strategic_press:
                category_multiplier += 0.42
                cash_weight = max(0.76, cash_weight - (0.12 if rounds_left <= 3 else 0.08))
            else:
                category_multiplier -= 0.12
                cash_weight += 0.22

        if bonus_gain <= 0 and rounds_left > 6:
            category_multiplier -= 0.04

        if pressure_mode == "king" and rounds_left <= 4:
            category_multiplier += 0.04
        if pressure_mode == "bully" and rounds_left <= 4:
            category_multiplier += 0.05

        return win_prob * (gain_value * category_multiplier - bid * cash_weight - reserve_penalty)

    def _choose_bid(self, state: AuctionState, minimum_bid: int) -> int:
        predicted_opp = int(state.item.value * self._predict_opp_ratio(state))
        my_count, my_value = self._category_state(state.my_items, state.item.category)
        bonus_gain = self._marginal_bonus_gain(my_count, my_value, state.item.value)
        budget_share = self._budget_share(state)
        pressure_mode = self._opponent_pressure_mode(state)

        if self._bully_override_hint(state):
            return self._bully_direct_bid(state, minimum_bid, bonus_gain)

        if pressure_mode == "king":
            predicted_opp = max(predicted_opp, int(state.item.value * 0.86))
            if bonus_gain > 0 or self._category_state(state.opponent_items, state.item.category)[0] > 0:
                predicted_opp = max(predicted_opp, int(state.item.value * (0.94 if self._rounds_left(state) <= 4 else 0.90)))

        if state.my_budget <= budget_share and minimum_bid == 0:
            return 0

        candidates = self._candidate_bids(state, minimum_bid, predicted_opp, bonus_gain)
        spend_cap = self._spend_cap(state, bonus_gain)
        best_bid = minimum_bid
        best_score = 0.0
        for bid in candidates:
            if bid > spend_cap and bid != minimum_bid:
                continue
            score = self._expected_utility(state, bid, predicted_opp, bonus_gain)
            if score > best_score or (score == best_score and bid < best_bid):
                best_score = score
                best_bid = bid

        if best_score <= 0.0:
            return minimum_bid
        return best_bid

    def choose_bid_round_1(self, state: AuctionState) -> int:
        self._maybe_train(state)
        minimum_bid = 0
        bully_opening = self._bully_opening_bid(state)
        my_count, my_value = self._category_state(state.my_items, state.item.category)
        opp_count, _ = self._category_state(state.opponent_items, state.item.category)
        bonus_gain = self._marginal_bonus_gain(my_count, my_value, state.item.value)
        minimum_bid = max(minimum_bid, self._aggressive_floor(state, bonus_gain))
        if self._bullyish_opponent(state):
            minimum_bid = max(minimum_bid, int(state.item.value * 0.81))
            if self._bully_strategic_press(state, bonus_gain):
                minimum_bid = max(minimum_bid, int(state.item.value * 0.93))
        if opp_count > 0 or bonus_gain >= MIN_BID_INCREMENT or state.item.value >= 15_000_000:
            minimum_bid = max(minimum_bid, bully_opening + MIN_BID_INCREMENT)
        if state.item.value >= 13_000_000 and (opp_count > 0 or bonus_gain > 0):
            minimum_bid = max(minimum_bid, int(state.item.value * 0.96))
        bid = self._choose_bid(state, minimum_bid)
        self._update_memory(state)
        return bid

    def choose_bid_round_2(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        self._maybe_train(state)
        minimum_bid = max(my_bid, 0)
        minimum_bid = max(minimum_bid, self._aggressive_floor(state, self._marginal_bonus_gain(*self._category_state(state.my_items, state.item.category), state.item.value)))
        if opponent_bid > my_bid and state.item.value >= 11_500_000 and state.my_budget > self._budget_share(state):
            minimum_bid = max(minimum_bid, opponent_bid + MIN_BID_INCREMENT)
        if self._kingish_opponent(state) and state.my_budget > self._budget_share(state):
            minimum_bid = max(minimum_bid, opponent_bid + MIN_BID_INCREMENT)
            if state.item.value >= 12_000_000:
                minimum_bid = max(minimum_bid, int(state.item.value * 0.52))
        if self._bullyish_opponent(state) and state.item.value >= 13_500_000:
            minimum_bid = max(minimum_bid, int(state.item.value * 0.81))
        bully_follow_up = self._bully_follow_up_bid(state, my_bid, opponent_bid)
        my_count, my_value = self._category_state(state.my_items, state.item.category)
        opp_count, _ = self._category_state(state.opponent_items, state.item.category)
        bonus_gain = self._marginal_bonus_gain(my_count, my_value, state.item.value)
        if self._opponent_pressure_mode(state) == "bully" and self._bully_strategic_press(state, bonus_gain):
            if self._rounds_left(state) <= 4:
                direct = max(minimum_bid, bully_follow_up + MIN_BID_INCREMENT, self._bully_ceiling(state) + MIN_BID_INCREMENT)
                return self._clamp(min(direct, state.my_budget), state.my_budget)
        if opp_count > 0 or bonus_gain >= MIN_BID_INCREMENT or state.item.value >= 15_000_000:
            minimum_bid = max(minimum_bid, bully_follow_up + MIN_BID_INCREMENT)
        if state.item.value >= 13_000_000 and (opp_count > 0 or bonus_gain > 0):
            minimum_bid = max(minimum_bid, int(state.item.value * 1.00))
        bid = self._choose_bid(state, minimum_bid)
        self._update_memory(state)
        return bid

    def choose_bid_round_3(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        self._maybe_train(state)
        minimum_bid = max(my_bid, 0)
        minimum_bid = max(minimum_bid, self._aggressive_floor(state, self._marginal_bonus_gain(*self._category_state(state.my_items, state.item.category), state.item.value)))
        if opponent_bid > my_bid and state.my_budget > self._budget_share(state):
            minimum_bid = max(minimum_bid, opponent_bid + MIN_BID_INCREMENT)
        if state.item.value >= 14_000_000:
            minimum_bid = max(minimum_bid, int(state.item.value * 0.50))
        if self._kingish_opponent(state):
            minimum_bid = max(minimum_bid, opponent_bid + MIN_BID_INCREMENT)
            if state.item.value >= 12_500_000:
                minimum_bid = max(minimum_bid, int(state.item.value * 0.56))
        if self._bullyish_opponent(state) and state.item.value >= 13_500_000:
            minimum_bid = max(minimum_bid, int(state.item.value * 0.81))
        bully_follow_up = self._bully_follow_up_bid(state, my_bid, opponent_bid)
        my_count, my_value = self._category_state(state.my_items, state.item.category)
        opp_count, _ = self._category_state(state.opponent_items, state.item.category)
        bonus_gain = self._marginal_bonus_gain(my_count, my_value, state.item.value)
        if self._opponent_pressure_mode(state) == "bully" and self._bully_strategic_press(state, bonus_gain):
            if self._rounds_left(state) <= 4:
                direct = max(minimum_bid, bully_follow_up + MIN_BID_INCREMENT, self._bully_ceiling(state) + MIN_BID_INCREMENT)
                return self._clamp(min(direct, state.my_budget), state.my_budget)
        if opp_count > 0 or bonus_gain >= MIN_BID_INCREMENT or state.item.value >= 15_000_000:
            minimum_bid = max(minimum_bid, bully_follow_up + MIN_BID_INCREMENT)
        if state.item.value >= 13_000_000 and (opp_count > 0 or bonus_gain > 0):
            minimum_bid = max(minimum_bid, int(state.item.value * 1.03))
        bid = self._choose_bid(state, minimum_bid)
        self._update_memory(state)
        return bid


BOT_CLASS = HybridModelBot
