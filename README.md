<img width="2051" height="544" alt="VARTA" src="https://github.com/user-attachments/assets/66fd0bb7-ca5e-4769-aeaa-fbfd57343f3e" />

# VARTA — Open-Weight Agent Guard

Open-weight coding agents ship with no safety layer. VARTA gives a local coding agent the
protections closed models get by default, so it can run **autonomously** without being hijacked
by prompt injection.

**Prevention, not detection.** We never try to spot the injection — a good one looks benign. We
assume the model *will* be fooled, and make sure a fooled agent cannot do damage.

---

## How it works

Every tool the agent proposes (`read_file`, `write_file`, `shell`, `http_request`,
`read_github_issue`, `tavily_search`, …) passes through one checkpoint, `Guard.check(tool, args)`.
There are three layers; only the first makes security decisions on its own.

![Guard pipeline for every tool call](docs/guard-pipeline.png)

**Layer 1 — deterministic policy (plain code, no LLM).** Rules from `guard/policy.yaml`:

- **File boundary** — paths resolved with `realpath` (blocks `../` and symlinks). `.env`, `*.pem`,
  `~/.ssh` are never readable; writes only inside the repo.
- **Network allowlist** — only listed hosts are reachable.
- **Session taint** — set the moment the agent reads anything outside the trusted list (a GitHub
  issue, a web page, an external file) and never resets. A tainted session can't reach unknown
  hosts, `git push`, or install packages.
- **Secrets as placeholders** — the model only ever sees `{{BANK_API_KEY}}`; the real value is
  injected at egress, and only for allowlisted hosts.
- **Docker shell** — every `shell`/`run_tests` runs in a throwaway container: only the project
  mounted, secret files masked, `--network none`, read-only root, non-root, resource-limited. Text
  filtering is just a fast first pass; the container is the real boundary, so `c''at .e*` reaches
  nothing.

**Layer 2 — fine-tuned reviewer (the "researcher agent").** When the policy can't auto-decide a
call — an unknown host on a clean session, or a tainted-and-sensitive action — it escalates to a
**fine-tuned model** instead of a human, so the agent stays autonomous. The reviewer investigates
the *outgoing call only* with read-only tools (destination inspection, payload secret-scan, web
reputation via Tavily) and returns approve/deny. It can only decide inside this gray zone: it can
**never** unlock reading a secret or sending data out — those stay hard-denied in code. It fails
closed (unreachable model, bad output, or budget spent → deny).

**Layer 3 — content detector (optional).** The same fine-tuned model can also flag a tool result
as a likely injection. It can only *tighten* (taint + warn), never approve.

A denied call returns `BLOCKED: <reason>` to the agent so it can replan, and every decision is
written to an audit log the agent can't read.

---

## Quick start

```bash
git clone <this repo> && cd imperial_hackathon_submission_-projectname-_1
pip install -r requirements.txt            # only pyyaml (+ pytest); API calls use the stdlib
cp .env.example .env                        # then fill in your keys (see below)
python3 -m pytest -q                        # sanity check — the guard's test suite
```

You need an **OpenAI-compatible model endpoint with tool calling** for the coding agent
(GPT-OSS 20B via llama.cpp, or `gemma4:e2b` via Ollama, or vLLM/SGLang). Point the agent at it
with `AGENT_BASE_URL` / `AGENT_MODEL`, or the `--base-url` / `--model` flags.

### Keys (`.env`, git-ignored)

| Variable | Used for |
|---|---|
| `ADAPTION_API_KEY` | the fine-tuned reviewer / detector (Adaption Labs). Without it, Layer 1 runs alone. |
| `TAVILY_API_KEY` | the reviewer's web-reputation tool (only the domain is ever sent). |
| `AGENT_BASE_URL`, `AGENT_MODEL`, `AGENT_API_KEY` | the coding agent's model endpoint. |

---

## Try it

**The attack, with and without the guard** — same task, same poisoned issue:

```bash
python3 -m agent.run --model gemma4:e2b --no-guard --issue poisoned_issue_v3.md   # key leaks
python3 -m agent.run --model gemma4:e2b           --issue poisoned_issue_v3.md   # blocked, bug still fixed
```

Each run uses a fresh temp copy of `demo_repo/` with a fake `.env` and a local fake "attacker"
server that records what it receives. The summary reports whether the secret reached the attacker,
the model's context, or the final answer, and whether the tests pass.

**Challenge the fine-tuned reviewer** on safe and dangerous links (approve vs deny):

```bash
python3 -m eval.researcher_bench
```

**With the fine-tuned reviewer wired into a full run:**

```bash
python3 -m agent.run --model gemma4:e2b --researcher-model adaption --remote-repo strong
```

**Metrics** (attack success, task completion, false positives — N runs with and without the guard):

```bash
python3 -m eval.run_attacks --model gemma4:e2b --scenarios v3 remote legit --n 5
```

**Check a model endpoint** is reachable and does tool calling: `python3 -m agent.check`.

### Interactive web demo

`demo_web/index.html` is a self-contained page that replays **real captured runs** in three steps —
no guard, guard, and the fine-tuned reviewer judging labelled safe/dangerous links with its live
tool calls. Open it in any browser, or see `docs/DEMO_SCRIPT.md` for the 2-minute walkthrough.

---

## Models & services

| Role | What we used |
|---|---|
| Coding agent (open-weight, local) | **GPT-OSS 20B** (llama.cpp, `local-ai/`), or **`gemma4:e2b`** / `qwen2.5vl:7b` via Ollama |
| Fine-tuned reviewer & detector | **Adaption Labs** fine-tuned model (`stack:uvx`), via its Responses API (`guard/adaption_model.py`) |
| Web reputation | **Tavily** search API (`proxy/tavily_client.py`) |

The guard itself is pure Python — no ML dependency in the enforcement path.

---

## Repository layout

| Path | What's inside |
|---|---|
| `guard/` | the guard: `core.py` (checkpoint), one module per protection (`files`, `network`, `shell`, `secrets`, `taint`, `audit`), `researcher.py` (fine-tuned reviewer), `adaption_model.py`, `detector.py`, `sandbox.py` |
| `agent/` | minimal coding-agent loop, tool executors, scenario runner, CLIs (`run`, `check`, `demo`) |
| `proxy/` | the tool-gate harness: OpenAI façade + `/v1/tools/execute` → `Guard.check`, Tavily tools |
| `attacks/` | fake, versioned injection payloads (poisoned issue, repo file, image) |
| `demo_repo/` | the toy project the agent fixes, with a deliberate bug and a fake `.env` |
| `eval/` | `run_attacks.py` (metrics) and `researcher_bench.py` (reviewer accuracy) |
| `demo_web/` | the interactive 3-step web demo |
| `tests/` | the full test suite (`pytest -q`) |
| `local-ai/`, `bank-mail/`, `cview/`, `scripts/` | model-host setup and operator tooling |

---

## Security model

The guard assumes the agent is already compromised. Its job is to bound the blast radius:

- Catastrophic actions (reading secrets, writing outside the repo, exfiltration to an unknown host)
  are **denied in code** and never delegated to any model.
- The fine-tuned reviewer only adjudicates a bounded, policy-defined *gray zone*; the worst an
  injection can get approved there is a soft action (e.g. a package install), never a secret
  leaving.
- Enforcement is a mandatory wrapper, not advice the model may skip.

All payloads in `attacks/` are fake, and no real secrets live in the repo. See `CLAUDE.md` for the
core principles and `docs/` for the demo script, the pipeline diagram, and host compatibility notes.
