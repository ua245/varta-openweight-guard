"""Proxy tool gate uses the same Guard — blocked exfil still fails closed."""
from pathlib import Path

from proxy.tools import build_guard, execute_tool

ROOT = Path(__file__).resolve().parent.parent


def test_proxy_blocks_env_after_poisoned_issue():
    guard = build_guard(ROOT, audit_path="audit_proxy_test.jsonl")
    # Taint via untrusted source
    r1 = execute_tool(guard, "read_github_issue", {"issue": "42"})
    assert r1["ok"] and not r1["blocked"]
    assert "BLOCKED" not in r1["content"]

    r2 = execute_tool(guard, "read_file", {"path": ".env"})
    assert r2["blocked"]
    assert r2["content"].startswith("BLOCKED:")


def test_proxy_allows_legit_read_inside_repo():
    guard = build_guard(ROOT, audit_path="audit_proxy_test.jsonl")
    r = execute_tool(guard, "read_file", {"path": "README.md"})
    assert r["ok"] and not r["blocked"]
    assert "Open-Weight Agent Guard" in r["content"]
