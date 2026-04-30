# Auction Game Prototype

This repository contains a lightweight tournament engine for the conference
auction game. It is designed to be fast enough for all-vs-all evaluation on
each submission.

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
