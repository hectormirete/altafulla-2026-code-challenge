def choose_bid(state: dict) -> int:
    item_value = int(state["item"]["value"])
    budget = int(state["my_budget"])
    if item_value >= 8:
        return min(10, budget)
    if item_value >= 6:
        return min(8, budget)
    return min(5, budget)
