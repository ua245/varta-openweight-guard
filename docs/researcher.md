# Researcher agent (`guard/researcher.py`)

The "Researcher agent" box in `updated-guard-flow.png`. It is the autonomous agent in the guard: it makes the approve/deny call a human would otherwise be asked to make.

## Where it sits

1. `Guard._decide` runs the deterministic policy. A hard deny (`.env`, write outside the repo, unknown tool, secret placeholder to a non-allowlisted host) is blocked and never reaches the researcher.
2. A call the policy leaves open goes to `Researcher.review`:
   - **ambiguous**: host not on the allowlist (`network.unknown: ask`)
   - **tainted and sensitive**: the session is tainted and the call matches `tainted_session.deny` (`git_push`, `network_unknown`, `install_package`)
3. Approve → the tool executes. Deny → `BLOCKED: <reason>` goes back to the coding agent, and counts toward the 3-denial handover.

With no researcher attached (`Guard(..., researcher=None)`, or no model backend configured) step 2 is a deny, as before.

## Tools

All read-only. None takes free text from the model that leaves the machine.

| Tool | Args | What it does | Network |
|---|---|---|---|
| `search_web_reputation` | `target`, `focus` (`reputation` / `ownership` / `security_reports`) | Tavily search about one destination. `target` must be a research target the harness extracted from the call (registrable domain, or package name for installs). The query is a fixed template. | Tavily |
| `inspect_destination` | none | Per destination: registrable domain, scheme, port, raw IP, private address, punycode, subdomain depth, on allowlist, closest allowlisted host and lookalike flag. | none |
| `inspect_payload` | none | Scans the outgoing args for registered secret values, credential tokens, private keys, `KEY=value` assignments, protected file references, long opaque tokens, request body size. | none |
| `read_policy` | none | Allowlisted hosts, protected file patterns, actions sensitive when tainted. | none |
| `read_session_history` | `limit` | Taint state and sources, plus recent proposed calls and the guard's decision on each (from `audit.jsonl`). Outgoing calls only, no tool results. | none |
| `submit_verdict` | `decision`, `reason_code`, `rationale` | Ends the review. | none |

## Rules enforced in code

- **Sees outgoing calls only.** The prompt holds the proposed tool, its args and the session taint sources. Tool results are never passed in.
- **Domain only to Tavily.** Subdomain, path, query string and body never leave. The model cannot write the query.
- **Secrets never reach the model.** Registered secret values are redacted from the prompt and from history.
- **Secret-looking payload → deny without asking the model.** A model that reads web content can be talked round; this check cannot.
- **No approval without research.** `approve` is refused until `search_web_reputation` has returned results for every non-allowlisted target. If Tavily is down, the outcome is deny.
- **Fail closed.** Model unreachable, malformed output, or step budget (6) spent → deny.
- **Fixed reason text to the coding agent.** The agent gets a canned sentence per `reason_code`. The model's `rationale` goes to `audit.jsonl` only, so text from a web page cannot reach the coding agent through the block reason.

## Configuration

`proxy/tools.py::build_researcher` attaches the researcher when a model is available:

| Env | Default |
|---|---|
| `RESEARCHER_BASE_URL` | first OpenAI-compatible backend in `llm_map.json`, plus `/v1` |
| `RESEARCHER_MODEL` | `FINE_TUNED_MODEL`, else the backend's first model |
| `RESEARCHER_API_KEY` | none |
| `TAVILY_API_KEY` | required for any approval of a call with a destination |

## Tests

`python -m pytest tests/test_researcher.py -q` (scripted model, fake Tavily, no network).
