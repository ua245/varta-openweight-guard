"""Tavily Search client for the proxy (Best use of Tavily bounty).

Uses stdlib only. API key from TAVILY_API_KEY (see .env.example).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

TAVILY_SEARCH_URL = "https://api.tavily.com/search"


class TavilyError(RuntimeError):
    pass


def _load_dotenv() -> None:
    """Minimal .env loader (no dependency). Does not override existing env."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def resolve_api_key(explicit: str | None = None) -> str:
    _load_dotenv()
    key = (explicit or os.environ.get("TAVILY_API_KEY") or "").strip()
    if not key or key.startswith("{{"):
        raise TavilyError(
            "TAVILY_API_KEY is not set. Export it or copy .env.example to .env. "
            "Get a key at https://tavily.com"
        )
    return key


def search(
    query: str,
    *,
    api_key: str | None = None,
    max_results: int = 5,
    search_depth: str = "basic",
    topic: str = "general",
    include_answer: bool = True,
) -> dict[str, Any]:
    """POST https://api.tavily.com/search — cited web results for agent research."""
    key = resolve_api_key(api_key)
    payload = {
        "query": query,
        "max_results": max_results,
        "search_depth": search_depth,
        "topic": topic,
        "include_answer": include_answer,
    }
    req = Request(
        TAVILY_SEARCH_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise TavilyError(f"Tavily HTTP {e.code}: {body}") from e
    except URLError as e:
        raise TavilyError(f"Tavily network error: {e}") from e


def format_results(data: dict[str, Any]) -> str:
    lines: list[str] = []
    answer = data.get("answer")
    if answer:
        lines.append(f"Tavily answer: {answer}")
        lines.append("")
    for i, r in enumerate(data.get("results") or [], 1):
        title = r.get("title") or "(no title)"
        url = r.get("url") or ""
        content = (r.get("content") or "").strip()
        published = r.get("published_date") or ""
        lines.append(f"{i}. {title}")
        lines.append(f"   URL: {url}")
        if published:
            lines.append(f"   Published: {published}")
        if content:
            lines.append(f"   {content[:500]}")
        lines.append("")
    return "\n".join(lines).strip() or "(no Tavily results)"
