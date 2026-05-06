# Auction Game Prototype

<!-- leaderboard:start -->
## Latest Leaderboard

Last run config: `budget=200000000` `items=20` `min_value=8000000` `max_value=16000000` `seed=random`

| Rank | User | Bot | Win Rate | Wins | Matches | Score |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | ruben-abad | aggressive_bully | 95.8% | 23 | 24 | 5_586_908_253 |
| 2 | ruben-abad | breakpoint_denier | 87.5% | 21 | 24 | 6_086_749_103 |
| 3 | ruben-abad | tit_for_tat | 87.5% | 21 | 24 | 6_036_903_717 |
| 4 | jaume | king | 79.2% | 19 | 24 | 5_383_721_673 |
| 5 | ruben-abad | budget_aware_bidder | 75.0% | 18 | 24 | 5_712_987_014 |
| 6 | miguellobato84 | value_sniper | 70.8% | 17 | 24 | 6_236_066_228 |
| 7 | miguellobato84 | late_raiser | 66.7% | 16 | 24 | 6_197_057_324 |
| 8 | ruben-abad | value_hunter | 66.7% | 16 | 24 | 6_154_028_009 |
| 9 | demo-bots | copycat_bidder | 62.5% | 15 | 24 | 5_005_411_507 |
| 10 | ruben-abad | zero_intelligence_constrainer_rng | 58.3% | 14 | 24 | 6_135_399_218 |
| 11 | miguellobato84 | noisy_opportunist | 58.3% | 14 | 24 | 5_004_037_887 |
| 12 | ruben-abad | zero_intelligence_constrainer | 50.0% | 12 | 24 | 5_957_438_149 |
| 13 | demo-bots | greedy_value | 50.0% | 12 | 24 | 4_712_376_162 |
| 14 | martin | value_trap | 50.0% | 12 | 24 | 4_632_739_170 |
| 15 | ruben-abad | patient_sniper | 37.5% | 9 | 24 | 5_986_272_349 |
| 16 | miguellobato84 | balanced_portfolio | 37.5% | 9 | 24 | 5_499_476_370 |
| 17 | miguellobato84 | copycat_counterbidder | 33.3% | 8 | 24 | 5_530_862_535 |
| 18 | miguellobato84 | cash_preserver | 33.3% | 8 | 24 | 4_608_361_495 |
| 19 | miguellobato84 | scarcity_aware | 33.3% | 8 | 24 | 4_512_492_977 |
| 20 | miguellobato84 | anti_leader | 33.3% | 8 | 24 | 4_486_447_996 |
| 21 | demo-bots | steady_bidder | 29.2% | 7 | 24 | 3_736_781_115 |
| 22 | ruben-abad | category_synergist | 25.0% | 6 | 24 | 5_079_960_966 |
| 23 | miguellobato84 | early_domination | 12.5% | 3 | 24 | 2_662_115_672 |
| 24 | miguellobato84 | deterministic_heuristic | 8.3% | 2 | 24 | 1_454_829_383 |
| 25 | demo-bots | random_bidder | 8.3% | 2 | 24 | 936_468_704 |

<!-- leaderboard:end -->

## What Is This Project About?

This repository contains a lightweight tournament engine for the conference
auction game. It is designed to be fast enough for all-vs-all evaluation on
each submission.

Each bot gets a `200_000_000` budget by default and competes across `20`
auctions. Each item is sold through 3 bidding rounds: a blind opening bid, a
second bid after both opening bids are revealed, and a final third bid after
the second bids are revealed. Item values are generated randomly for each
tournament run within a configured range, and final score is:

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

Each participant may submit one or more bots under their own `<user-name>`
directory.

The repository includes sample bots under `auction_game/bots/demo-bots/`.

```python
from auction_game import AuctionBot, AuctionState


class MyBot(AuctionBot):
    def choose_bid_round_1(self, state: AuctionState) -> int:
        return min(state.item.value, state.my_budget)

    def choose_bid_round_2(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        return max(my_bid, min(opponent_bid + 1, state.my_budget))

    def choose_bid_round_3(self, state: AuctionState, my_bid: int, opponent_bid: int) -> int:
        return max(my_bid, min(opponent_bid + 1, state.my_budget))


BOT_CLASS = MyBot
```

`AuctionState` includes the current item, both remaining budgets, prior bids,
prior won items, the current round index, and total rounds. In rounds 2 and 3,
bots receive the standing bids explicitly through the method arguments and may
only keep or raise their own previous bid. A raise must beat the opponent's
current standing bid by at least `1_000_000` by default.

## Submission Rules

- Submit only bots under your own directory, using
  `auction_game/bots/<user-name>/<bot-name>.py`. You may submit multiple bot
  files under your own `<user-name>` directory.
- Do not modify the engine, scoring, interfaces, validator, loader, leaderboard,
  demo bots, or other participants' files as part of a ranked submission.
- Your bot may only use the information provided through `AuctionState`,
  `my_bid`, and `opponent_bid`.
- Bots must not modify repository or process state from inside bot code,
  including monkey-patching imported modules, globals, builtins, or
  `sys.modules`.
- Bots must not use the network, shell commands, subprocesses, filesystem
  access, environment variables, or hidden repository data at runtime.
- Submissions should pass `python -m auction_game.validate_bots`.

Full participant and Codex-specific rules are documented in [AGENTS.md](AGENTS.md).
