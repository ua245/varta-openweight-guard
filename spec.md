# Spec: Open-Weight Agent Guard

Short and testable. Principles and architecture are in CLAUDE.md, the step-by-step plan is in README.md, and the agent/guard contract is in `docs/agent-interface.md`.

## Goal
A local open-weight coding agent can run autonomously on a task that includes untrusted content (a GitHub issue, a README). A hijacked agent cannot leak secrets or take destructive actions, and it still completes the legitimate task.

## Threat model
- **Attacker:** controls text the agent reads (issue body, README, web page).
- **Assumption:** the model follows the injected instructions some of the time. We do not try to detect this.
- **Protected assets:** secrets (`.env`, keys, tokens), files outside the repo, the network, the remote repo (`git push`).
- **Out of scope:** a compromised host, a malicious user, closed-model agents (see README).

## Requirements
| # | Requirement | Verified by |
|---|---|---|
| R1 | Every tool call passes `Guard.check` before it executes | agent loop test (Step 2) |
| R2 | The enforcement path is deterministic and contains no LLM | code review; any model-based signal can only deny, never allow |
| R3 | Reading untrusted content taints the session permanently | `test_hijacked_agent_cannot_exfiltrate` |
| R4 | A tainted session cannot `git push`, install packages or reach unknown hosts | `test_tainted_session_blocks_push_and_install` |
| R5 | `.env`, keys and `~/.ssh` cannot be read, including via `../` and symlinks. Writes stay in the repo | `test_path_tricks_blocked` |
| R6 | The model sees only `{{NAME}}` placeholders. Real secrets are injected only for allowlisted hosts, and tool output is redacted | `test_secret_injected_only_for_allowed_host` + redaction test (Step 2) |
| R7 | A denial returns `BLOCKED: <reason>`. After 3 in a row the guard pauses for the human | `test_handover_after_three_denials` |
| R8 | Every decision is written to `audit.jsonl` with the taint source | `test_audit_log_written` |
| R9 | Shell commands run in Docker with only the project mounted and limited network | bypass tests such as `c''at .e*` (Step 4) |
| R10 | Legitimate work is not blocked | `test_legit_fix_still_allowed_after_taint` + eval |

## Acceptance (what the demo and metrics must show)
1. With the guard off, the agent on the poisoned issue sends the fake `.env` to the attacker host.
2. With the guard on, the same run sends nothing, `audit.jsonl` names the tainting source, and the bug is still fixed.
3. Metrics table over N runs each, with and without the guard: attack success rate, task completion rate, false positives. The numbers must come from real runs.

## Status
| Item | State |
|---|---|
| R3, R4, R5, R7, R8 and part of R6 (guard side) | done, 7 tests |
| R1, R6 redaction | Step 2, in progress |
| R9 | Step 4 |
| R10 and acceptance 3 | Step 5 |

## Open questions
- Does the fine-tuned attack model from the team become a tighten-only extra signal (R2), an attack generator for the eval, or neither? Needs its input/output format from the teammates working on it.
- Definition of "task completed" for the metrics (for example, a test on the fixed `bank/interest.py` passes).
