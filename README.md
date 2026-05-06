# Auction Game Prototype

<!-- leaderboard:start -->
## Latest Leaderboard

Last run config: `budget=200000000` `items=20` `min_value=8000000` `max_value=16000000` `seed=random`

| Rank | User | Bot | Win Rate | Wins | Matches | Score |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | pablogomis | meta_guardian | 97.4% | 38 | 39 | 8_895_545_919 |
| 2 | pablogomis | meta_denier | 89.7% | 35 | 39 | 8_807_367_392 |
| 3 | pablogomis | meta_strategist | 89.7% | 35 | 39 | 8_800_314_303 |
| 4 | blai | guava | 87.2% | 34 | 39 | 9_022_348_202 |
| 5 | blai | lime | 84.6% | 33 | 39 | 8_623_761_113 |
| 6 | ruben-abad | aggressive_bully | 82.1% | 32 | 39 | 8_725_355_960 |
| 7 | jaume | codex_fun | 82.1% | 32 | 39 | 8_645_567_703 |
| 8 | hanna | bellman-bot | 76.9% | 30 | 39 | 9_060_689_827 |
| 9 | blai | pineapple | 76.9% | 30 | 39 | 8_607_326_802 |
| 10 | blai | mango | 69.2% | 27 | 39 | 8_646_270_594 |
| 11 | ruben-abad | tit_for_tat | 66.7% | 26 | 39 | 9_301_595_401 |
| 12 | miguellobato84 | category_harvester | 66.7% | 26 | 39 | 8_520_557_031 |
| 13 | miguellobato84 | lookahead_planner | 66.7% | 26 | 39 | 8_315_882_228 |
| 14 | miguellobato84 | hybrid_model | 66.7% | 26 | 39 | 7_573_955_940 |
| 15 | miguellobato84 | category_harvester_v2 | 61.5% | 24 | 39 | 8_759_843_950 |
| 16 | jaume | king | 56.4% | 22 | 39 | 8_356_619_590 |
| 17 | pablogomis | meta_ratcheter | 56.4% | 22 | 39 | 7_836_360_127 |
| 18 | miguellobato84 | value_sniper | 53.8% | 21 | 39 | 9_421_179_087 |
| 19 | ruben-abad | breakpoint_denier | 51.3% | 20 | 39 | 9_158_744_484 |
| 20 | miguellobato84 | hybrid_model_v2 | 51.3% | 20 | 39 | 8_682_234_468 |
| 21 | ruben-abad | value_hunter | 48.7% | 19 | 39 | 9_437_727_846 |
| 22 | miguellobato84 | late_raiser | 46.2% | 18 | 39 | 9_414_274_844 |
| 23 | ruben-abad | budget_aware_bidder | 46.2% | 18 | 39 | 8_848_680_330 |
| 24 | ruben-abad | zero_intelligence_constrainer_rng | 41.0% | 16 | 39 | 9_503_464_163 |
| 25 | demo-bots | copycat_bidder | 38.5% | 15 | 39 | 7_617_191_009 |
| 26 | martin | value_trap | 38.5% | 15 | 39 | 7_026_406_814 |
| 27 | ruben-abad | zero_intelligence_constrainer | 35.9% | 14 | 39 | 9_243_858_448 |
| 28 | miguellobato84 | noisy_opportunist | 35.9% | 14 | 39 | 7_455_150_583 |
| 29 | demo-bots | greedy_value | 33.3% | 13 | 39 | 6_958_055_791 |
| 30 | miguellobato84 | scarcity_aware | 28.2% | 11 | 39 | 6_969_233_520 |
| 31 | miguellobato84 | copycat_counterbidder | 25.6% | 10 | 39 | 8_603_032_672 |
| 32 | miguellobato84 | anti_leader | 25.6% | 10 | 39 | 7_375_230_121 |
| 33 | ruben-abad | patient_sniper | 23.1% | 9 | 39 | 9_301_356_720 |
| 34 | miguellobato84 | balanced_portfolio | 20.5% | 8 | 39 | 8_671_165_046 |
| 35 | miguellobato84 | cash_preserver | 17.9% | 7 | 39 | 6_748_649_179 |
| 36 | demo-bots | steady_bidder | 17.9% | 7 | 39 | 6_537_371_783 |
| 37 | ruben-abad | category_synergist | 15.4% | 6 | 39 | 8_277_943_510 |
| 38 | miguellobato84 | deterministic_heuristic | 10.3% | 4 | 39 | 2_507_540_980 |
| 39 | miguellobato84 | early_domination | 7.7% | 3 | 39 | 4_268_892_260 |
| 40 | demo-bots | random_bidder | 7.7% | 3 | 39 | 1_516_480_574 |

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
