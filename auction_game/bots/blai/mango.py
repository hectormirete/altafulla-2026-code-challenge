from __future__ import annotations

import random

from auction_game import AuctionBot, AuctionItem, AuctionState, MIN_BID_INCREMENT

CATS = ("ai", "web", "brand", "cloud", "dev", "data")


class BotCfg:
    open_ratio = 0.76
    deny_w = 0.45
    budget_push = 0.12
    rnd_low = 0.92
    rnd_high = 1.04
    step_up_bonus = 1_200_000
    last_one_bonus = 900_000
    near_last_bonus = 600_000
    late_max_mul = 1.6


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


def left_in_cat(state: AuctionState, cat: str) -> int:
    left = 0
    for idx in range(state.round_index + 1, state.total_rounds):
        if CATS[idx % len(CATS)] == cat:
            left += 1
    return left


class BlaiBot(AuctionBot):
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
        if my_cnt + 1 in (2, 3, 4):
            swing += self.cfg.step_up_bonus
        if opp_cnt + 1 in (2, 3, 4):
            swing += self.cfg.step_up_bonus
        return swing

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

    def _max_bid(self, state: AuctionState) -> int:
        rounds_left = self._rounds_left(state)
        my_per = state.my_budget / rounds_left
        mul = 1.4
        if rounds_left <= 5:
            mul = self.cfg.late_max_mul
        return min(int(my_per * mul), state.my_budget)

    def _price_for_me(self, state: AuctionState) -> int:
        value = self._raw_value(state)
        value += self._cat_swing(state)
        value += self._urgenc(state)
        value += self._budget_pressur(state)
        value = max(0, value)
        return min(value, self._max_bid(state))

    def choose_bid_round_1(self, state: AuctionState) -> int:
        price = self._price_for_me(state)
        rand_mult = random.uniform(self.cfg.rnd_low, self.cfg.rnd_high)
        open_bid = int(price * self.cfg.open_ratio * rand_mult)
        return min(max(0, open_bid), state.my_budget)

    def choose_bid_round_2(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        if opponent_bid < my_bid:
            return my_bid
        price = self._price_for_me(state)
        need_bid = opponent_bid + MIN_BID_INCREMENT
        if need_bid <= price:
            return min(need_bid, state.my_budget)
        return max(my_bid, min(price, state.my_budget))

    def choose_bid_round_3(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        if opponent_bid < my_bid:
            return my_bid
        price = self._price_for_me(state)
        need_bid = opponent_bid + MIN_BID_INCREMENT
        if need_bid <= price:
            return min(need_bid, state.my_budget)
        return max(my_bid, min(price, state.my_budget))


BOT_CLASS = BlaiBot
