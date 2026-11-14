"""Guarded tool execution — the only legal tool path for coding agents."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from guard import Guard, load_policy


def build_guard(project_root: str | Path | None = None, audit_path: str = "audit.jsonl") -> Guard:
    root = Path(project_root) if project_root else Path(__file__).resolve().parent.parent
    policy = load_policy(root / "guard" / "policy.yaml")
    return Guard(policy, project_root=str(root), audit_path=str(root / audit_path))


def _normalize_args(tool: str, args: dict) -> dict:
    """Canonicalise aliases so guard + executors agree (cmd vs command)."""
    out = dict(args or {})
    if tool == "shell":
        if "cmd" not in out and "command" in out:
            out["cmd"] = out["command"]
        if "command" not in out and "cmd" in out:
            out["command"] = out["cmd"]
    if tool == "read_github_issue":
        if "number" not in out and "issue" in out:
            raw = str(out["issue"]).lstrip("#")
            try:
                out["number"] = int(raw)
            except ValueError:
                out["number"] = raw
    return out


def execute_tool(guard: Guard, tool: str, args: dict, *, no_guard: bool = False) -> dict:
    """
    Run one tool through Guard.check (unless no_guard for eval baseline only).
    Returns a JSON-serialisable result; denials become BLOCKED messages for the model.
    """
    args = _normalize_args(tool, args)
    if no_guard:
        decision_action = "allow"
        reason = "no-guard baseline"
        effective_args = args
        handover = False
    else:
        decision = guard.check(tool, args)
        decision_action = decision.action
        reason = decision.reason
        effective_args = decision.args if decision.args else args
        handover = decision.handover
        if decision_action != "allow" or handover:
            return {
                "ok": False,
                "blocked": True,
                "handover": handover,
                "content": f"BLOCKED: {reason}",
                "tool": tool,
            }

    try:
        content = _run(tool, effective_args, Path(guard.files.root))
        return {
            "ok": True,
            "blocked": False,
            "handover": False,
            "content": content,
            "tool": tool,
            "decision": decision_action,
            "reason": reason,
        }
    except Exception as e:  # noqa: BLE001 — surface executor errors to the agent loop
        return {
            "ok": False,
            "blocked": False,
            "handover": False,
            "content": f"ERROR: {e}",
            "tool": tool,
        }


def _run(tool: str, args: dict, project_root: Path) -> str:
    if tool == "read_file":
        path = _resolve(project_root, args["path"])
        return path.read_text(encoding="utf-8", errors="replace")
    if tool == "write_file":
        path = _resolve(project_root, args["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(args.get("content", ""), encoding="utf-8")
        return f"wrote {path}"
    if tool == "shell":
        # Roadmap: Docker executor (project mount, allowlisted network). Text filter is first layer only.
        cmd = args.get("cmd") or args.get("command")
        return (
            "SHELL_STUB: command accepted by guard; "
            "Docker executor not wired yet (roadmap). "
            f"cmd={cmd!r}"
        )
    if tool == "http_request":
        return _http(args)
    if tool == "read_github_issue":
        issue = str(args.get("issue") or args.get("number") or "")
        if issue.lstrip("#") == "42":
            poisoned = project_root / "attacks" / "poisoned_issue.md"
            if poisoned.exists():
                return poisoned.read_text(encoding="utf-8")
        return f"(stub) GitHub issue {issue} not found locally"
    if tool == "tavily_search":
        from proxy.tavily_client import TavilyError, format_results, search

        try:
            data = search(
                args["query"],
                max_results=int(args.get("max_results") or 5),
                search_depth=args.get("search_depth") or "basic",
                topic=args.get("topic") or "general",
            )
            return format_results(data)
        except TavilyError as e:
            # Offline / no-key demo path for Autonomous Agents scripted runs
            return (
                f"TAVILY_OFFLINE: {e}\n"
                f"(Set TAVILY_API_KEY for live search.) "
                f"Stub citation for query={args.get('query')!r}: "
                "https://docs.tavily.com — prefer Tavily over raw http_request."
            )
    if tool == "verify_claim":
        from proxy.stale import verify_claim
        from proxy.tavily_client import TavilyError

        claim = args.get("claim") or args.get("query") or ""
        try:
            result = verify_claim(claim)
        except TavilyError as e:
            # Deterministic offline stale detection when key missing (demo / CI)
            evil = "evil-attacker" in claim.lower() or "bank_api_key" in claim.lower()
            result = {
                "verdict": "STALE" if evil else "UNCERTAIN",
                "reason": (
                    "offline heuristic (no TAVILY_API_KEY): "
                    + ("exfil-style claim flagged STALE" if evil else str(e))
                ),
                "claim": claim,
                "tavily_answer": None,
                "citations": [],
                "formatted": "",
                "offline": True,
            }
        return json.dumps(result, indent=2)
    raise ValueError(f"no executor for tool {tool!r}")


def _resolve(project_root: Path, path: str) -> Path:
    p = Path(path)
    if not p.is_absolute():
        p = project_root / p
    return p


def _http(args: dict) -> str:
    url = args["url"]
    method = (args.get("method") or "GET").upper()
    body = args.get("body")
    data = None
    headers = {"User-Agent": "open-weight-agent-guard-proxy/0.1"}
    if body is not None:
        if isinstance(body, (dict, list)):
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        else:
            data = str(body).encode("utf-8")
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=10) as resp:  # noqa: S310 — host allowlisted by guard
            return resp.read().decode("utf-8", errors="replace")
    except HTTPError as e:
        return f"HTTP {e.code}: {e.read().decode('utf-8', errors='replace')}"
    except URLError as e:
        return f"URL error: {e}"
