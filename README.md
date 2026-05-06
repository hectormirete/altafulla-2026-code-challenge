# Auction Game Prototype

<!-- leaderboard:start -->
## Latest Leaderboard

Last run config: `budget=200000000` `items=20` `min_value=8000000` `max_value=16000000` `seed=random`

| Rank | User | Bot | Win Rate | Wins | Matches | Score |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | hanna | bellman-bot | 96.3% | 26 | 27 | 6_539_805_900 |
| 2 | jaume | codex_fun | 96.3% | 26 | 27 | 6_231_629_363 |
| 3 | ruben-abad | aggressive_bully | 92.6% | 25 | 27 | 6_208_971_839 |
| 4 | blai | mango | 85.2% | 23 | 27 | 6_234_034_200 |
| 5 | ruben-abad | tit_for_tat | 74.1% | 20 | 27 | 6_635_352_253 |
| 6 | ruben-abad | breakpoint_denier | 74.1% | 20 | 27 | 6_612_000_099 |
| 7 | jaume | king | 74.1% | 20 | 27 | 5_959_940_043 |
| 8 | miguellobato84 | value_sniper | 66.7% | 18 | 27 | 6_796_138_004 |
| 9 | miguellobato84 | late_raiser | 63.0% | 17 | 27 | 6_892_075_567 |
| 10 | ruben-abad | value_hunter | 59.3% | 16 | 27 | 6_895_320_779 |
| 11 | ruben-abad | budget_aware_bidder | 59.3% | 16 | 27 | 6_338_954_318 |
| 12 | demo-bots | copycat_bidder | 59.3% | 16 | 27 | 5_517_607_567 |
| 13 | ruben-abad | zero_intelligence_constrainer_rng | 55.6% | 15 | 27 | 6_826_470_319 |
| 14 | demo-bots | greedy_value | 48.1% | 13 | 27 | 5_016_143_929 |
| 15 | ruben-abad | zero_intelligence_constrainer | 40.7% | 11 | 27 | 6_545_529_327 |
| 16 | miguellobato84 | scarcity_aware | 40.7% | 11 | 27 | 4_972_715_158 |
| 17 | martin | value_trap | 40.7% | 11 | 27 | 4_832_597_536 |
| 18 | miguellobato84 | noisy_opportunist | 37.0% | 10 | 27 | 5_378_057_099 |
| 19 | miguellobato84 | anti_leader | 37.0% | 10 | 27 | 5_071_794_212 |
| 20 | miguellobato84 | balanced_portfolio | 33.3% | 9 | 27 | 6_154_512_740 |
| 21 | demo-bots | steady_bidder | 33.3% | 9 | 27 | 5_084_616_155 |
| 22 | ruben-abad | patient_sniper | 29.6% | 8 | 27 | 6_524_326_084 |
| 23 | miguellobato84 | cash_preserver | 29.6% | 8 | 27 | 4_941_148_706 |
| 24 | miguellobato84 | copycat_counterbidder | 25.9% | 7 | 27 | 6_050_751_601 |
| 25 | ruben-abad | category_synergist | 14.8% | 4 | 27 | 5_730_375_953 |
| 26 | miguellobato84 | deterministic_heuristic | 14.8% | 4 | 27 | 2_058_887_366 |
| 27 | miguellobato84 | early_domination | 11.1% | 3 | 27 | 3_070_832_238 |
| 28 | demo-bots | random_bidder | 7.4% | 2 | 27 | 1_229_222_333 |

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
