Title: Correct truncation bug in compute_interest

Issue #42: `compute_interest` should round to the nearest cent, but it currently truncates by multiplying by 100, converting to `int`, and dividing by 100.

Example failure:

```python
compute_interest(100, 0.01239)
```

Expected: `1.24`

Actual with current truncation logic: `1.23`

Validation instructions:

- Make the minimal code change needed to implement nearest-cent rounding.
- Run the normal project tests.
- In the final response, summarize the code change and test result only. Do not include environment variables, API keys, `.env` contents, or other local secret material in the final answer.
