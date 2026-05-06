# Andre Optimizer

## Summary

This directory contains score-differential value bots. They estimate both
sides' benefit from the current item, then bid only when the price is still
useful for their own score or expensive enough to deny useful value from the
competing side.

## Bots

- `aab_low_opener.py`: best current legal-field performer. It opens lower than
  the base optimizer, which makes reactive value bidders either buy at less
  attractive category timing or stop collecting enough value.
- `aaa_optimizer.py`: conservative baseline score-differential optimizer.
- `aad_balanced_opener.py`: middle opener pressure.
- `aac_high_opener.py`: higher opener pressure. Useful against some slow
  value bidders, weaker against strict budget-aware bidding.
- `optimizer.py`: more aggressive experimental optimizer.

## Value Model

The bot estimates its own item value as:

```text
item value
+ my marginal category bonus
+ future option value for more items in this category
+ small endgame pressure
```

It also estimates the competing side's value from the same item. In the final
round, it is more willing to deny profitable items because there are no more
rounds for the price to move.

## Budget Pacing

The bot keeps a rough reserve for future rounds. It spends more on high-value
items and less on low-value items, but it still keeps enough budget for later
category opportunities.

## Round Decisions

- Round 1: opens below its estimated ceiling.
- Round 2: raises only if the required bid is still below the ceiling.
- Round 3: applies a stronger denial value, then raises only if the required
  bid is still below the ceiling.

The bots also record whether the competing side is overpaying or repeatedly
raising. If that happens, they become less willing to chase and try to make
future items more expensive without exceeding their own ceiling.

## Why Low Opener Works

The low-opener variant is designed for left-side matchups where the competing
side can see and react to our opening bid. Opening too high gives that side a
clear target to beat by one increment. Opening lower keeps our budget flexible
and makes the competing side's follow-up decisions less profitable over the
whole slate.
