# CategoryValueBot

## Summary

This is the simple Andre bot. It tries to buy items only when the price is still
below the score value it expects to get back.

For each item, it estimates:

```text
item value + extra category bonus + 2,000,000
```

Then it bids below that estimate and only raises if the new price still fits
inside it. The bot does not try to guess the whole future auction. It only asks:
"if I win this item now, how much does my score improve?"

It also has one small tactical response when the competing opening bid is just
above item value: it raises once, then becomes careful again.

That one raise is a controlled test. It spends at most one tactical raise, then
returns to the normal value ceiling instead of chasing expensive bids.

## How It Works

### Item Value

The bot calculates the category bonus it has now, then calculates the category
bonus it would have after winning the current item. The difference is the
`extra category bonus`.

- The `2,000,000` buffer is a small tactical margin. Since a valid raise usually
  needs `1,000,000`, this gives the bot room to beat one reasonable final raise
  while still staying close to the item's real value. It also covers small
  category or denial upside that the simple formula may not fully capture.

### Fair-Opener Test

If the competing opening bid is between:

```text
item.value + 800,000
and
item.value + 1,200,000
```

the bot treats the price as just above fair value. It raises once by the
minimum valid increment. The bot only performs this test once per match so it
does not keep raising without a value limit.

## Round Decisions

- Round 1: calculates the item's estimated value and opens `1,000,000` below
  that number. This leaves room for one valid raise later.
- Round 2: usually keeps the same bid. If the competing opening bid is around
  `item.value + 1,000,000`, specifically between `item.value + 800,000` and
  `item.value + 1,200,000`, it raises once. This is a one-time probe around
  fair value, then the bot goes back to careful bidding.
- Round 3: raises only if beating the competing bid still costs less than the
  bot's estimated value for the item. Otherwise, it stops at its current bid.

## Goal

Stay simple, avoid obviously bad overpays, and still account for category bonus
instead of bidding only on raw item value.
