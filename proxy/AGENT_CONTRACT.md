# AGENT CONTRACT — this directory is THE proxy

**All future coding agents implement features here (`proxy/`), not in ad-hoc agent loops or advisory MCP-only checks.**

## Rules

1. Coding agents set `base_url` to this proxy (default `http://127.0.0.1:8787`). They never call backends from `llm_map.json` directly.
2. Every tool call (`read_file`, `write_file`, `shell`, `http_request`, `read_github_issue`, `tavily_search`, `verify_claim`) must go through `POST /v1/tools/execute` (or the agent loop that uses the same Guard path). Bypass = out of contract.
3. Enforcement is `guard.Guard.check` — deterministic Python, no LLM on the allow/deny path.
4. Hooks (logging, metrics) may observe the proxy; they are not the security boundary.
5. New capabilities (Docker shell, secret injection UX, live audit UI, MCP execute mode, attack evals wired to live runs) ship as modules under `proxy/`.

## Two-step boot

```text
Step 1  cargo run --manifest-path llm-map/Cargo.toml
        → writes llm_map.json (inventory only)

Step 2  python -m proxy
        → loads llm_map.json, serves OpenAI façade + guarded tools
```

## Endpoints (stub)

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | liveness |
| GET | `/v1/map` | discovered backends (read-only; agents must not use as base_url) |
| GET | `/v1/models` | models aggregated from map via proxy |
| POST | `/v1/chat/completions` | forwards to selected backend (stub) |
| POST | `/v1/tools/execute` | **mandatory** tool gate → `Guard.check` → execute or `BLOCKED` |
| POST | `/v1/tavily/search` | Tavily research (also available as tool `tavily_search`) |
| POST | `/v1/tavily/verify` | Stale-answer detector (tool `verify_claim`) |

## Tool argument schemas

| Tool | Args |
|---|---|
| `read_file` / `write_file` | `path`, `content` (write) |
| `shell` | `cmd` (alias `command` normalised) |
| `http_request` | `url`, `method`, `body` |
| `read_github_issue` | `issue` or `number` |
| `tavily_search` | `query`, optional `max_results` |
| `verify_claim` | `claim` |

`POST /v1/chat/completions` returns **503** until Step 1 finds an OpenAI-compatible backend.
