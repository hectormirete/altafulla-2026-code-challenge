# Andre Counter Swarm

## Summary

This is a communicating group of category counters. Each bot has one category
where it is most willing to spend, but all of them share a small memory of
category pressure observed during the tournament process.

The goal is to avoid using one bot to solve every category. Instead, the team
spreads that job across six entries:

- `ai_counter.py`: focuses on `ai`
- `web_counter.py`: focuses on `web`
- `brand_counter.py`: focuses on `brand`
- `cloud_counter.py`: focuses on `cloud`
- `dev_counter.py`: focuses on `dev`
- `data_counter.py`: focuses on `data`

## Shared Memory

The shared strategy stores a small profile keyed by the first few opening-bid
patterns it sees in a match.

For each category, the profile records pressure:

- opening at or above item value: strong pressure
- opening at or above `78%` of item value: medium pressure
- opening at or above `50%` of item value: light pressure

Later team members can reuse that profile when they see the same opening
pattern. That lets the swarm adapt faster after one member has already played a
similar match.

## Item Value

For its focus category, a counter estimates:

```text
item value
+ bonus value assuming at least 4 items in the focus category
+ denial value
+ 1,500,000 buffer
```

For other categories, it uses one of two estimates. If the competing side has
been contesting value bids, it estimates:

```text
item value + 500,000 + denial value
```

If the competing side stayed passive for the first few rounds, it becomes more
conservative:

```text
item value - 1,000,000 + denial value
```

## Denial Value

Denial value is intentionally simple. It is only added when the competing side
already has at least 2 items in the current category:

```text
8% of item value
```

Earlier versions used stronger shared-memory denial, but that made the counters
buy too many late items. The current version keeps denial small enough that the
counter still preserves budget.

## Round Decisions

- Round 1: opens `1,000,000` below its estimated value. If the competing side
  has accepted an expensive raise above about `112%` of item value, it may use
  a stronger trap opener around `116%` of item value minus the minimum raise
  increment.
- Round 2: records the opening bid pattern and raises only inside its value
  ceiling. If the opening bid is around `item.value + 1,000,000`, it performs
  one controlled fair-value raise.
- Round 3: applies the same value ceiling again and records whether value bids
  are actively being contested.
