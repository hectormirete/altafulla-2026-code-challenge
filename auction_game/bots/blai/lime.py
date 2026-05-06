from __future__ import annotations

import random

from auction_game import AuctionBot, AuctionItem, AuctionState, MIN_BID_INCREMENT

CATS = ("ai", "web", "brand", "cloud", "dev", "data")


class BotCfg:
    open_ratio = 0.76
    deny_w = 0.38
    budget_push = 0.03
    rnd_low = 0.94
    rnd_high = 1.04
    step_up_bonus = 800_000
    own_second_bonus = 500_000
    own_later_bonus = 850_000
    opp_second_bonus = 350_000
    opp_later_bonus = 900_000
    future_cat_w = 0.060
    future_opp_w = 0.015
    late_score_rounds = 5
    trail_push_bonus = 500_000
    lead_soft_cut = 0
    last_one_bonus = 900_000
    near_last_bonus = 600_000
    late_max_mul = 1.6
    bully_open_floor = 1.03
    bully_jump_margin = 1_500_000
    bully_min_value = 12_000_000
    bully_push_bonus = 500_000


def bonus_rate(cnt: int) -> float:
    raw = 0.06 * max(0, cnt - 1) + 0.02 * max(0, cnt - 3)
    return min(raw, 0.30)


def cat_cnt(items: tuple[AuctionItem, ...], cat: str) -> int:
    return sum(1 for item in items if item.category == cat)


def cat_val(items: tuple[AuctionItem, ...], cat: str) -> int:
    return sum(item.value for item in items if item.category == cat)


def bonus_gain(cnt: int, value: int, item_value: int) -> int:
    now_bonus = int(value * bonus_rate(cnt))
    next_value = value + item_value
    next_bonus = int(next_value * bonus_rate(cnt + 1))
    return next_bonus - now_bonus


def total_bonus(items: tuple[AuctionItem, ...]) -> int:
    return sum(int(cat_val(items, cat) * bonus_rate(cat_cnt(items, cat))) for cat in CATS)


def score_now(items: tuple[AuctionItem, ...], budget: int) -> int:
    return sum(item.value for item in items) + total_bonus(items) + budget


def left_in_cat(state: AuctionState, cat: str) -> int:
    left = 0
    for idx in range(state.round_index + 1, state.total_rounds):
        if CATS[idx % len(CATS)] == cat:
            left += 1
    return left


class LimeBot(AuctionBot):
    def __init__(self) -> None:
        self.cfg = BotCfg()

    def _rounds_left(self, state: AuctionState) -> int:
        return max(1, state.total_rounds - state.round_index)

    def _raw_value(self, state: AuctionState) -> int:
        return state.item.value

    def _cat_swing(self, state: AuctionState) -> int:
        cat = state.item.category
        my_cnt = cat_cnt(state.my_items, cat)
        opp_cnt = cat_cnt(state.opponent_items, cat)
        my_val = cat_val(state.my_items, cat)
        opp_val = cat_val(state.opponent_items, cat)
        my_gain = bonus_gain(my_cnt, my_val, state.item.value)
        opp_gain = bonus_gain(opp_cnt, opp_val, state.item.value)
        swing = my_gain + int(opp_gain * self.cfg.deny_w)
        swing += self._step_bonus(my_cnt, is_opp=False)
        swing += self._step_bonus(opp_cnt, is_opp=True)
        return swing

    def _step_bonus(self, cnt: int, *, is_opp: bool) -> int:
        next_cnt = cnt + 1
        if next_cnt == 2:
            return self.cfg.opp_second_bonus if is_opp else self.cfg.own_second_bonus
        if next_cnt in (3, 4):
            return self.cfg.opp_later_bonus if is_opp else self.cfg.own_later_bonus
        return 0

    def _future_cat_value(self, state: AuctionState) -> int:
        cat = state.item.category
        left = left_in_cat(state, cat)
        if left <= 0:
            return 0

        my_cnt = cat_cnt(state.my_items, cat)
        opp_cnt = cat_cnt(state.opponent_items, cat)
        my_part = 0
        opp_part = 0

        if my_cnt > 0:
            my_part = int(state.item.value * left * self.cfg.future_cat_w)
        if opp_cnt > 0:
            opp_part = int(state.item.value * left * self.cfg.future_opp_w)
        return my_part + opp_part

    def _urgenc(self, state: AuctionState) -> int:
        cat = state.item.category
        left = left_in_cat(state, cat)
        my_cnt = cat_cnt(state.my_items, cat)
        opp_cnt = cat_cnt(state.opponent_items, cat)
        if left == 0 and (my_cnt > 0 or opp_cnt > 0):
            return self.cfg.last_one_bonus
        if left == 1 and (my_cnt > 0 or opp_cnt > 0):
            return self.cfg.near_last_bonus
        return 0

    def _budget_pressur(self, state: AuctionState) -> int:
        rounds_left = self._rounds_left(state)
        my_per = state.my_budget / rounds_left
        opp_per = state.opponent_budget / rounds_left
        diff = my_per - opp_per
        return int(diff * self.cfg.budget_push)

    def _score_adjust(self, state: AuctionState) -> int:
        if self._rounds_left(state) > self.cfg.late_score_rounds:
            return 0

        gap = score_now(state.my_items, state.my_budget) - score_now(state.opponent_items, state.opponent_budget)
        if gap < -10_000_000 and self._is_push_item(state):
            return self.cfg.trail_push_bonus
        if gap > 18_000_000 and not self._is_push_item(state):
            return -self.cfg.lead_soft_cut
        return 0

    def _max_bid(self, state: AuctionState) -> int:
        rounds_left = self._rounds_left(state)
        my_per = state.my_budget / rounds_left
        mul = 1.45
        if rounds_left <= 5:
            mul = self.cfg.late_max_mul
        return min(int(my_per * mul), state.my_budget)

    def _is_push_item(self, state: AuctionState) -> bool:
        cat = state.item.category
        my_cnt = cat_cnt(state.my_items, cat)
        opp_cnt = cat_cnt(state.opponent_items, cat)
        left = left_in_cat(state, cat)
        if state.item.value >= self.cfg.bully_min_value:
            return True
        if my_cnt + 1 in (2, 3, 4) or opp_cnt + 1 in (2, 3, 4):
            return True
        if left <= 1 and (my_cnt > 0 or opp_cnt > 0):
            return True
        return False

    def _bully_line(self, state: AuctionState) -> int:
        return min(int(state.item.value * self.cfg.bully_open_floor), state.my_budget)

    def _price_for_me(self, state: AuctionState) -> int:
        value = self._raw_value(state)
        value += self._cat_swing(state)
        value += self._future_cat_value(state)
        value += self._urgenc(state)
        value += self._budget_pressur(state)
        value += self._score_adjust(state)
        if self._is_push_item(state):
            value += self.cfg.bully_push_bonus
        value = max(0, value)
        return min(value, self._max_bid(state))

    def choose_bid_round_1(self, state: AuctionState) -> int:
        price = self._price_for_me(state)
        rand_mult = random.uniform(self.cfg.rnd_low, self.cfg.rnd_high)
        open_bid = int(price * self.cfg.open_ratio * rand_mult)
        if self._is_push_item(state):
            bully_line = self._bully_line(state)
            if bully_line <= price:
                open_bid = max(open_bid, bully_line)
        return min(max(0, open_bid), state.my_budget)

    def _anti_bully_bid(self, state: AuctionState, my_bid: int, opponent_bid: int, price: int) -> int:
        bully_break = min(self._bully_line(state) + self.cfg.bully_jump_margin, state.my_budget)
        if self._is_push_item(state) and opponent_bid >= int(state.item.value * 0.75) and bully_break <= price:
            return max(my_bid, bully_break)
        need_bid = opponent_bid + MIN_BID_INCREMENT
        if need_bid <= price:
            return min(need_bid, state.my_budget)
        return my_bid

    def choose_bid_round_2(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        if opponent_bid < my_bid:
            return my_bid
        return self._anti_bully_bid(state, my_bid, opponent_bid, self._price_for_me(state))

    def choose_bid_round_3(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        if opponent_bid < my_bid:
            return my_bid
        return self._anti_bully_bid(state, my_bid, opponent_bid, self._price_for_me(state))


BOT_CLASS = LimeBot
