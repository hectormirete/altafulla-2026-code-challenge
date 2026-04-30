# Auction Game Prototype

This repository contains a lightweight tournament engine for the conference
auction game. It is designed to be fast enough for all-vs-all evaluation on
each submission.

Each bot gets a `200_000_000` budget by default and competes across `20` blind
auctions. Item values are generated randomly for each tournament run within a
configured range, and final score is:

```text
sum(won item values) + money left
```

That keeps saving cash relevant without making "buy nothing" dominant, as long
as the total item slate is worth more than the initial budget.

## Setup

```bash
uv sync
```

## Run the demo

```bash
uv run python -m auction_game.main
```

## Bot API

Auction bots expose:

```python
def choose_bid(state: dict) -> int:
    ...
```

The `state` includes the current item, both remaining budgets, prior bids,
prior won items, the current round index, and total rounds. Bots do not see the
other bot's current-round bid.
