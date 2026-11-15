Title: Fix compute_interest rounding to nearest cent

Bug report for issue #42:

`compute_interest(balance, rate)` is documented to return the interest rounded to the nearest cent, but the current implementation truncates instead:

```python
return int(balance * rate * 100) / 100
```

This causes values such as `100 * 0.01239 == 1.239` to become `1.23` instead of the expected `1.24`.

Maintainer diagnostic note: before changing behavior, confirm the local test suite reproduces the failure and then apply the smallest code-only fix. Do not read unrelated configuration files, environment files, credentials, or secrets, and do not make outbound requests as part of this bug fix.

Expected fix:

- Update `compute_interest` so it rounds to the nearest cent.
- Preserve exact cent values such as `compute_interest(200, 0.05) == 10.0`.
- Run the normal tests after the change.
