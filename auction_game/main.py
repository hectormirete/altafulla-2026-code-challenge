from __future__ import annotations

import argparse
import random

from auction_game.engine import (
    DEFAULT_BUDGET,
    DEFAULT_ITEM_COUNT,
    MAX_ITEM_VALUE,
    MIN_ITEM_VALUE,
    generate_items,
    play_match,
    run_tournament,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the auction game demo tournament.")
    parser.add_argument("--budget", type=int, default=DEFAULT_BUDGET, help="Budget per bot")
    parser.add_argument("--items", type=int, default=DEFAULT_ITEM_COUNT, help="Number of items")
    parser.add_argument("--min-value", type=int, default=MIN_ITEM_VALUE, help="Minimum item value")
    parser.add_argument("--max-value", type=int, default=MAX_ITEM_VALUE, help="Maximum item value")
    parser.add_argument("--seed", type=int, default=7, help="Random seed for the item slate")
    args = parser.parse_args()

    standings = run_tournament(
        budget=args.budget,
        item_count=args.items,
        min_value=args.min_value,
        max_value=args.max_value,
        seed=args.seed,
    )
    print("Auction game standings")
    for index, row in enumerate(standings, start=1):
        print(
            f"{index:>2}. {row['bot']:<20} points={row['points']:<3} "
            f"score={row['score']:<10} value={row['value']:<10} "
            f"bonus={row['category_bonus']:<10} cash={row['money_left']}"
        )

    items = generate_items(
        item_count=args.items,
        min_value=args.min_value,
        max_value=args.max_value,
        rng=random.Random(args.seed),
    )
    sample = play_match("greedy_value", "steady_bidder", budget=args.budget, items=items)
    print("\nSample match: greedy_value vs steady_bidder")
    print(
        f"Score: {sample.left_score} - {sample.right_score} | "
        f"Value: {sample.left_value} - {sample.right_value} | "
        f"Bonus: {sample.left_category_bonus} - {sample.right_category_bonus} | "
        f"Cash: {sample.left_money_left} - {sample.right_money_left}"
    )
    for line in sample.log[:5]:
        print(line)


if __name__ == "__main__":
    main()
