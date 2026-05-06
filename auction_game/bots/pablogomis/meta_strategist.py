"""Cap-based auction bot following the META recipe, with adaptive modes.

Default play: cap = value + own_bonus_gain + 0.45*denial_bonus_gain + step-ups.
R1 opens at 75% of cap. R2/R3 raise opp+1M up to cap when behind or tied.

Adaptive layers:
- if the opponent's recorded R3 ever equals exactly
`item.value * 95 // 100` (the tit_for_tat retaliation signature), we switch
to snipe mode for the rest of the match — open at 0, hold in R2, then
bid opp_R2 + 1M in R3.
- if the opponent opens low for multiple rounds, we preserve cash by removing
speculative step-ups and opening closer to the likely clearing price.
- if the opponent opens high, we record that shape for future tuning. A tested
cap nudge is intentionally disabled because it regressed the bully matchup;
instead, we use a smaller R3 lead cushion to preserve endgame cash.
"""

from __future__ import annotations

from auction_game.interfaces import AuctionBot, AuctionItem, AuctionState, MIN_BID_INCREMENT

CATEGORIES = ("ai", "web", "brand", "cloud", "dev", "data")
DENIAL_WEIGHT = 0.45
R1_RATIO = 0.75
PASSIVE_R1_RATIO = 0.70
LOW_OPEN_MIN_RATIO = 0.25
LOW_OPEN_RATIO = 0.45
HIGH_OPEN_RATIO = 0.70
AGGRESSIVE_NUDGE = 0  # Reserved hook; non-zero values regressed aggressive_bully.


def _bonus_rate(count: int) -> float:
    return min(0.06 * max(0, count - 1) + 0.02 * max(0, count - 3), 0.30)


def _category_bonus(count: int, total_value: int) -> int:
    return int(total_value * _bonus_rate(count))


def _bonus_gain(count: int, total_value: int, item_value: int) -> int:
    return _category_bonus(count + 1, total_value + item_value) - _category_bonus(count, total_value)


def _category_state(items, category):
    count = sum(1 for it in items if it.category == category)
    value = sum(it.value for it in items if it.category == category)
    return count, value


def _remaining_in_category(state: AuctionState, category: str) -> int:
    return sum(
        1
        for r in range(state.round_index + 1, state.total_rounds)
        if CATEGORIES[r % len(CATEGORIES)] == category
    )


class PabloMetaBot(AuctionBot):
    def __init__(self) -> None:
        self._items_seen: list[AuctionItem] = []
        self._is_retaliator_flag = False
        self._low_open_samples = 0
        self._high_open_samples = 0
        self._round_2_seen: set[int] = set()
        self._mirror_flag = False

    def _remember(self, state: AuctionState) -> None:
        if len(self._items_seen) == state.round_index:
            self._items_seen.append(state.item)

    def _observe_round_2(self, state: AuctionState, opponent_bid: int) -> None:
        if state.round_index in self._round_2_seen:
            return
        self._round_2_seen.add(state.round_index)

        value = max(1, state.item.value)
        if int(value * LOW_OPEN_MIN_RATIO) <= opponent_bid <= int(value * LOW_OPEN_RATIO):
            self._low_open_samples += 1
        if opponent_bid >= int(value * HIGH_OPEN_RATIO):
            self._high_open_samples += 1

        recent_my_finals = state.my_bids[-3:]
        if opponent_bid > 0 and opponent_bid in recent_my_finals:
            self._mirror_flag = True

    def _detect_retaliator(self, state: AuctionState) -> bool:
        # Sticky: once flagged, stays flagged for the whole match.
        if self._is_retaliator_flag:
            return True
        # tit_for_tat retaliation R3 == value * 95 // 100 exactly.
        for past_item, opp_r3 in zip(self._items_seen, state.opponent_bids):
            if opp_r3 == past_item.value * 95 // 100:
                self._is_retaliator_flag = True
                return True
        return False

    def _is_passive(self) -> bool:
        return self._low_open_samples >= 2 and not self._mirror_flag

    def _is_aggressive(self) -> bool:
        return self._high_open_samples >= 2 and not self._is_passive()

    def _stable_jitter_percent(self, state: AuctionState) -> int:
        cat_weight = sum(ord(ch) for ch in state.item.category)
        my_count, _ = _category_state(state.my_items, state.item.category)
        op_count, _ = _category_state(state.opponent_items, state.item.category)
        basis = (
            state.item.value // 100_000
            + (state.round_index + 1) * 17
            + cat_weight * 3
            + my_count * 11
            + op_count * 19
        )
        # Keep the hook deterministic and visible, but do not perturb the
        # current leaderboard-tuned opening unless a mirror is detected.
        if not self._mirror_flag:
            return 100
        return 98 + basis % 5

    def _cap(self, state: AuctionState) -> int:
        item = state.item
        cat = item.category
        my_count, my_value = _category_state(state.my_items, cat)
        op_count, op_value = _category_state(state.opponent_items, cat)
        remaining = _remaining_in_category(state, cat)

        own_gain = _bonus_gain(my_count, my_value, item.value)
        denial_gain = _bonus_gain(op_count, op_value, item.value)

        cap = item.value + own_gain + int(DENIAL_WEIGHT * denial_gain)

        passive = self._is_passive()
        aggressive = self._is_aggressive()
        high_leverage = (
            (my_count + 1) in (2, 3, 4)
            or (op_count + 1) in (2, 3, 4)
            or (remaining == 0 and (my_count >= 1 or op_count >= 1))
        )

        if my_count == 0 and remaining >= 1 and not passive:
            cap += min(remaining, 3) * 400_000

        if (my_count + 1) in (3, 4) and (not passive or high_leverage):
            cap += 800_000
        if (op_count + 1) in (3, 4) and (not passive or high_leverage):
            cap += 600_000

        if remaining == 0 and (my_count >= 1 or op_count >= 2) and not passive:
            cap += item.value // 12

        if aggressive and high_leverage:
            cap += AGGRESSIVE_NUDGE
        if passive:
            cap = min(cap, max(item.value, item.value + own_gain))

        rounds_left = max(1, state.total_rounds - state.round_index)
        per_round = state.my_budget / rounds_left
        late_game = rounds_left <= 5
        soft_cap = int(per_round * (1.8 if late_game else 1.5))
        budget_cap = max(soft_cap, int(item.value * 1.3))
        cap = min(cap, budget_cap, state.my_budget)
        return max(0, cap)

    def _opp_has_escalated(self, state: AuctionState) -> bool:
        return any(o > m for o, m in zip(state.opponent_bids, state.my_bids))

    def choose_bid_round_1(self, state: AuctionState) -> int:
        self._remember(state)
        if self._detect_retaliator(state):
            return 0
        cap = self._cap(state)
        ratio = PASSIVE_R1_RATIO if self._is_passive() else R1_RATIO
        jitter = self._stable_jitter_percent(state)
        if self._is_passive():
            jitter = max(98, min(102, jitter))
        opening = int(cap * ratio * jitter / 100)
        return max(0, min(opening, state.my_budget))

    def choose_bid_round_2(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        self._observe_round_2(state, opponent_bid)
        if self._detect_retaliator(state):
            return my_bid
        if opponent_bid <= my_bid:
            return my_bid
        cap = self._cap(state)
        target = opponent_bid + MIN_BID_INCREMENT
        if target > cap or target > state.my_budget:
            return my_bid
        return target

    def choose_bid_round_3(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        if self._detect_retaliator(state):
            target = opponent_bid + MIN_BID_INCREMENT
            if target > state.my_budget:
                return my_bid
            return max(my_bid, target)
        cap = self._cap(state)
        if opponent_bid > my_bid:
            target = opponent_bid + MIN_BID_INCREMENT
        elif opponent_bid == my_bid:
            target = my_bid + MIN_BID_INCREMENT
        else:
            if self._is_passive():
                if my_bid >= state.item.value:
                    return my_bid
                target = my_bid + 2 * MIN_BID_INCREMENT
            elif self._is_aggressive():
                target = my_bid + MIN_BID_INCREMENT
            elif not self._opp_has_escalated(state):
                return my_bid
            elif my_bid - opponent_bid >= 2 * MIN_BID_INCREMENT:
                return my_bid
            else:
                target = my_bid + 2 * MIN_BID_INCREMENT
        if target > cap or target > state.my_budget:
            return my_bid
        return target


BOT_CLASS = PabloMetaBot
