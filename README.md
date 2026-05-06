# Auction Game Prototype

<!-- leaderboard:start -->
## Latest Leaderboard

Last run config: `budget=200000000` `items=20` `min_value=8000000` `max_value=16000000` `seed=random`

| Rank | User | Bot | Win Rate | Wins | Matches | Score |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | ruben-abad | aggressive_bully | 96.9% | 31 | 32 | 7_248_622_274 |
| 2 | jaume | codex_fun | 90.6% | 29 | 32 | 7_263_378_894 |
| 3 | blai | mango | 90.6% | 29 | 32 | 7_234_415_981 |
| 4 | hanna | bellman-bot | 87.5% | 28 | 32 | 7_548_874_802 |
| 5 | miguellobato84 | category_harvester | 87.5% | 28 | 32 | 7_079_725_685 |
| 6 | miguellobato84 | category_harvester_v2 | 78.1% | 25 | 32 | 7_230_755_052 |
| 7 | miguellobato84 | lookahead_planner | 75.0% | 24 | 32 | 7_251_078_631 |
| 8 | miguellobato84 | hybrid_model | 71.9% | 23 | 32 | 6_517_476_506 |
| 9 | ruben-abad | tit_for_tat | 68.8% | 22 | 32 | 7_799_827_069 |
| 10 | jaume | king | 65.6% | 21 | 32 | 6_895_609_675 |
| 11 | ruben-abad | zero_intelligence_constrainer_rng | 62.5% | 20 | 32 | 8_104_327_854 |
| 12 | miguellobato84 | value_sniper | 62.5% | 20 | 32 | 7_887_321_039 |
| 13 | ruben-abad | breakpoint_denier | 59.4% | 19 | 32 | 7_541_615_093 |
| 14 | ruben-abad | budget_aware_bidder | 59.4% | 19 | 32 | 7_341_282_160 |
| 15 | miguellobato84 | hybrid_model_v2 | 59.4% | 19 | 32 | 7_227_372_649 |
| 16 | ruben-abad | value_hunter | 53.1% | 17 | 32 | 7_979_070_815 |
| 17 | miguellobato84 | late_raiser | 50.0% | 16 | 32 | 7_762_695_454 |
| 18 | demo-bots | copycat_bidder | 46.9% | 15 | 32 | 6_347_933_135 |
| 19 | martin | value_trap | 43.8% | 14 | 32 | 5_923_740_350 |
| 20 | demo-bots | greedy_value | 43.8% | 14 | 32 | 5_748_352_531 |
| 21 | ruben-abad | zero_intelligence_constrainer | 34.4% | 11 | 32 | 7_583_671_137 |
| 22 | miguellobato84 | noisy_opportunist | 34.4% | 11 | 32 | 6_160_396_305 |
| 23 | miguellobato84 | scarcity_aware | 34.4% | 11 | 32 | 5_759_371_950 |
| 24 | miguellobato84 | balanced_portfolio | 28.1% | 9 | 32 | 7_163_261_590 |
| 25 | miguellobato84 | anti_leader | 28.1% | 9 | 32 | 5_971_757_389 |
| 26 | demo-bots | steady_bidder | 28.1% | 9 | 32 | 5_375_417_408 |
| 27 | ruben-abad | patient_sniper | 25.0% | 8 | 32 | 7_718_680_888 |
| 28 | miguellobato84 | copycat_counterbidder | 25.0% | 8 | 32 | 7_280_671_180 |
| 29 | miguellobato84 | cash_preserver | 21.9% | 7 | 32 | 5_531_296_169 |
| 30 | ruben-abad | category_synergist | 12.5% | 4 | 32 | 6_744_589_399 |
| 31 | miguellobato84 | deterministic_heuristic | 12.5% | 4 | 32 | 2_223_789_420 |
| 32 | miguellobato84 | early_domination | 9.4% | 3 | 32 | 3_561_666_942 |
| 33 | demo-bots | random_bidder | 3.1% | 1 | 32 | 1_232_571_067 |

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
