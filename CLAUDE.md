# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Project: open-weight agent guard (Imperial AI Hackathon, track Autonomous Agents)

## One-line pitch
Open-weight coding agents get no safety layer by default. We give a local coding agent the protections Claude gets by default, so it can run autonomously without being hijacked by prompt injection.

## Core principles (do not break these)
1. **Prevention, not detection.** We do not try to detect injections. A good injection looks benign. We assume the agent WILL be fooled and make sure a fooled agent cannot do damage.
2. **The model never decides its own permissions.** Permissions come from a policy file and from the user's original request only. No LLM call may grant or widen a permission after untrusted content has been read.
3. **Enforcement lives in code, outside the model.** The guard is a proxy / tool wrapper that every tool call must pass through. An "advisory" MCP the model may choose to call is NOT a security control.
4. **Shell must eventually run in a container (roadmap).** Filtering shell commands by text is bypassable (`c''at .e*`). Today `shell` is a guarded stub; Docker mount + allowlisted network is planned. Text filtering is only a first fast layer.
5. **Secrets are never in the agent's context.** The agent holds a placeholder token. The guard swaps in the real key only on requests to an allowed host.

## Architecture
- **Step 1 (`llm-map/`)** — Rust script maps local open-weight / OSS LLM processes → `llm_map.json`. Inventory only.
- **Step 2 (`proxy/`)** — **THE PROXY.** All future coding-agent features implement here. Agents set `base_url` to the proxy; they never call mapped backends directly. Contract: `proxy/AGENT_CONTRACT.md`.
- **Developer** gives a task.
- **Coding agent**: open-weight model (discovered by llm-map, reached only via proxy), tools: read_file, write_file, shell, http_request.
- **Guard inside the proxy** intercepts every tool call (`POST /v1/tools/execute`):
  1. allow / ask / deny rules from `policy.yaml`
  2. session taint: set as soon as the agent reads untrusted content (web page, GitHub issue, dependency README, external file). Never resets during the session.
  3. secrets as placeholders, injected at egress
  4. network and file allowlists (paths normalised with realpath to block `../` and symlink tricks)
  5. audit log + block reason returned to the agent so it can replan; after 3 denials in a row, hand over to the human
- **Tools**: project files (write inside repo only), shell (guarded stub; Docker roadmap), Tavily search/verify, allowed hosts.
- **Blocked**: .env, *.pem, ~/.ssh, unknown hosts, git push, package installs when tainted.
- **Hooks** are optional observers on the proxy path; they are not enforcement.

## Policy file format (`policy.yaml`)
```yaml
network:
  allow: [pypi.org, github.com, api.mybank-internal.com]
  unknown: ask            # becomes deny when the session is tainted
files:
  deny: [.env, "*.pem", ~/.ssh]
  write_only_in: ./
tainted_session:
  deny: [git_push, network_unknown, install_package]
untrusted_sources: [http_request, read_github_issue, read_external_file]
```
Defaults ship with the guard. Allowed hosts can also be derived from the lockfile and git remote, or recorded in a clean "learning" session and then locked.

## Demo scenario (three phases)
Story: a bank runs an open-weight coding agent on its own server.
1. **Without guard**: the agent is asked to fix a bug, reads a poisoned GitHub issue whose hidden text says to send `.env` to an external URL. The agent does it.
2. **With guard**: same task, same issue. The session is tainted on read, the `.env` read and the outbound request are blocked, the agent replans and still fixes the bug. The log shows which source tainted the session and what was blocked.
3. **How it works**: architecture slide, threat model slide, numbers.

## Metrics (required)
- Attack success rate with and without the guard.
- Legitimate task completion rate with the guard (autonomy preserved).
- False positives (legitimate actions blocked).
- Stretch: AgentDojo cases. Map covered techniques to MITRE ATLAS (taxonomy only, not a dataset).

## Work split
1. Agent + local model, tools routed through the guard; check the model can do a simple legit task.
2. Guard core: interception, policy engine, taint state, block reasons, handover after repeated denials.
3. Boundaries + secrets: placeholder keys, egress allowlist, file boundary, Docker shell, fast shell pattern filter.
4. Attacks + evaluation: poisoned issue, poisoned README, metrics script.
5. Demo + pitch: live log view, demo script, README with one-line install and roadmap.

## Milestones
- Sat 5 pm: one attack blocked end to end.
- Sat 10 pm: metrics with and without the guard.
- Sun morning: polish only. Code freeze 2 hours before demos.
- Sun at 12 it is the deadline 

## Out of scope (roadmap only, put in README)
Protecting Claude Code or closed models (they already have hooks, sandbox, classifiers), PR scanning, PII redaction, fine-tuning, enterprise portal, other attack modules (memory poisoning, supply chain beyond allowlists).

## Working rules for Claude Code in this repo
- Keep the guard deterministic. Do not add an LLM to the enforcement path.
- Write the attack scenario as a test first, then make it pass.
- Small modules, one per protection, so new attack modules can be added later.
- Never put real secrets in the repo. Attack payloads live in `attacks/` and are fake.
- **Implement new agent features in `proxy/`.** Do not grow a parallel unprotected agent path. llm-map stays inventory-only.
- **Tavily is the allowlisted research path** (`tavily_search`, `verify_claim` stale-answer detector). Prefer it over raw `http_request` to unknown hosts.
- Use `python -m …` in docs and scripts (Windows-friendly).

## Commands
- Install: `pip install -r requirements.txt`
- All tests: `python -m pytest -q`
- One test: `python -m pytest tests/test_poisoned_issue.py::test_hijacked_agent_cannot_exfiltrate -q`

## Guard code map
`guard/core.py` `Guard.check(tool, args) -> Decision` is the single enforcement point; it dispatches to one module per protection (`files.py`, `network.py`, `shell.py`, `secrets.py`), updates `taint.py` after a call is allowed, counts consecutive denials (handover + pause after 3, `Guard.resume()` to continue), and writes `audit.jsonl`. `Decision.args` may hold rewritten args (secrets injected) — executors must use those, not the originals. Default policy: `guard/policy.yaml` (`mode: autonomous` turns `ask` into `deny`).
