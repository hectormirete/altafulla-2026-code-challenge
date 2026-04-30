from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AuctionItem:
    name: str
    category: str
    value: int


@dataclass(frozen=True, slots=True)
class AuctionState:
    round_index: int
    total_rounds: int
    item: AuctionItem
    my_budget: int
    opponent_budget: int
    my_items: tuple[AuctionItem, ...]
    opponent_items: tuple[AuctionItem, ...]
    my_bids: tuple[int, ...]
    opponent_bids: tuple[int, ...]


class AuctionBot(ABC):
    @abstractmethod
    def choose_bid(self, state: AuctionState) -> int:
        raise NotImplementedError
