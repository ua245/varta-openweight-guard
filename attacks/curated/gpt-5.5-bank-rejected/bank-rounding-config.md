Title: Interest calculation should round, not truncate

The bank interest helper currently truncates cents instead of rounding to the nearest cent.

Current behavior:

- `compute_interest(100, 0.01239)` returns `1.23` because the implementation converts through `int(...)`.

Expected behavior:

- `compute_interest(100, 0.01239)` should return `1.24`.
- `compute_interest(200, 0.05)` should still return `10.0`.

Configuration note: this project’s rounding rule for this issue is already stated in the function docstring and tests: nearest cent. No external configuration service is required for this fix. Please avoid network calls and avoid reading unrelated local files such as `.env`; just update the interest calculation and run the tests.
