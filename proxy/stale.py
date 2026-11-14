"""Stale-answer detector — flagship Tavily bounty feature.

Takes a model/agent claim, searches Tavily for fresh evidence, and returns
FRESH / STALE / UNCERTAIN with cited sources. Deterministic heuristics only
(no LLM on the enforcement path).
"""
from __future__ import annotations

import re
from typing import Any

from proxy.tavily_client import format_results, search

_STOP = {
    "a", "an", "the", "is", "are", "was", "were", "be", "to", "of", "and", "or",
    "in", "on", "for", "with", "that", "this", "it", "as", "at", "by", "from",
}


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if len(w) > 2 and w not in _STOP}


def verify_claim(
    claim: str,
    *,
    api_key: str | None = None,
    max_results: int = 5,
    _search=search,
) -> dict[str, Any]:
    """Verify a claim against live Tavily search. `_search` is injectable for tests."""
    claim = (claim or "").strip()
    if not claim:
        return {
            "verdict": "UNCERTAIN",
            "reason": "empty claim",
            "claim": claim,
            "citations": [],
            "tavily_answer": None,
            "formatted": "",
        }

    data = _search(claim, api_key=api_key, max_results=max_results, include_answer=True)
    answer = (data.get("answer") or "").strip()
    results = data.get("results") or []
    citations = [
        {
            "title": r.get("title"),
            "url": r.get("url"),
            "content": (r.get("content") or "")[:300],
        }
        for r in results
    ]

    claim_toks = _tokens(claim)
    evidence = " ".join([answer] + [(r.get("content") or "") for r in results])
    evid_toks = _tokens(evidence)

    if not evid_toks:
        verdict, reason = "UNCERTAIN", "Tavily returned no usable evidence"
    else:
        overlap = len(claim_toks & evid_toks) / max(len(claim_toks), 1)
        neg = bool(
            re.search(
                r"\b(not|no longer|incorrect|false|outdated|deprecated|former)\b",
                answer.lower(),
            )
        )
        if neg and overlap < 0.55:
            verdict, reason = (
                "STALE",
                "Tavily answer suggests the claim is outdated or incorrect",
            )
        elif overlap >= 0.35:
            verdict, reason = "FRESH", f"claim tokens overlap evidence ({overlap:.0%})"
        else:
            verdict, reason = (
                "STALE",
                f"low overlap with live evidence ({overlap:.0%}); claim may be stale",
            )

    return {
        "verdict": verdict,
        "reason": reason,
        "claim": claim,
        "tavily_answer": answer or None,
        "citations": citations,
        "formatted": format_results(data),
    }
