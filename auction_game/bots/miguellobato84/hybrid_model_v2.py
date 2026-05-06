from __future__ import annotations

from math import exp
from statistics import fmean

from auction_game.interfaces import AuctionBot, AuctionState, MIN_BID_INCREMENT


class HybridModelV2Bot(AuctionBot):
    def __init__(self) -> None:
        self._weights = {
            "value_norm": 0.34,
            "progress": 0.08,
            "rounds_left": -0.11,
            "budget_edge": 0.11,
            "budget_share": 0.08,
            "my_cat_count": -0.04,
            "opp_cat_count": 0.08,
            "category_pressure": 0.16,
            "category_edge": 0.08,
            "opp_vs_me": 0.12,
            "opp_pressure_rate": 0.14,
            "inventory_gap": 0.05,
            "preferred_category_edge": 0.14,
            "preferred_category_count": 0.04,
            "opponent_category_focus": 0.13,
            "opponent_style_aggression": 0.10,
            "reserve_ratio": -0.12,
            "endgame_pressure": 0.10,
        }
        self._bias = 0.18
        self._trained_rounds = 0
        self._last_features: dict[str, float] | None = None
        self._last_item_value: int | None = None
        self._opponent_bid_ratios: list[float] = []

    def _rounds_left(self, state: AuctionState) -> int:
        return max(1, state.total_rounds - state.round_index)

    def _budget_share(self, state: AuctionState) -> int:
        return max(1, state.my_budget // self._rounds_left(state))

    def _category_bonus_rate(self, item_count: int) -> float:
        raw_rate = 0.06 * max(0, item_count - 1) + 0.02 * max(0, item_count - 3)
        return min(raw_rate, 0.30)

    def _marginal_bonus_gain(self, current_count: int, current_value: int, item_value: int) -> int:
        before = int(current_value * self._category_bonus_rate(current_count))
        after = int((current_value + item_value) * self._category_bonus_rate(current_count + 1))
        return after - before

    def _category_state(self, items: tuple, category: str) -> tuple[int, int]:
        count = 0
        total_value = 0
        for item in items:
            if item.category == category:
                count += 1
                total_value += item.value
        return count, total_value

    def _category_counts(self, items: tuple) -> tuple[dict[str, int], dict[str, int]]:
        counts: dict[str, int] = {}
        values: dict[str, int] = {}
        for item in items:
            counts[item.category] = counts.get(item.category, 0) + 1
            values[item.category] = values.get(item.category, 0) + item.value
        return counts, values

    def _sigmoid(self, value: float) -> float:
        if value >= 16:
            return 1.0
        if value <= -16:
            return 0.0
        return 1.0 / (1.0 + exp(-value))

    def _opponent_style(self, state: AuctionState) -> tuple[str | None, float, float]:
        opp_counts, opp_values = self._category_counts(state.opponent_items)
        if not opp_counts:
            pressure_rate = 0.0
            if state.my_bids and state.opponent_bids:
                pressure_rate = sum(
                    1 for my, opp in zip(state.my_bids, state.opponent_bids) if opp >= my + MIN_BID_INCREMENT
                ) / len(state.my_bids)
            return None, 0.0, pressure_rate

        focus_category = max(opp_counts, key=lambda category: (opp_counts[category], opp_values[category]))
        total_items = len(state.opponent_items)
        total_value = sum(opp_values.values())
        focus_count = opp_counts[focus_category]
        focus_value = opp_values[focus_category]
        second_best = max((count for category, count in opp_counts.items() if category != focus_category), default=0)

        concentration = focus_count / max(1, total_items)
        spread = max(0, focus_count - second_best) / 3.0
        value_share = focus_value / max(1, total_value)
        focus_score = min(1.0, 0.5 * concentration + 0.3 * spread + 0.2 * value_share)

        if state.my_bids and state.opponent_bids:
            pressure_rate = sum(
                1 for my, opp in zip(state.my_bids, state.opponent_bids) if opp >= my + MIN_BID_INCREMENT
            ) / len(state.my_bids)
        else:
            pressure_rate = 0.0
        style_aggression = min(1.0, 0.55 * focus_score + 0.45 * pressure_rate)
        return focus_category, focus_score, style_aggression

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

    def _bullyish_opponent(self, state: AuctionState) -> float:
        if len(self._opponent_bid_ratios) < 2:
            return 0.0

        recent = self._opponent_bid_ratios[-3:]
        avg_ratio = sum(recent) / len(recent)
        spread = max(recent) - min(recent)
        pressure_rate = 0.0
        if state.my_bids and state.opponent_bids:
            pressure_rate = sum(
                1 for my, opp in zip(state.my_bids, state.opponent_bids) if opp >= my + MIN_BID_INCREMENT
            ) / len(state.my_bids)

        ratio_score = max(0.0, min(1.0, (avg_ratio - 0.70) / 0.20))
        consistency = max(0.0, min(1.0, (0.15 - spread) / 0.15))
        return min(1.0, 0.60 * ratio_score + 0.15 * consistency + 0.25 * pressure_rate)

    def _aggressive_bully_ceiling(self, state: AuctionState) -> int | None:
        bully_score = self._bullyish_opponent(state)
        if bully_score < 0.60:
            return None
        return min(state.opponent_budget, int(state.item.value * 1.10))

    def _clear_category_harvester(self, state: AuctionState) -> tuple[str | None, float, float]:
        focus_category, focus_score, style_aggression = self._opponent_style(state)
        if focus_category is None:
            return None, 0.0, style_aggression

        opp_counts, opp_values = self._category_counts(state.opponent_items)
        focus_count = opp_counts.get(focus_category, 0)
        total_items = len(state.opponent_items)
        if total_items == 0:
            return None, 0.0, style_aggression

        second_best = max((count for category, count in opp_counts.items() if category != focus_category), default=0)
        concentration = focus_count / total_items
        count_gap = max(0, focus_count - second_best)
        value_share = opp_values.get(focus_category, 0) / max(1, sum(opp_values.values()))
        clear_score = 0.38 * concentration + 0.34 * min(1.0, count_gap / 3.0) + 0.18 * value_share + 0.10 * style_aggression
        if clear_score < 0.75 or focus_score < 0.62:
            return None, clear_score, style_aggression
        return focus_category, clear_score, style_aggression

    def _reserve_floor(self, state: AuctionState, my_count: int) -> int:
        rounds_left = self._rounds_left(state)
        budget_share = self._budget_share(state)
        focus_category, clear_score, _ = self._clear_category_harvester(state)
        bully_score = self._bullyish_opponent(state)

        reserve = budget_share
        reserve += state.item.value // 12

        if rounds_left > 5:
            reserve += budget_share // 2
        elif rounds_left > 2:
            reserve += budget_share // 4
        else:
            reserve //= 2

        if my_count > 0:
            reserve -= min(budget_share // 4, state.item.value // 10)
        else:
            reserve += budget_share // 5

        if state.item.value >= 14_500_000:
            reserve -= min(budget_share // 5, state.item.value // 14)

        if rounds_left <= 2:
            reserve = max(0, reserve - budget_share // 3)

        if focus_category is not None and clear_score >= 0.78:
            reserve = max(0, reserve - budget_share // 2)
            if focus_category == state.item.category:
                reserve = max(0, reserve - state.item.value // 6)
                if rounds_left <= 4:
                    reserve = max(0, reserve - state.item.value // 8)

        if bully_score >= 0.60:
            reserve = max(0, reserve - budget_share // 3)

        return max(0, min(state.my_budget, reserve))

    def _spend_cap(self, state: AuctionState, bonus_gain: int, my_count: int) -> int:
        reserve = self._reserve_floor(state, my_count)
        rounds_left = self._rounds_left(state)
        bully_score = self._bullyish_opponent(state)
        bully_ceiling = self._aggressive_bully_ceiling(state)
        if bonus_gain > 0:
            reserve = max(0, reserve - min(state.item.value // 10, bonus_gain // 2))
        if rounds_left <= 2 and bonus_gain > state.item.value // 10:
            reserve = max(0, reserve - state.item.value // 8)
        cap = max(0, state.my_budget - reserve)
        if bully_ceiling is not None and (rounds_left <= 4 or bonus_gain > 0):
            cap = max(cap, bully_ceiling + MIN_BID_INCREMENT)
        return max(0, min(state.my_budget, cap))

    def _feature_vector(self, state: AuctionState) -> dict[str, float]:
        value = state.item.value
        total_budget = state.my_budget + state.opponent_budget
        rounds_left = self._rounds_left(state)
        progress = state.round_index / max(1, state.total_rounds - 1)
        my_cat_count, my_cat_value = self._category_state(state.my_items, state.item.category)
        opp_cat_count, opp_cat_value = self._category_state(state.opponent_items, state.item.category)
        my_gain = self._marginal_bonus_gain(my_cat_count, my_cat_value, value)
        opp_gain = self._marginal_bonus_gain(opp_cat_count, opp_cat_value, value)
        my_counts, my_values = self._category_counts(state.my_items)

        best_category_bonus = 0
        best_category_count = 0
        for category, count in my_counts.items():
            gain = self._marginal_bonus_gain(count, my_values[category], value)
            if gain > best_category_bonus:
                best_category_bonus = gain
                best_category_count = count

        preferred_category_edge = best_category_bonus / max(1, value)
        focus_category, clear_score, style_aggression = self._clear_category_harvester(state)
        opp_focus_current = 1.0 if focus_category == state.item.category else 0.0
        reserve_floor = self._reserve_floor(state, my_cat_count)
        reserve_ratio = reserve_floor / max(1, state.my_budget)
        endgame_pressure = max(0.0, 1.0 - (state.my_budget / max(1, self._budget_share(state) * rounds_left)))

        if state.my_bids and state.opponent_bids:
            bid_ratios = [opp / max(1, my) for my, opp in zip(state.my_bids, state.opponent_bids)]
            opp_vs_me = fmean(bid_ratios)
            pressure_rate = sum(
                1 for my, opp in zip(state.my_bids, state.opponent_bids) if opp >= my + MIN_BID_INCREMENT
            ) / len(state.my_bids)
        else:
            opp_vs_me = 1.0
            pressure_rate = 0.0

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
            "opponent_category_focus": clear_score,
            "opponent_style_aggression": style_aggression,
            "reserve_ratio": reserve_ratio,
            "endgame_pressure": endgame_pressure,
            "opp_focus_current": opp_focus_current,
        }

    def _predict_opp_ratio(self, state: AuctionState) -> float:
        features = self._feature_vector(state)
        raw = self._bias
        for name, value in features.items():
            raw += self._weights.get(name, 0.0) * value
        if features["opponent_category_focus"] >= 0.80 and features["opp_focus_current"] > 0.0:
            raw += 0.08
        if features["reserve_ratio"] < 0.65:
            raw -= 0.05
        bully_score = self._bullyish_opponent(state)
        if bully_score >= 0.55:
            raw += 0.06 + 0.04 * bully_score
        return max(0.05, min(0.95, raw))

    def _maybe_train(self, state: AuctionState) -> None:
        completed_rounds = len(state.opponent_bids)
        if completed_rounds <= self._trained_rounds:
            return
        if self._last_features is None or self._last_item_value is None:
            self._trained_rounds = completed_rounds
            return

        observed_bid = state.opponent_bids[-1]
        self._opponent_bid_ratios.append(observed_bid / max(1, self._last_item_value))
        if len(self._opponent_bid_ratios) > 8:
            self._opponent_bid_ratios = self._opponent_bid_ratios[-8:]
        target_ratio = max(0.0, min(1.0, observed_bid / max(1, self._last_item_value)))
        predicted_ratio = self._bias
        for name, value in self._last_features.items():
            predicted_ratio += self._weights.get(name, 0.0) * value
        predicted_ratio = max(0.05, min(0.95, predicted_ratio))

        error = predicted_ratio - target_ratio
        learning_rate = 0.15
        for name, value in self._last_features.items():
            updated = self._weights.get(name, 0.0) - learning_rate * error * value
            self._weights[name] = max(-1.6, min(1.6, updated))
        self._bias = max(-0.8, min(0.8, self._bias - learning_rate * error))
        self._trained_rounds = completed_rounds

    def _update_memory(self, state: AuctionState) -> None:
        self._last_features = self._feature_vector(state)
        self._last_item_value = state.item.value

    def _candidate_bids(self, state: AuctionState, minimum_bid: int, predicted_opp: int, bonus_gain: int) -> list[int]:
        value = state.item.value
        rounds_left = self._rounds_left(state)
        budget_share = self._budget_share(state)
        bully_score = self._bullyish_opponent(state)
        bully_ceiling = self._aggressive_bully_ceiling(state)

        base_ratio = min(0.88, max(0.22, predicted_opp / max(1, value) + 0.02))
        spread = 0.06
        if rounds_left <= 2:
            spread = 0.03
        elif rounds_left <= 5:
            spread = 0.045

        if bonus_gain > value // 10:
            base_ratio += 0.04
        if bonus_gain > value // 6:
            base_ratio += 0.05
        if bonus_gain <= 0 and rounds_left > 6:
            base_ratio -= 0.03

        ratios = [base_ratio - 2 * spread, base_ratio - spread, base_ratio, base_ratio + spread, base_ratio + 2 * spread]
        if bonus_gain > value // 8:
            ratios.append(base_ratio + 3 * spread)
        if rounds_left <= 3:
            ratios.append(min(0.95, base_ratio + 0.14))

        candidates = {
            minimum_bid,
            budget_share,
            predicted_opp + MIN_BID_INCREMENT,
            predicted_opp + 2 * MIN_BID_INCREMENT,
            predicted_opp + max(MIN_BID_INCREMENT, bonus_gain // 3),
            int((value + max(0, bonus_gain)) * 0.50),
            int((value + max(0, bonus_gain)) * 0.62),
        }
        for ratio in ratios:
            candidates.add(int(value * ratio))

        if bonus_gain > 0:
            candidates.add(int(value * 0.74))
            candidates.add(int(value * 0.82))
        if self._kingish_opponent(state):
            candidates.add(int(value * 0.72))
            candidates.add(int(value * 0.86))
            if bonus_gain > value // 10:
                candidates.add(min(state.my_budget, predicted_opp + 2 * MIN_BID_INCREMENT))
                candidates.add(int((value + max(0, bonus_gain)) * 0.78))
        if bully_score >= 0.55:
            candidates.add(int(value * 0.88))
            candidates.add(int(value * 0.94))
            candidates.add(int(value * 1.00))
        if bully_score >= 0.75:
            candidates.add(int(value * 1.04))
            candidates.add(int(value * 1.10))
            if rounds_left <= 4:
                candidates.add(int(value * 1.08))
                candidates.add(int(value * 1.12))
            if rounds_left <= 2 or bonus_gain > value // 12:
                candidates.add(int(value * 1.14))
        if bully_ceiling is not None:
            candidates.add(bully_ceiling + MIN_BID_INCREMENT)
            if rounds_left <= 4 or bonus_gain > value // 12:
                candidates.add(bully_ceiling + 2 * MIN_BID_INCREMENT)
        if rounds_left <= 2:
            candidates.add(int(value * 0.9))

        normalized = sorted(max(minimum_bid, min(state.my_budget, bid)) for bid in candidates)
        return normalized

    def _expected_utility(self, state: AuctionState, bid: int, predicted_opp: int, bonus_gain: int) -> float:
        value = state.item.value
        rounds_left = self._rounds_left(state)
        budget_share = self._budget_share(state)
        reserve_floor = self._reserve_floor(state, self._category_state(state.my_items, state.item.category)[0])
        reserve_ratio = reserve_floor / max(1, state.my_budget)
        gain_value = value + max(0, bonus_gain)
        bully_score = self._bullyish_opponent(state)
        margin = bid - (predicted_opp + MIN_BID_INCREMENT)
        win_scale = max(1.0, value * (0.045 + 0.01 * min(rounds_left, 5)))
        win_prob = self._sigmoid(margin / win_scale)

        category_aggression = max(0.0, bonus_gain / max(1, value))
        cash_weight = 1.00 + 0.08 * (rounds_left / max(1, state.total_rounds))
        if reserve_ratio < 0.90:
            cash_weight += (0.90 - reserve_ratio) * 0.85
        if rounds_left <= 2:
            cash_weight += 0.18
        if rounds_left <= 1:
            cash_weight += 0.22

        reserve_penalty = 0.0
        if bid > budget_share:
            reserve_penalty += (bid - budget_share) * (0.18 + 0.10 * (1.0 - reserve_ratio))
        spend_cap = self._spend_cap(state, bonus_gain, self._category_state(state.my_items, state.item.category)[0])
        if bid > spend_cap:
            reserve_penalty += (bid - spend_cap) * (0.26 + 0.08 * (1.0 - reserve_ratio))
        if rounds_left <= 2 and bid > reserve_floor:
            reserve_penalty += (bid - reserve_floor) * 0.12

        category_multiplier = 1.0 + min(0.34, category_aggression * 1.1)
        focus_category, clear_score, style_aggression = self._clear_category_harvester(state)
        if focus_category == state.item.category and clear_score >= 0.78:
            category_multiplier += 0.18
        elif clear_score >= 0.60:
            category_multiplier += 0.03
        if style_aggression >= 0.70 and clear_score >= 0.78 and bonus_gain > 0:
            category_multiplier += 0.08
        if self._kingish_opponent(state):
            category_multiplier += 0.06
            cash_weight += 0.04
        if bully_score >= 0.55:
            category_multiplier += 0.05 + 0.08 * bully_score
            cash_weight -= 0.03 * bully_score
            win_prob = min(0.995, win_prob + 0.08 * bully_score)
        if bully_score >= 0.75 and rounds_left <= 4:
            category_multiplier += 0.10
            cash_weight -= 0.02
        if bully_score >= 0.75 and rounds_left <= 2:
            category_multiplier += 0.06
            win_scale *= 0.88
        if bonus_gain <= 0 and rounds_left > 6:
            category_multiplier -= 0.04

        if rounds_left <= 2:
            category_multiplier += 0.05 * min(1.0, category_aggression + clear_score)

        return win_prob * (gain_value * category_multiplier - bid * cash_weight - reserve_penalty)

    def _choose_bid(self, state: AuctionState, minimum_bid: int) -> int:
        my_count, my_value = self._category_state(state.my_items, state.item.category)
        bonus_gain = self._marginal_bonus_gain(my_count, my_value, state.item.value)
        predicted_opp = int(state.item.value * self._predict_opp_ratio(state))
        reserve_floor = self._reserve_floor(state, my_count)
        rounds_left = self._rounds_left(state)
        bully_score = self._bullyish_opponent(state)
        bully_ceiling = self._aggressive_bully_ceiling(state)

        if state.my_budget <= reserve_floor and minimum_bid == 0:
            return 0

        if bully_ceiling is not None and state.my_budget > reserve_floor and (rounds_left <= 3 or bonus_gain > 0):
            minimum_bid = max(minimum_bid, bully_ceiling + MIN_BID_INCREMENT)
            if rounds_left <= 3 or bonus_gain > state.item.value // 12:
                minimum_bid = max(minimum_bid, bully_ceiling + 2 * MIN_BID_INCREMENT)
            if rounds_left <= 3:
                return min(state.my_budget, max(minimum_bid, bully_ceiling + MIN_BID_INCREMENT))

        candidates = self._candidate_bids(state, minimum_bid, predicted_opp, bonus_gain)
        spend_cap = self._spend_cap(state, bonus_gain, my_count)
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
        bid = self._choose_bid(state, 0)
        self._update_memory(state)
        return bid

    def choose_bid_round_2(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        self._maybe_train(state)
        minimum_bid = max(my_bid, 0)
        my_count, my_value = self._category_state(state.my_items, state.item.category)
        bonus_gain = self._marginal_bonus_gain(my_count, my_value, state.item.value)
        reserve_floor = self._reserve_floor(state, my_count)
        rounds_left = self._rounds_left(state)
        focus_category, clear_score, _ = self._clear_category_harvester(state)
        bully_score = self._bullyish_opponent(state)
        bully_ceiling = self._aggressive_bully_ceiling(state)

        if opponent_bid > my_bid and state.item.value >= 11_500_000 and state.my_budget > reserve_floor:
            minimum_bid = max(minimum_bid, opponent_bid + MIN_BID_INCREMENT)
        if focus_category == state.item.category and clear_score >= 0.78:
            minimum_bid = max(minimum_bid, opponent_bid + MIN_BID_INCREMENT)
            if bonus_gain > 0:
                minimum_bid = max(minimum_bid, int(state.item.value * 0.48))
        if self._kingish_opponent(state) and state.my_budget > reserve_floor:
            minimum_bid = max(minimum_bid, opponent_bid + MIN_BID_INCREMENT)
            if bonus_gain > 0 or state.item.value >= 12_000_000:
                minimum_bid = max(minimum_bid, int(state.item.value * 0.52))
        if bully_ceiling is not None and state.my_budget > reserve_floor and (rounds_left <= 3 or bonus_gain > 0):
            minimum_bid = max(minimum_bid, bully_ceiling + MIN_BID_INCREMENT)
            if rounds_left <= 3 or bonus_gain > state.item.value // 12:
                minimum_bid = max(minimum_bid, bully_ceiling + 2 * MIN_BID_INCREMENT)
            if rounds_left <= 3:
                minimum_bid = max(minimum_bid, bully_ceiling + MIN_BID_INCREMENT)
        if state.my_budget <= reserve_floor:
            minimum_bid = my_bid

        bid = self._choose_bid(state, minimum_bid)
        self._update_memory(state)
        return bid

    def choose_bid_round_3(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        self._maybe_train(state)
        minimum_bid = max(my_bid, 0)
        my_count, my_value = self._category_state(state.my_items, state.item.category)
        bonus_gain = self._marginal_bonus_gain(my_count, my_value, state.item.value)
        reserve_floor = self._reserve_floor(state, my_count)
        rounds_left = self._rounds_left(state)
        focus_category, clear_score, style_aggression = self._clear_category_harvester(state)
        bully_score = self._bullyish_opponent(state)
        bully_ceiling = self._aggressive_bully_ceiling(state)

        if state.item.value >= 14_000_000:
            minimum_bid = max(minimum_bid, int(state.item.value * 0.45))
        if opponent_bid > my_bid and state.my_budget > reserve_floor:
            minimum_bid = max(minimum_bid, opponent_bid + MIN_BID_INCREMENT)
        if focus_category == state.item.category and clear_score >= 0.78:
            minimum_bid = max(minimum_bid, int(state.item.value * 0.50))
            minimum_bid = max(minimum_bid, opponent_bid + MIN_BID_INCREMENT)
        if style_aggression >= 0.72 and clear_score >= 0.78 and bonus_gain > state.item.value // 12:
            minimum_bid = max(minimum_bid, opponent_bid + 2 * MIN_BID_INCREMENT)
        if self._kingish_opponent(state) and state.my_budget > reserve_floor:
            minimum_bid = max(minimum_bid, opponent_bid + MIN_BID_INCREMENT)
            if bonus_gain > 0 or state.item.value >= 12_500_000:
                minimum_bid = max(minimum_bid, int(state.item.value * 0.56))
        if bully_ceiling is not None and state.my_budget > reserve_floor and (rounds_left <= 3 or bonus_gain > 0):
            minimum_bid = max(minimum_bid, bully_ceiling + MIN_BID_INCREMENT)
            if rounds_left <= 3 or bonus_gain > state.item.value // 12:
                minimum_bid = max(minimum_bid, bully_ceiling + 2 * MIN_BID_INCREMENT)
            if rounds_left <= 3:
                minimum_bid = max(minimum_bid, bully_ceiling + MIN_BID_INCREMENT)
        if state.my_budget <= reserve_floor:
            minimum_bid = my_bid

        bid = self._choose_bid(state, minimum_bid)
        self._update_memory(state)
        return bid


BOT_CLASS = HybridModelV2Bot
