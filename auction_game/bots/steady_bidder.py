def choose_bid(state: dict) -> int:
    item_value = int(state["item"]["value"])
    budget = int(state["my_budget"])
    rounds_left = int(state["total_rounds"]) - int(state["round_index"])
    anchor_bid = budget // max(1, rounds_left)
    if item_value >= 18_000_000:
        return min(max(anchor_bid, 16_000_000), budget)
    if item_value >= 14_000_000:
        return min(max(anchor_bid, 12_000_000), budget)
    return min(max(anchor_bid // 2, 6_000_000), budget)
