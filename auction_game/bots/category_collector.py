def choose_bid(state: dict) -> int:
    budget = int(state["my_budget"])
    item = state["item"]
    my_items = state["my_items"]
    same_category = sum(1 for entry in my_items if entry["category"] == item["category"])
    rounds_left = int(state["total_rounds"]) - int(state["round_index"])
    base_bid = max(int(item["value"]), budget // max(1, rounds_left))
    if same_category >= 1:
        base_bid += int(item["value"] * 0.15)
    elif int(item["value"]) >= 16_000_000:
        base_bid += int(item["value"] * 0.08)
    return min(base_bid, budget)
