from auction_game.engine import DEFAULT_BUDGET, DEFAULT_ITEM_COUNT
from auction_game.interfaces import AuctionBot, AuctionItem, AuctionState, MIN_BID_INCREMENT


BASELINE_BUDGET_PER_ITEM = DEFAULT_BUDGET // DEFAULT_ITEM_COUNT
FOUR_COPY_CATEGORIES = {"ai", "web"}


def _percentage_of(value: int, percent: int) -> int:
    return value * percent // 100


def _category_count(items: tuple[AuctionItem, ...], category: str) -> int:
    return sum(1 for item in items if item.category == category)


def _category_value(items: tuple[AuctionItem, ...], category: str) -> int:
    return sum(item.value for item in items if item.category == category)


def _category_bonus_rate(item_count: int) -> float:
    raw_rate = 0.06 * max(0, item_count - 1) + 0.02 * max(0, item_count - 3)
    return min(raw_rate, 0.30)


def _marginal_bonus_if_won(state: AuctionState) -> int:
    category = state.item.category
    current_count = _category_count(state.my_items, category)
    current_value = _category_value(state.my_items, category)
    current_bonus = int(current_value * _category_bonus_rate(current_count))
    next_value = current_value + state.item.value
    next_bonus = int(next_value * _category_bonus_rate(current_count + 1))
    return next_bonus - current_bonus


def _reserve_after_current_item(state: AuctionState) -> int:
    rounds_after_current = max(0, state.total_rounds - state.round_index - 1)
    return rounds_after_current * BASELINE_BUDGET_PER_ITEM


def _spendable_budget(state: AuctionState) -> int:
    return max(0, state.my_budget - _reserve_after_current_item(state))


def _is_breakpoint_count(category: str, item_count: int) -> bool:
    if item_count == 1:
        return True
    return item_count == 3 and category in FOUR_COPY_CATEGORIES


def _is_breakpoint_category(state: AuctionState) -> bool:
    my_count = _category_count(state.my_items, state.item.category)
    opponent_count = _category_count(state.opponent_items, state.item.category)
    return _is_breakpoint_count(state.item.category, my_count) or _is_breakpoint_count(
        state.item.category,
        opponent_count,
    )


def _estimated_bully_ceiling(state: AuctionState) -> int:
    return _percentage_of(state.item.value, 110)


def _win_cap(state: AuctionState) -> int:
    spendable_budget = _spendable_budget(state)
    if spendable_budget <= 0:
        return 0
    if _is_breakpoint_category(state):
        spendable_budget = min(state.my_budget, spendable_budget + MIN_BID_INCREMENT)

    marginal_score = state.item.value + _marginal_bonus_if_won(state)
    if not _is_breakpoint_category(state):
        strategic_cap = min(_percentage_of(state.item.value, 96), marginal_score)
    else:
        strategic_cap = marginal_score
        if _category_count(state.opponent_items, state.item.category) >= 1:
            strategic_cap = max(strategic_cap, _estimated_bully_ceiling(state) + MIN_BID_INCREMENT)
        else:
            strategic_cap = max(strategic_cap, _percentage_of(state.item.value, 72))

    return min(strategic_cap, spendable_budget, state.my_budget)


class BreakpointDenierBot(AuctionBot):
    def __init__(self) -> None:
        self._opponent_is_bully = False
        self._opponent_openings_seen = 0
        self._opponent_high_openings = 0

    def _observe_opener(self, state: AuctionState, opponent_bid: int) -> None:
        self._opponent_openings_seen += 1
        if opponent_bid >= _percentage_of(state.item.value, 78):
            self._opponent_high_openings += 1
        if self._opponent_openings_seen >= 2 and self._opponent_high_openings * 2 >= self._opponent_openings_seen:
            self._opponent_is_bully = True

    def _is_own_breakpoint(self, state: AuctionState) -> bool:
        return _is_breakpoint_count(state.item.category, _category_count(state.my_items, state.item.category))

    def _is_opponent_breakpoint(self, state: AuctionState) -> bool:
        return _is_breakpoint_count(
            state.item.category,
            _category_count(state.opponent_items, state.item.category),
        )

    def _is_bullyish_open(self, state: AuctionState, opponent_bid: int) -> bool:
        return opponent_bid >= _percentage_of(state.item.value, 78) and opponent_bid <= _percentage_of(
            state.item.value,
            112,
        )

    def _should_contest_value_open(self, state: AuctionState) -> bool:
        return (
            self._is_own_breakpoint(state)
            or self._is_opponent_breakpoint(state)
            or state.item.value >= BASELINE_BUDGET_PER_ITEM * 13 // 10
        )

    def choose_bid_round_1(self, state: AuctionState) -> int:
        if _spendable_budget(state) <= 0:
            return 0
        if _is_breakpoint_category(state):
            return min(_percentage_of(state.item.value, 72), _win_cap(state))
        return min(_percentage_of(state.item.value, 19), _win_cap(state))

    def choose_bid_round_2(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        self._observe_opener(state, opponent_bid)
        candidate_bid = opponent_bid + MIN_BID_INCREMENT
        cap = _win_cap(state)
        if candidate_bid <= my_bid or candidate_bid > cap:
            return my_bid

        if opponent_bid <= _percentage_of(state.item.value, 20):
            cheap_cap = _percentage_of(state.item.value, 45 if self._is_own_breakpoint(state) else 35)
            if candidate_bid <= cheap_cap:
                return candidate_bid
            return my_bid

        if self._is_bullyish_open(state, opponent_bid):
            if not _is_breakpoint_category(state):
                return my_bid
            return candidate_bid

        if opponent_bid > state.item.value:
            if _is_breakpoint_category(state):
                return candidate_bid
            return my_bid

        if self._should_contest_value_open(state):
            return candidate_bid
        return my_bid

    def choose_bid_round_3(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        candidate_bid = opponent_bid + MIN_BID_INCREMENT
        cap = _win_cap(state)
        if candidate_bid <= my_bid or candidate_bid > cap:
            return my_bid

        if opponent_bid <= _percentage_of(state.item.value, 20):
            cheap_cap = _percentage_of(state.item.value, 45 if self._is_own_breakpoint(state) else 35)
            if candidate_bid <= cheap_cap:
                return candidate_bid
            return my_bid

        if self._opponent_is_bully or self._is_bullyish_open(state, opponent_bid):
            if not _is_breakpoint_category(state):
                return my_bid
            return candidate_bid

        if opponent_bid > state.item.value:
            if _is_breakpoint_category(state):
                return candidate_bid
            return my_bid

        if self._should_contest_value_open(state):
            return candidate_bid
        return my_bid


BOT_CLASS = BreakpointDenierBot
