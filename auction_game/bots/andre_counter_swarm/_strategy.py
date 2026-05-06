from __future__ import annotations

from dataclasses import dataclass, field

from auction_game.interfaces import AuctionBot, AuctionItem, AuctionState, MIN_BID_INCREMENT


TARGET_CATEGORY_ITEMS = 4


@dataclass(frozen=True, slots=True)
class CounterConfig:
    bot_name: str
    category: str


@dataclass(slots=True)
class OpponentProfile:
    category_pressure: dict[str, int] = field(default_factory=dict)

    def observe(self, category: str, item_value: int, bid: int) -> None:
        if bid >= item_value:
            pressure = 3
        elif bid >= int(item_value * 0.78):
            pressure = 2
        elif bid >= int(item_value * 0.50):
            pressure = 1
        else:
            pressure = 0

        if pressure:
            self.category_pressure[category] = self.category_pressure.get(category, 0) + pressure

    def focus_category(self) -> str | None:
        if not self.category_pressure:
            return None
        return max(self.category_pressure, key=self.category_pressure.get)

    def pressure_for(self, category: str) -> int:
        return self.category_pressure.get(category, 0)


TEAM_MEMORY: dict[tuple[int, ...], OpponentProfile] = {}


def _bonus_rate(item_count: int) -> float:
    return min(0.06 * max(0, item_count - 1) + 0.02 * max(0, item_count - 3), 0.30)


def _category_count(items: tuple[AuctionItem, ...], category: str) -> int:
    return sum(1 for item in items if item.category == category)


def _category_bonus(items: tuple[AuctionItem, ...]) -> int:
    category_values: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    for item in items:
        category_values[item.category] = category_values.get(item.category, 0) + item.value
        category_counts[item.category] = category_counts.get(item.category, 0) + 1
    return sum(
        int(category_values[category] * _bonus_rate(category_counts[category]))
        for category in category_values
    )


def _bonus_delta(items: tuple[AuctionItem, ...], item: AuctionItem) -> int:
    return _category_bonus(items + (item,)) - _category_bonus(items)


def _opening_bucket(item_value: int, bid: int) -> int:
    return min(30, max(0, bid * 20 // max(1, item_value)))


def build_counter_bot(config: CounterConfig) -> type[AuctionBot]:
    class CounterSwarmBot(AuctionBot):
        def __init__(self) -> None:
            self._signature: list[int] = []
            self._profile: OpponentProfile | None = None
            self._triggered_fair_opener = False
            self._opponent_openings_seen = 0
            self._opponent_high_openings = 0
            self._opponent_contests_value = False
            self._opponent_tracks_high_openers = False
            self._opponent_accepts_expensive_raises = False

        def _profile_for_current_match(self) -> OpponentProfile | None:
            if not self._signature:
                return None
            for length in range(len(self._signature), 0, -1):
                profile = TEAM_MEMORY.get(tuple(self._signature[:length]))
                if profile is not None:
                    return profile
            return None

        def _observe_opening(self, state: AuctionState, bid: int) -> None:
            if len(self._signature) < 3:
                self._signature.append(_opening_bucket(state.item.value, bid))

            key = tuple(self._signature)
            profile = TEAM_MEMORY.setdefault(key, self._profile_for_current_match() or OpponentProfile())
            profile.observe(state.item.category, state.item.value, bid)
            self._profile = profile

        def _known_pressure(self, category: str) -> int:
            profile = self._profile_for_current_match() or self._profile
            if profile is None:
                return 0
            return profile.pressure_for(category)

        def _known_focus(self) -> str | None:
            profile = self._profile_for_current_match() or self._profile
            if profile is None:
                return None
            return profile.focus_category()

        def _target_bonus_value(self, state: AuctionState) -> int:
            current_count = _category_count(state.my_items, config.category)
            target_count = max(TARGET_CATEGORY_ITEMS, current_count + 1)
            return int(state.item.value * _bonus_rate(target_count))

        def _denial_value(self, state: AuctionState) -> int:
            category = state.item.category
            opponent_count = _category_count(state.opponent_items, category)
            if opponent_count < 2:
                return 0
            return int(state.item.value * 0.08)

        def _value(self, state: AuctionState) -> int:
            denial_value = self._denial_value(state)

            if state.item.category == config.category:
                value = (
                    state.item.value
                    + self._target_bonus_value(state)
                    + denial_value
                    + 1_500_000
                )
            else:
                if self._opponent_openings_seen >= 2 and not self._opponent_contests_value:
                    value = state.item.value - 1_000_000 + denial_value
                else:
                    value = state.item.value + 500_000 + denial_value

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
            self._observe_opening(state, opponent_bid)
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

            target = opponent_bid + MIN_BID_INCREMENT
            if opponent_bid >= my_bid and target <= self._value(state):
                return min(target, state.my_budget)
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

    CounterSwarmBot.__name__ = config.bot_name
    return CounterSwarmBot
