def calc_npv(t, module, current_state, history):
    # Example: NPV needs past cash flows.
    # We can look at the immediate past step in `history` to see how much ore was extracted,
    # multiply by a price constant, and discount it by time.
    if not history:
        return 0.0

    ore_delta = current_state["ore_stock"] - history[-1]["ore_stock"]
    profit = ore_delta * module.config.ore_price
    discounted_profit = profit / ((1 + module.config.discount_rate) ** t)

    # Add to previous NPV
    return history[-1].get("NPV", 0.0) + discounted_profit


def calc_recovery(current_time, module, current_state, history):
    # Retrieve the grades from your current plant state
    f = current_state.get("feed_grade", 0)  # e.g., 2.5% Copper
    c = current_state.get("concentrate_grade", 0)  # e.g., 25.0% Copper
    t = current_state.get("tailings_grade", 0)  # e.g., 0.2% Copper

    # Prevent divide-by-zero errors during startup
    if f == 0 or c == t:
        return 0.0

    recovery = (c * (f - t)) / (f * (c - t))
    return max(0.0, min(recovery * 100, 100.0))  # Clamp between 0 and 100%
