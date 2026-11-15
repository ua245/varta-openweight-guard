def compute_interest(balance: float, rate: float) -> float:
    """Return the interest on `balance` at `rate`, rounded to the nearest cent."""
    # Compute raw interest
    raw = balance * rate
    # Round to nearest cent using round half to even (Python default)
    return round(raw, 2)
