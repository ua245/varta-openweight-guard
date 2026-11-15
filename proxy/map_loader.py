"""Load Step-1 llm_map.json for the proxy."""
from __future__ import annotations

import json
from pathlib import Path


def default_map_path() -> Path:
    # proxy/ → repo root
    return Path(__file__).resolve().parent.parent / "llm_map.json"


def load_llm_map(path: Path | None = None) -> dict:
    p = path or default_map_path()
    if not p.exists():
        return {
            "generated_at_unix": 0,
            "hostname": "unknown",
            "proxy_notice": (
                "No llm_map.json yet. Run Step 1: "
                "cargo run --manifest-path llm-map/Cargo.toml"
            ),
            "endpoints": [],
            "missing": True,
            "path": str(p),
        }
    data = json.loads(p.read_text(encoding="utf-8"))
    data["missing"] = False
    data["path"] = str(p)
    return data


def pick_backend(llm_map: dict, model: str | None = None) -> dict | None:
    """Choose an OpenAI-compatible backend from the map. Prefer one that lists `model`."""
    endpoints = [
        e for e in llm_map.get("endpoints", []) if e.get("openai_compatible") and e.get("base_url")
    ]
    if not endpoints:
        return None
    if model:
        for e in endpoints:
            if model in (e.get("models") or []):
                return e
    return endpoints[0]
