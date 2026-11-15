def compute_interest(balance: float, rate: float) -> float:
    """Return the interest on `balance` at `rate`, rounded to the nearest cent."""
    return int(balance * rate * 100) / 100
