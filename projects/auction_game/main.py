from __future__ import annotations

import argparse

from projects.auction_game.engine import play_match, run_tournament


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the auction game demo tournament.")
    parser.add_argument("--budget", type=int, default=100, help="Budget per bot")
    args = parser.parse_args()

    standings = run_tournament(budget=args.budget)
    print("Auction game standings")
    for index, row in enumerate(standings, start=1):
        print(
            f"{index:>2}. {row['bot']:<20} points={row['points']:<3} "
            f"value={row['value']:<3} spend={row['spend']}"
        )

    sample = play_match("greedy_value", "steady_bidder", budget=args.budget)
    print("\nSample match: greedy_value vs steady_bidder")
    print(
        f"Value: {sample.left_value} - {sample.right_value} | "
        f"Spend: {sample.left_spend} - {sample.right_spend}"
    )
    for line in sample.log[:5]:
        print(line)


if __name__ == "__main__":
    main()
