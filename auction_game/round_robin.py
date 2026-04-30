from __future__ import annotations

from collections.abc import Callable
from itertools import combinations
from typing import TypeVar

T = TypeVar("T")


def run_round_robin(
    competitors: list[str],
    play_match: Callable[[str, str], T],
) -> list[tuple[str, str, T]]:
    results = []
    for left, right in combinations(competitors, 2):
        results.append((left, right, play_match(left, right)))
    return results
