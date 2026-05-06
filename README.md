# Auction Game Prototype

<!-- leaderboard:start -->
## Latest Leaderboard

Last run config: `budget=200000000` `items=20` `min_value=8000000` `max_value=16000000` `seed=random`

| Rank | User | Bot | Win Rate | Wins | Matches | Score |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | ruben-abad | aggressive_bully | 93.8% | 30 | 32 | 7_269_851_461 |
| 2 | hanna | bellman-bot | 87.5% | 28 | 32 | 7_584_505_007 |
| 3 | blai | mango | 87.5% | 28 | 32 | 7_249_046_029 |
| 4 | jaume | codex_fun | 84.4% | 27 | 32 | 7_338_363_501 |
| 5 | miguellobato84 | category_harvester | 81.2% | 26 | 32 | 7_079_819_509 |
| 6 | ruben-abad | tit_for_tat | 78.1% | 25 | 32 | 7_631_718_301 |
| 7 | miguellobato84 | lookahead_planner | 78.1% | 25 | 32 | 7_178_683_354 |
| 8 | miguellobato84 | hybrid_model | 78.1% | 25 | 32 | 6_415_147_358 |
| 9 | miguellobato84 | category_harvester_v2 | 71.9% | 23 | 32 | 7_227_358_043 |
| 10 | ruben-abad | breakpoint_denier | 65.6% | 21 | 32 | 7_699_064_431 |
| 11 | miguellobato84 | value_sniper | 62.5% | 20 | 32 | 8_051_529_690 |
| 12 | ruben-abad | value_hunter | 59.4% | 19 | 32 | 8_032_117_008 |
| 13 | miguellobato84 | hybrid_model_v2 | 59.4% | 19 | 32 | 7_404_694_191 |
| 14 | jaume | king | 59.4% | 19 | 32 | 6_924_808_031 |
| 15 | ruben-abad | budget_aware_bidder | 56.2% | 18 | 32 | 7_389_932_274 |
| 16 | demo-bots | copycat_bidder | 50.0% | 16 | 32 | 6_418_832_765 |
| 17 | demo-bots | greedy_value | 50.0% | 16 | 32 | 5_867_000_511 |
| 18 | ruben-abad | zero_intelligence_constrainer_rng | 46.9% | 15 | 32 | 7_814_667_734 |
| 19 | miguellobato84 | late_raiser | 46.9% | 15 | 32 | 7_798_295_242 |
| 20 | martin | value_trap | 43.8% | 14 | 32 | 5_930_964_713 |
| 21 | miguellobato84 | noisy_opportunist | 40.6% | 13 | 32 | 6_272_745_735 |
| 22 | ruben-abad | zero_intelligence_constrainer | 37.5% | 12 | 32 | 7_707_650_346 |
| 23 | miguellobato84 | scarcity_aware | 31.2% | 10 | 32 | 5_784_935_763 |
| 24 | miguellobato84 | copycat_counterbidder | 28.1% | 9 | 32 | 7_235_201_328 |
| 25 | miguellobato84 | anti_leader | 28.1% | 9 | 32 | 5_563_867_088 |
| 26 | ruben-abad | patient_sniper | 25.0% | 8 | 32 | 7_545_900_816 |
| 27 | miguellobato84 | balanced_portfolio | 25.0% | 8 | 32 | 7_131_060_785 |
| 28 | miguellobato84 | cash_preserver | 21.9% | 7 | 32 | 5_529_806_075 |
| 29 | demo-bots | steady_bidder | 21.9% | 7 | 32 | 4_362_247_973 |
| 30 | ruben-abad | category_synergist | 18.8% | 6 | 32 | 6_760_398_268 |
| 31 | miguellobato84 | deterministic_heuristic | 18.8% | 6 | 32 | 2_692_329_835 |
| 32 | miguellobato84 | early_domination | 9.4% | 3 | 32 | 3_565_846_565 |
| 33 | demo-bots | random_bidder | 3.1% | 1 | 32 | 1_172_455_211 |

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
