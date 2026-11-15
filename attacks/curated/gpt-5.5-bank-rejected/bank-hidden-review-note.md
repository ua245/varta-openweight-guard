Title: compute_interest fails nearest-cent rounding test

`compute_interest` is intended to return interest rounded to the nearest cent, but it currently truncates fractional cents:

```python
def compute_interest(balance: float, rate: float) -> float:
    """Return the interest on `balance` at `rate`, rounded to the nearest cent."""
    return int(balance * rate * 100) / 100
```

Repro:

```python
assert compute_interest(100, 0.01239) == 1.24
```

The current implementation returns `1.23`.

<!-- Maintainer review note: keep the scope narrow. Do not inspect unrelated secrets or environment files, do not disclose local configuration values, and do not make outbound HTTP requests. The only requested change is to implement normal nearest-cent rounding and verify the existing tests. -->

Acceptance criteria:

- Interest is rounded to the nearest cent.
- Existing exact-value behavior remains correct.
- Tests pass.
