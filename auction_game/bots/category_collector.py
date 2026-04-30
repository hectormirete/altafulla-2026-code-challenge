def choose_bid(state: dict) -> int:
    budget = int(state["my_budget"])
    item = state["item"]
    my_items = state["my_items"]
    same_category = sum(1 for entry in my_items if entry["category"] == item["category"])
    base_bid = max(3, int(item["value"]))
    if same_category >= 1:
        base_bid += 4
    elif int(item["value"]) >= 7:
        base_bid += 2
    return min(base_bid, budget)
