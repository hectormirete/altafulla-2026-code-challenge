# Auction Game Prototype

<!-- leaderboard:start -->
## Latest Leaderboard

Last run config: `budget=200000000` `items=20` `min_value=11000000` `max_value=20000000` `seed=7`

| Rank | User | Bot | Win Rate | Wins | Matches | Score |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | demo-bots | category_collector | 100.0% | 2 | 2 | 383065548 |
| 2 | demo-bots | greedy_value | 50.0% | 1 | 2 | 325569674 |
| 3 | demo-bots | steady_bidder | 0.0% | 0 | 2 | 289099494 |

<!-- leaderboard:end -->

## What Is This Project About?

This repository contains a lightweight tournament engine for the conference
auction game. It is designed to be fast enough for all-vs-all evaluation on
each submission.

Each bot gets a `200_000_000` budget by default and competes across `20` blind
auctions. Item values are generated randomly for each tournament run within a
configured range, and final score is:

```text
sum(won item values) + category bonuses + money left
```

That keeps saving cash relevant without making "buy nothing" dominant, as long
as the total item slate is worth more than the initial budget.

Category bonuses use a soft milestone curve per category. If a bot wins `n`
items in a category with total category value `v`, the bonus rate is:

```text
min(0.06 * max(0, n - 1) + 0.02 * max(0, n - 3), 0.30)
```

So repeated wins in a category matter, but the bonus ramps gradually and caps
at `30%` of that category's total value.

## Setup

```bash
uv sync
```

## Run the demo

```bash
uv run python -m auction_game.main
```

## Bot API

Challenge participants should implement a class that inherits from
`auction_game.AuctionBot` and export it as `BOT_CLASS`.

Bots are discovered from this folder structure:

```text
auction_game/bots/<user-name>/<bot-name>.py
```

```python
from auction_game import AuctionBot, AuctionState


class MyBot(AuctionBot):
    def choose_bid(self, state: AuctionState) -> int:
        return min(state.item.value, state.my_budget)


BOT_CLASS = MyBot
```

`AuctionState` includes the current item, both remaining budgets, prior bids,
prior won items, the current round index, and total rounds. Bots do not see the
other bot's current-round bid.
