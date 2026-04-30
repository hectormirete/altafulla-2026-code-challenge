from __future__ import annotations

import random
from pathlib import Path

from auction_game.bot_loader import discover_bots, load_bot
from auction_game.engine import DEFAULT_BUDGET, generate_items, play_match
from auction_game.interfaces import AuctionState


def _build_probe_state() -> AuctionState:
    items = generate_items(item_count=3, rng=random.Random(11))
    return AuctionState(
        round_index=0,
        total_rounds=3,
        item=items[0],
        my_budget=DEFAULT_BUDGET,
        opponent_budget=DEFAULT_BUDGET,
        my_items=tuple(),
        opponent_items=tuple(),
        my_bids=tuple(),
        opponent_bids=tuple(),
    )


def validate_bots() -> None:
    bots_dir = Path(__file__).with_name("bots")
    bot_specs = discover_bots(bots_dir)
    if not bot_specs:
        raise ValueError("No bots discovered")

    probe_state = _build_probe_state()
    anchor_bot_id = "demo-bots/greedy_value"
    discovered_ids = {bot_spec.bot_id for bot_spec in bot_specs}
    if anchor_bot_id not in discovered_ids:
        raise ValueError(f"Expected anchor bot {anchor_bot_id} to exist for validation")

    for bot_spec in bot_specs:
        bot = load_bot(bot_spec)
        round_1 = bot.choose_bid_round_1(probe_state)
        round_2 = bot.choose_bid_round_2(probe_state, round_1, round_1)
        round_3 = bot.choose_bid_round_3(probe_state, round_2, round_2)

        if not isinstance(round_1, int):
            raise TypeError(f"{bot_spec.bot_id} choose_bid_round_1 must return int")
        if not isinstance(round_2, int):
            raise TypeError(f"{bot_spec.bot_id} choose_bid_round_2 must return int")
        if not isinstance(round_3, int):
            raise TypeError(f"{bot_spec.bot_id} choose_bid_round_3 must return int")

        if bot_spec.bot_id != anchor_bot_id:
            play_match(bot_spec.bot_id, anchor_bot_id, items=generate_items(rng=random.Random(7)))


if __name__ == "__main__":
    validate_bots()
