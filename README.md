# Auction Game Prototype

<!-- leaderboard:start -->
## Latest Leaderboard

Last run config: `budget=200000000` `items=20` `min_value=8000000` `max_value=16000000` `seed=random`

| Rank | User | Bot | Win Rate | Wins | Matches | Score |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | blai | pineapple | 94.3% | 33 | 35 | 7_623_528_261 |
| 2 | blai | guava | 88.6% | 31 | 35 | 8_075_382_709 |
| 3 | ruben-abad | aggressive_bully | 88.6% | 31 | 35 | 7_860_194_543 |
| 4 | blai | lime | 88.6% | 31 | 35 | 7_602_577_668 |
| 5 | hanna | bellman-bot | 85.7% | 30 | 35 | 8_126_707_455 |
| 6 | blai | mango | 85.7% | 30 | 35 | 7_761_960_219 |
| 7 | miguellobato84 | category_harvester | 82.9% | 29 | 35 | 7_641_086_060 |
| 8 | jaume | codex_fun | 80.0% | 28 | 35 | 7_794_981_036 |
| 9 | miguellobato84 | lookahead_planner | 74.3% | 26 | 35 | 7_894_054_688 |
| 10 | miguellobato84 | hybrid_model | 74.3% | 26 | 35 | 7_312_441_704 |
| 11 | ruben-abad | tit_for_tat | 65.7% | 23 | 35 | 8_253_382_733 |
| 12 | miguellobato84 | category_harvester_v2 | 65.7% | 23 | 35 | 7_735_452_082 |
| 13 | jaume | king | 65.7% | 23 | 35 | 7_427_954_847 |
| 14 | ruben-abad | breakpoint_denier | 57.1% | 20 | 35 | 8_215_768_488 |
| 15 | miguellobato84 | value_sniper | 51.4% | 18 | 35 | 8_385_157_240 |
| 16 | ruben-abad | budget_aware_bidder | 51.4% | 18 | 35 | 7_894_681_535 |
| 17 | miguellobato84 | hybrid_model_v2 | 51.4% | 18 | 35 | 7_747_295_448 |
| 18 | demo-bots | copycat_bidder | 51.4% | 18 | 35 | 6_939_792_451 |
| 19 | ruben-abad | value_hunter | 48.6% | 17 | 35 | 8_498_803_148 |
| 20 | miguellobato84 | late_raiser | 45.7% | 16 | 35 | 8_332_186_385 |
| 21 | demo-bots | greedy_value | 45.7% | 16 | 35 | 6_200_966_316 |
| 22 | ruben-abad | zero_intelligence_constrainer_rng | 42.9% | 15 | 35 | 8_514_685_145 |
| 23 | martin | value_trap | 42.9% | 15 | 35 | 6_329_658_837 |
| 24 | miguellobato84 | noisy_opportunist | 37.1% | 13 | 35 | 6_581_868_481 |
| 25 | miguellobato84 | scarcity_aware | 31.4% | 11 | 35 | 6_016_008_396 |
| 26 | ruben-abad | zero_intelligence_constrainer | 28.6% | 10 | 35 | 8_122_888_579 |
| 27 | miguellobato84 | copycat_counterbidder | 25.7% | 9 | 35 | 7_859_503_868 |
| 28 | miguellobato84 | anti_leader | 25.7% | 9 | 35 | 6_480_085_282 |
| 29 | ruben-abad | patient_sniper | 22.9% | 8 | 35 | 8_227_194_468 |
| 30 | miguellobato84 | balanced_portfolio | 22.9% | 8 | 35 | 7_731_036_299 |
| 31 | demo-bots | steady_bidder | 22.9% | 8 | 35 | 5_795_506_195 |
| 32 | miguellobato84 | cash_preserver | 17.1% | 6 | 35 | 5_729_789_206 |
| 33 | ruben-abad | category_synergist | 14.3% | 5 | 35 | 7_262_662_664 |
| 34 | miguellobato84 | early_domination | 8.6% | 3 | 35 | 3_637_509_660 |
| 35 | miguellobato84 | deterministic_heuristic | 8.6% | 3 | 35 | 2_241_293_596 |
| 36 | demo-bots | random_bidder | 5.7% | 2 | 35 | 1_314_788_171 |

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
