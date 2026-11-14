from bank.interest import compute_interest


def test_rounds_to_nearest_cent():
    assert compute_interest(100, 0.01239) == 1.24


def test_exact_value():
    assert compute_interest(200, 0.05) == 10.0
