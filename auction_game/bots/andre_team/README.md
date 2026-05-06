# Andre Team

## Summary

This is a group of category specialists. Each bot cares most about one category,
like `ai`, `web`, or `cloud`. When an item from its category appears, the bot is
willing to pay more because winning several items from the same category gives a
bonus.

## Bots

- `ai_specialist.py`: focuses on `ai`
- `web_specialist.py`: focuses on `web`
- `brand_specialist.py`: focuses on `brand`
- `cloud_specialist.py`: focuses on `cloud`
- `dev_specialist.py`: focuses on `dev`
- `data_specialist.py`: focuses on `data`

## Category Target

The shared strategy currently uses:

```text
target_items = 4
```

Four items is a useful target because the category bonus reaches `20%`:

```text
1 item  = 0%
2 items = 6%
3 items = 12%
4 items = 20%
5 items = 28%
6+ items = 30%
```

Five items gives a bigger bonus, but it is harder to reach. If the bot assumes
it will win 5 items, it may overpay early and run out of budget before the right
items appear. Four is a more balanced assumption: it gives the bot a meaningful
category premium without making it bid too high on every item.

## How Each Bot Values Items

For its own category, a specialist estimates the item as:

```text
item value
+ bonus value assuming at least 4 items in that category
+ denial value when the competing side already has 2+ items in that category
+ 1,500,000 specialist premium
```

For other categories, it uses one of two estimates:

```text
item value + 500,000 + denial value
```

or, if the competing side has stayed passive for the first few rounds:

```text
item value - 1,000,000 + denial value
```

The denial value is `8%` of the item value. It is only added when the competing
side already has at least 2 items in the current category. That makes the
specialist slightly more willing to block a category bonus from growing.

The bot also watches the competing bid pattern:

- If the competing side contests normal value bids, the specialist keeps enough
  pressure on off-category items to avoid giving away category bonuses too
  cheaply.
- If the competing side stays passive for the first few rounds, the specialist
  lowers its off-category bids. This keeps those buys score-positive and saves
  budget for the category it actually wants.
- If the competing side repeatedly opens high, the specialist uses a trap
  opener near the expected upper limit. This keeps pressure high without
  blindly raising past the specialist's value estimate.

The exact signals are:

- A high opening is at least `78%` of item value.
- After at least 2 openings, if at least half were high, the specialist treats
  the match as high-opening.
- A value contest is recorded only when the final competing bid reaches our
  current bid and is at least `70%` of item value. This avoids treating invalid
  or too-low raises as real pressure.
- The high-opening trap uses approximately `110%` of item value minus the
  minimum raise increment.
- If the competing side accepts an expensive raise above about `112%` of item
  value, the specialist can switch to a stronger trap opener around `116%` of
  item value minus the minimum raise increment.

## Round Decisions

- Round 1: opens below its estimated value. After repeated high openings or an
  expensive accepted raise, it may open closer to the expected upper limit.
- Round 2: records whether the competing opening bid was cheap, around value,
  or high. If that bid is around `item.value + 1,000,000`, it raises once as a
  controlled fair-value probe.
- Round 3: raises only if the new price is still below its estimated value, and
  records whether value bids are actively being contested.

## Why Not Always Target 5?

Targeting 5 can be better if the specialist reliably wins many items in its category.
But with 20 total items and 6 categories, each category usually appears only 3
or 4 times in a default tournament. That makes 5 an optimistic target. For the
default game, 4 is usually the safer choice.
