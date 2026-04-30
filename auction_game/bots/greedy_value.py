def choose_bid(state: dict) -> int:
    item_value = int(state["item"]["value"])
    budget = int(state["my_budget"])
    rounds_left = int(state["total_rounds"]) - int(state["round_index"])
    target_bid = max(item_value, budget // max(1, rounds_left))
    return min(target_bid, budget)
