"""Cap-based auction bot following the META recipe, with adaptive snipe mode.

Default play: cap = value + own_bonus_gain + 0.45*denial_bonus_gain + step-ups.
R1 opens at 75% of cap. R2/R3 raise opp+1M up to cap when behind or tied.

Adaptive layer: if the opponent's recorded R3 ever equals exactly
`item.value * 95 // 100` (the tit_for_tat retaliation signature), we switch
to snipe mode for the rest of the match — open at 0, hold in R2, then
bid opp_R2 + 1M in R3. Tit_for_tat reads opp_R2 = 0 as peaceful and
holds at 20% V, so we win the item for ~21% V instead of paying ~95% V.
"""

from __future__ import annotations

from auction_game.interfaces import AuctionBot, AuctionItem, AuctionState, MIN_BID_INCREMENT

CATEGORIES = ("ai", "web", "brand", "cloud", "dev", "data")
DENIAL_WEIGHT = 0.45
R1_RATIO = 0.75


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

    def _remember(self, state: AuctionState) -> None:
        if len(self._items_seen) == state.round_index:
            self._items_seen.append(state.item)

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

    def _cap(self, state: AuctionState) -> int:
        item = state.item
        cat = item.category
        my_count, my_value = _category_state(state.my_items, cat)
        op_count, op_value = _category_state(state.opponent_items, cat)
        remaining = _remaining_in_category(state, cat)

        own_gain = _bonus_gain(my_count, my_value, item.value)
        denial_gain = _bonus_gain(op_count, op_value, item.value)

        cap = item.value + own_gain + int(DENIAL_WEIGHT * denial_gain)

        if my_count == 0 and remaining >= 1:
            cap += min(remaining, 3) * 400_000

        if (my_count + 1) in (3, 4):
            cap += 800_000
        if (op_count + 1) in (3, 4):
            cap += 600_000

        if remaining == 0 and (my_count >= 1 or op_count >= 2):
            cap += item.value // 12

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
        return max(0, min(int(cap * R1_RATIO), state.my_budget))

    def choose_bid_round_2(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
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
            if not self._opp_has_escalated(state):
                return my_bid
            if my_bid - opponent_bid >= 2 * MIN_BID_INCREMENT:
                return my_bid
            target = my_bid + 2 * MIN_BID_INCREMENT
        if target > cap or target > state.my_budget:
            return my_bid
        return target


BOT_CLASS = PabloMetaBot
