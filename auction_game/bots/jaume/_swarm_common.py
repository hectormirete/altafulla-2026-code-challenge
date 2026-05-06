from __future__ import annotations

from dataclasses import dataclass

from auction_game import AuctionBot, AuctionState
from auction_game.bots.jaume.codex_optimal_9 import CodexOptimal9Bot

ROLE_SIGNAL_BASE = 100_000
QUEEN_OPEN = 12_345
SOLDIER_OPEN = 54_321


@dataclass(frozen=True, slots=True)
class SwarmConfig:
    role: str
    codename: str
    lane: int = 0


class SwarmBot(CodexOptimal9Bot):
    def __init__(self, config: SwarmConfig) -> None:
        super().__init__()
        self._config = config
        self._recognized_peer = False

    def choose_bid_round_1(self, state: AuctionState) -> int:
        if state.round_index == 0:
            return min(self._open_signature(state), state.my_budget)
        if self._recognized_peer and self._config.role == "soldier":
            return 0
        return super().choose_bid_round_1(state)

    def choose_bid_round_2(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        if state.round_index == 0 and opponent_bid == self._expected_peer_signature(state):
            self._recognized_peer = True
        if self._recognized_peer and self._config.role == "soldier":
            return my_bid
        return super().choose_bid_round_2(state, my_bid, opponent_bid)

    def choose_bid_round_3(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        if self._recognized_peer and self._config.role == "soldier":
            return my_bid
        return super().choose_bid_round_3(state, my_bid, opponent_bid)

    def _open_signature(self, state: AuctionState) -> int:
        role_marker = QUEEN_OPEN if self._config.role == "queen" else SOLDIER_OPEN
        base_open = self._base_opening_bid(state)
        return base_open - (base_open % ROLE_SIGNAL_BASE) + role_marker

    def _expected_peer_signature(self, state: AuctionState) -> int:
        role_marker = SOLDIER_OPEN if self._config.role == "queen" else QUEEN_OPEN
        base_open = self._base_opening_bid(state)
        return base_open - (base_open % ROLE_SIGNAL_BASE) + role_marker

    def _base_opening_bid(self, state: AuctionState) -> int:
        ceiling = self._ceiling(state, opponent_bid=0, final_round=False)
        opener = min(ceiling, int(self._own_effective_value(state) * self._opener_rate(state)))
        return self._clamp(opener, 0, state.my_budget)


def make_queen_bot_class(codename: str) -> type[AuctionBot]:
    class SwarmQueenBot(SwarmBot):
        def __init__(self) -> None:
            super().__init__(SwarmConfig(role="queen", codename=codename))

    SwarmQueenBot.__name__ = f"{codename.title().replace('-', '')}QueenBot"
    return SwarmQueenBot


def make_soldier_bot_class(codename: str, lane: int) -> type[AuctionBot]:
    class SwarmSoldierBot(SwarmBot):
        def __init__(self) -> None:
            super().__init__(SwarmConfig(role="soldier", codename=codename, lane=lane))

    SwarmSoldierBot.__name__ = f"{codename.title().replace('-', '')}SoldierBot"
    return SwarmSoldierBot
