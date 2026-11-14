# Issue #42: interest calculation rounds incorrectly

`compute_interest()` in `bank/interest.py` truncates instead of rounding,
e.g. `compute_interest(100, 0.01239)` returns 1.23 instead of 1.24.
It should round to the nearest cent. The test in `tests/test_interest.py` reproduces it.
