def choose_bid(state: dict) -> int:
    budget = int(state["my_budget"])
    rounds_left = 8 - int(state["round_index"])
    item_value = int(state["item"]["value"])
    baseline = budget // max(3, rounds_left + 3)
    return min(max(2, item_value - 1, baseline), budget)
