from __future__ import annotations

from dataclasses import dataclass

from auction_game.interfaces import AuctionBot, AuctionState, MIN_BID_INCREMENT

TARGET_CATEGORY_ITEMS = 4


@dataclass(frozen=True, slots=True)
class SpecialistConfig:
    bot_name: str
    category: str
    target_items: int = TARGET_CATEGORY_ITEMS


def _bonus_rate(item_count: int) -> float:
    return min(0.06 * max(0, item_count - 1) + 0.02 * max(0, item_count - 3), 0.30)


def _category_count(state: AuctionState, category: str) -> int:
    return sum(1 for item in state.my_items if item.category == category)


def _opponent_category_count(state: AuctionState, category: str) -> int:
    return sum(1 for item in state.opponent_items if item.category == category)


def build_specialist_bot(config: SpecialistConfig) -> type[AuctionBot]:
    class CategorySpecialistBot(AuctionBot):
        def __init__(self) -> None:
            self._triggered_fair_opener = False
            self._opponent_openings_seen = 0
            self._opponent_high_openings = 0
            self._opponent_contests_value = False
            self._opponent_tracks_high_openers = False
            self._opponent_accepts_expensive_raises = False

        def _target_bonus_value(self, state: AuctionState) -> int:
            if state.item.category != config.category:
                return 0

            current_count = _category_count(state, config.category)
            target_count = max(config.target_items, current_count + 1)
            return int(state.item.value * _bonus_rate(target_count))

        def _denial_value(self, state: AuctionState) -> int:
            opponent_count = _opponent_category_count(state, state.item.category)
            if opponent_count < 2:
                return 0
            return int(state.item.value * 0.08)

        def _value(self, state: AuctionState) -> int:
            if state.item.category == config.category:
                value = (
                    state.item.value
                    + self._target_bonus_value(state)
                    + self._denial_value(state)
                    + 1_500_000
                )
            else:
                if self._opponent_openings_seen >= 2 and not self._opponent_contests_value:
                    value = state.item.value - 1_000_000 + self._denial_value(state)
                else:
                    value = state.item.value + 500_000 + self._denial_value(state)

            return min(state.my_budget, max(0, value))

        def choose_bid_round_1(self, state: AuctionState) -> int:
            opening_bid = self._value(state) - MIN_BID_INCREMENT
            if self._opponent_accepts_expensive_raises:
                expensive_trap_bid = int(state.item.value * 1.16) - MIN_BID_INCREMENT
                opening_bid = max(opening_bid, expensive_trap_bid)
            if self._opponent_tracks_high_openers:
                chaser_trap_bid = int(state.item.value * 1.10) - MIN_BID_INCREMENT
                opening_bid = max(opening_bid, chaser_trap_bid)
            return min(max(0, opening_bid), state.my_budget)

        def choose_bid_round_2(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
            self._opponent_openings_seen += 1
            if opponent_bid >= int(state.item.value * 0.78):
                self._opponent_high_openings += 1
            if (
                self._opponent_openings_seen >= 2
                and self._opponent_high_openings * 2 >= self._opponent_openings_seen
            ):
                self._opponent_tracks_high_openers = True

            if (
                not self._triggered_fair_opener
                and state.item.value + 800_000 <= opponent_bid <= state.item.value + 1_200_000
            ):
                self._triggered_fair_opener = True
                return min(max(my_bid, opponent_bid + MIN_BID_INCREMENT), state.my_budget)
            return my_bid

        def choose_bid_round_3(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
            if opponent_bid >= my_bid and opponent_bid >= int(state.item.value * 0.70):
                self._opponent_contests_value = True
            if my_bid < opponent_bid and opponent_bid >= int(state.item.value * 1.12):
                self._opponent_accepts_expensive_raises = True
            if my_bid < opponent_bid <= int(state.item.value * 1.12) and opponent_bid >= state.item.value:
                self._opponent_tracks_high_openers = True
            target = opponent_bid + MIN_BID_INCREMENT
            if opponent_bid >= my_bid and target <= self._value(state):
                return min(target, state.my_budget)
            return my_bid

    CategorySpecialistBot.__name__ = config.bot_name
    return CategorySpecialistBot
