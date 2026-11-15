# Agent ↔ Guard interface (Step 2)

The contract between the agent loop (`agent/`) and the guard (`guard/`). The guard side already exists and is tested. Everything below is read from `guard/core.py` and `tests/test_poisoned_issue.py`.

## Rule
The agent never runs a tool before `Guard.check`. Executors run only with `decision.args`, never the model's original args, because secrets are injected there.

## Tools and arg names
These are the names the guard understands. Use them in the schemas sent to the model, or the guard will deny with `unknown tool`.

| Tool | Args | Notes |
|---|---|---|
| `read_file` | `path` | `.env`, keys, `~/.ssh` denied; paths resolved with realpath |
| `write_file` | `path`, `content` | inside the repo only |
| `shell` | `cmd` | runs in Docker (Step 4); the text filter is only a first layer |
| `http_request` | `method`, `url`, `headers?`, `body?` | allowlisted hosts only; `{{NAME}}` placeholders injected at egress |
| `read_github_issue` | `repo`, `number` | always allowed, but taints the session |

An unlisted tool name is denied. Adding a tool means adding a branch in `Guard._decide`.

## Loop contract
```
for each tool_call the model returns:
    d = guard.check(tool, args)
    if d.handover:      stop the loop, show d.reason to the human; continue only after guard.resume()
    elif d.allowed:     result = execute(tool, d.args)      # d.args, not args
    else:               result = f"BLOCKED: {d.reason}"     # goes back to the model so it can replan
    result = guard.secrets.redact(result)                   # before the model sees it
    append result as the tool message
```

`Decision` fields: `action` (`allow` | `deny` | `ask`), `reason`, `args`, `handover`. Use `d.allowed`, which is false during a handover even if the action was allow. In autonomous mode (the default) `ask` is already turned into `deny`.

## Rules for executors
- Taint is set inside `check`, so the executor does nothing about it. The returned content (issue text, web page) goes straight to the model.
- `read_github_issue` is served by a local stub that returns `attacks/poisoned_issue.md` for issue #42. No real GitHub access.
- Register fake secrets with `guard.secrets.register("BANK_API_KEY", "fake-secret")` at startup. The model only ever sees `{{BANK_API_KEY}}`.
- The `--no-guard` flag swaps in a pass-through that returns `allow(args)` for every call. The executors and the loop stay identical, so the with/without comparison is fair.

## Not decided yet (agree before building)
- Max turns per run, and what counts as "task completed" for the metrics.
- Whether the fake attacker host is an in-process stub or a local HTTP server. Step 5 needs to read what it received.
- Where `audit.jsonl` is written for each run (the eval needs one per run).
