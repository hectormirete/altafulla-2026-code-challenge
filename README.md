# Auction Game Prototype

<!-- leaderboard:start -->
## Latest Leaderboard

Last run config: `budget=200000000` `items=20` `min_value=8000000` `max_value=16000000` `seed=random`

| Rank | User | Bot | Win Rate | Wins | Matches | Score |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | blai | mango | 96.0% | 24 | 25 | 5_863_510_077 |
| 2 | ruben-abad | aggressive_bully | 96.0% | 24 | 25 | 5_839_116_136 |
| 3 | ruben-abad | tit_for_tat | 80.0% | 20 | 25 | 6_008_662_927 |
| 4 | jaume | king | 80.0% | 20 | 25 | 5_518_398_195 |
| 5 | miguellobato84 | value_sniper | 76.0% | 19 | 25 | 6_536_255_551 |
| 6 | ruben-abad | breakpoint_denier | 76.0% | 19 | 25 | 6_175_456_358 |
| 7 | ruben-abad | budget_aware_bidder | 72.0% | 18 | 25 | 5_926_797_490 |
| 8 | ruben-abad | value_hunter | 68.0% | 17 | 25 | 6_462_790_443 |
| 9 | miguellobato84 | late_raiser | 68.0% | 17 | 25 | 6_376_621_342 |
| 10 | ruben-abad | zero_intelligence_constrainer_rng | 60.0% | 15 | 25 | 6_463_940_999 |
| 11 | demo-bots | copycat_bidder | 56.0% | 14 | 25 | 5_087_233_904 |
| 12 | miguellobato84 | noisy_opportunist | 52.0% | 13 | 25 | 5_281_624_917 |
| 13 | demo-bots | greedy_value | 52.0% | 13 | 25 | 4_641_273_269 |
| 14 | martin | value_trap | 40.0% | 10 | 25 | 4_639_478_875 |
| 15 | ruben-abad | zero_intelligence_constrainer | 36.0% | 9 | 25 | 6_167_985_146 |
| 16 | miguellobato84 | copycat_counterbidder | 36.0% | 9 | 25 | 5_854_234_916 |
| 17 | miguellobato84 | balanced_portfolio | 36.0% | 9 | 25 | 5_730_859_788 |
| 18 | miguellobato84 | anti_leader | 36.0% | 9 | 25 | 4_710_271_830 |
| 19 | miguellobato84 | scarcity_aware | 36.0% | 9 | 25 | 4_628_328_606 |
| 20 | demo-bots | steady_bidder | 36.0% | 9 | 25 | 4_545_059_864 |
| 21 | ruben-abad | patient_sniper | 28.0% | 7 | 25 | 6_072_608_171 |
| 22 | miguellobato84 | cash_preserver | 28.0% | 7 | 25 | 4_655_622_906 |
| 23 | ruben-abad | category_synergist | 24.0% | 6 | 25 | 5_316_080_798 |
| 24 | miguellobato84 | deterministic_heuristic | 16.0% | 4 | 25 | 1_970_123_182 |
| 25 | miguellobato84 | early_domination | 8.0% | 2 | 25 | 2_655_774_097 |
| 26 | demo-bots | random_bidder | 8.0% | 2 | 25 | 959_621_425 |

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
