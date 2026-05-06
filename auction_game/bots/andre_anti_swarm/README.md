# AntiSwarmBot

## Summary

This bot is built to play against category-focused groups.

It is still a normal bidding bot: it only uses the public game state and returns
normal integer bids. The main idea is to value two things at the same time:

```text
my score gain from winning the item
+ part of the category bonus the competing side would gain
```

That makes the bot more willing to contest items when the competing side is
close to growing a category bonus.

## How It Values Items

The base value is:

```text
item value
+ my extra category bonus if I win
+ denial value
+ 500,000 buffer
```

The denial value comes from the competing side's category position. If the
competing side already owns items in the current category, the bot estimates
how much extra category bonus that side would get by winning this item. It uses
part of that amount as denial value.

The denial value gets slightly larger when the competing side already has 2 or
3 items in the category, because those counts are close to stronger category
bonus breakpoints.

## Bid Pattern Tracking

The bot also tracks which categories receive high opening bids.

- An opening at or above item value adds strong pressure to that category.
- An opening at or above `75%` of item value adds light pressure.
- If a category has repeated pressure, the bot adds a little more denial value
  on future items in that category.

This lets the bot respond to category focus without needing to know anything
about the file, name, or implementation of the competing entry.

## Round Decisions

- Round 1: opens `1,000,000` below its estimated value.
- Round 2: records the competing opening bid and raises only if the new price
  is still below the estimated value.
- Round 3: applies the same value ceiling again.

The bot does not try to win every item. It tries to make category breakpoints
more expensive while still buying items that are useful for its own score.
