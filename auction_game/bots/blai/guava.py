from __future__ import annotations

from auction_game import AuctionBot, AuctionItem, AuctionState, MIN_BID_INCREMENT

AVG_ITEM = 12_000_000
CATS = ("ai", "web", "brand", "cloud", "dev", "data")


def bonus_rate(cnt: int) -> float:
    raw = 0.06 * max(0, cnt - 1) + 0.02 * max(0, cnt - 3)
    return min(raw, 0.30)


def cat_info(items: tuple[AuctionItem, ...], cat: str) -> tuple[int, int]:
    count = 0
    value = 0
    for item in items:
        if item.category == cat:
            count += 1
            value += item.value
    return count, value


def cat_bonus(cnt: int, value: int) -> int:
    return int(value * bonus_rate(cnt))


def bonus_gain(cnt: int, value: int, item_value: int) -> int:
    return cat_bonus(cnt + 1, value + item_value) - cat_bonus(cnt, value)


def left_in_cat(state: AuctionState) -> int:
    cat_index = CATS.index(state.item.category)
    return sum(1 for idx in range(state.round_index + 1, state.total_rounds) if idx % len(CATS) == cat_index)


class GuavaBot(AuctionBot):
    def __init__(self) -> None:
        self._seen: list[AuctionItem] = []

    def choose_bid_round_1(self, state: AuctionState) -> int:
        self._remember(state)
        reserve = self._reserve(state, phase=1)
        if reserve <= 0:
            return 0
        bid = reserve * self._open_pct(state) // 100
        return min(max(0, bid), reserve, state.my_budget)

    def choose_bid_round_2(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        return self._follow(state, my_bid, opponent_bid, phase=2)

    def choose_bid_round_3(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        return self._follow(state, my_bid, opponent_bid, phase=3)

    def _follow(self, state: AuctionState, my_bid: int, opponent_bid: int, *, phase: int) -> int:
        if opponent_bid < my_bid:
            return my_bid
        reserve = self._reserve(state, phase=phase)
        need = opponent_bid + MIN_BID_INCREMENT
        if need <= reserve and need <= state.my_budget:
            return need
        return my_bid

    def _reserve(self, state: AuctionState, *, phase: int) -> int:
        cat = state.item.category
        my_cnt, my_val = cat_info(state.my_items, cat)
        opp_cnt, opp_val = cat_info(state.opponent_items, cat)

        immediate = state.item.value + bonus_gain(my_cnt, my_val, state.item.value)
        denial = self._denial_value(opp_cnt, opp_val, state.item.value)
        future = self._future_value(state, my_cnt, opp_cnt)
        tie = self._tie_value(state, phase, my_cnt, opp_cnt)

        value = immediate + denial + future + tie
        value = int(value * self._opponent_pressure(state, phase))
        value = min(value, self._budget_anchor(state, phase, my_cnt))
        return min(max(0, value), state.my_budget)

    def _future_value(self, state: AuctionState, my_cnt: int, opp_cnt: int) -> int:
        left = left_in_cat(state)
        if left <= 0:
            return 0

        my_edge = self._future_edge(my_cnt)
        opp_edge = 0 if opp_cnt <= 0 else int(self._future_edge(opp_cnt) * 0.55)
        urgency = 1.0 + min(2, my_cnt) * 0.16 + min(2, opp_cnt) * 0.10
        if left == 1:
            urgency += 0.20
        return int((my_edge + opp_edge) * left * urgency * 0.85)

    def _future_edge(self, cnt: int) -> int:
        return int(AVG_ITEM * ((1.0 + bonus_rate(cnt + 1)) - (1.0 + bonus_rate(cnt))))

    def _denial_value(self, opp_cnt: int, opp_val: int, item_value: int) -> int:
        if opp_cnt <= 0:
            return 0
        return int(bonus_gain(opp_cnt, opp_val, item_value) * 0.48)

    def _tie_value(self, state: AuctionState, phase: int, my_cnt: int, opp_cnt: int) -> int:
        if phase != 3:
            return 0
        if my_cnt > 0 or opp_cnt >= 2 or state.total_rounds - state.round_index <= 3:
            return MIN_BID_INCREMENT
        return 0

    def _budget_anchor(self, state: AuctionState, phase: int, my_cnt: int) -> int:
        rounds_left = max(1, state.total_rounds - state.round_index)
        share = state.my_budget // rounds_left
        anchor = share + int(state.item.value * 0.62)
        if my_cnt > 0:
            anchor += state.item.value // 4
        if phase == 3:
            anchor += MIN_BID_INCREMENT
        if rounds_left <= 4:
            anchor += share // 2
        return min(state.my_budget, max(anchor, state.item.value // 2))

    def _opponent_pressure(self, state: AuctionState, phase: int) -> float:
        past_items = self._seen[:-1]
        if not past_items:
            return 1.0 if phase == 1 else 1.03

        ratios = [bid / item.value for item, bid in zip(past_items, state.opponent_bids) if item.value > 0]
        if not ratios:
            return 1.0

        avg = sum(ratios) / len(ratios)
        if avg >= 1.02:
            return 1.15 if phase >= 2 else 1.07
        if avg >= 0.90:
            return 1.07 if phase >= 2 else 1.02
        if avg <= 0.65:
            return 0.94
        return 1.0

    def _open_pct(self, state: AuctionState) -> int:
        pressure = self._opponent_pressure(state, 1)
        if pressure >= 1.10:
            return 80
        if pressure <= 0.95:
            return 67
        return 74

    def _remember(self, state: AuctionState) -> None:
        if len(self._seen) == state.round_index:
            self._seen.append(state.item)


BOT_CLASS = GuavaBot
