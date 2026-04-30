def choose_bid(state: dict) -> int:
    item_value = int(state["item"]["value"])
    budget = int(state["my_budget"])
    return min(item_value + 1, budget)
