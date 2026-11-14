# -*- coding: utf-8 -*-
"""VARTA ASCII loader — shown on every launch.

Source art: assets/varta-logo.html
Scenarios tell the coding LLM what surface is loaded.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass

ASCII_LOGO = r"""
╭╮╱╱╭╮╱╭━━━╮╱╭━━━╮╱╭━━━━╮╱╭━━━╮
┃╰╮╭╯┃╱┃╭━╮┃╱┃╭━╮┃╱┃╭╮╭╮┃╱┃╭━╮┃
╰╮┃┃╭╯╱┃┃╱┃┃╱┃╰━╯┃╱╰╯┃┃╰╯╱┃┃╱┃┃
╱┃╰╯┃╱╱┃╰━╯┃╱┃╭╮╭╯╱╱╱┃┃╱╱╱┃╰━╯┃
╱╰╮╭╯╱╱┃╭━╮┃╱┃┃┃╰╮╱╱╱┃┃╱╱╱┃╭━╮┃
╱╱╰╯╱╱╱╰╯╱╰╯╱╰╯╰━╯╱╱╱╰╯╱╱╱╰╯╱╰╯
""".strip("\n")

BASE_TAGLINE = (
    "5641525441 - Secure your Open-Weight Open-Source Coding Agents - BfUVXmtYsj"
)

_RESET = "\033[0m"
_DIM = "\033[2m"
_BOLD = "\033[1m"
_BLUE = "\033[38;2;120;181;255m"
_BLUE2 = "\033[38;2;155;208;255m"
_CYAN = "\033[38;2;164;215;255m"
_MUTED = "\033[38;2;70;90;120m"
_GREEN = "\033[38;2;80;200;120m"
_YELLOW = "\033[38;2;230;180;80m"
_RED = "\033[38;2;230;90;90m"


@dataclass(frozen=True)
class Scenario:
    key: str
    title: str
    loaded: tuple[str, ...]
    hint: str
    accent: str = _BLUE


SCENARIOS: dict[str, Scenario] = {
    "proxy": Scenario(
        key="proxy",
        title="PROXY  (product surface)",
        loaded=(
            "guard.Guard.check  — deterministic allow/deny/taint",
            "OpenAI façade      — /v1/chat/completions + /v1/models",
            "tool gate          — /v1/tools/execute (mandatory)",
            "Tavily             — /v1/tavily/search + /verify (stale-answer)",
            "llm_map.json       — backends from Step 1 (llm-map)",
        ),
        hint="Coding agents: set base_url here. Never call mapped LLMs directly.",
        accent=_CYAN,
    ),
    "agent": Scenario(
        key="agent",
        title="AGENT  (loop → proxy only)",
        loaded=(
            "HTTP client        — talks only to VARTA proxy",
            "tools              — read_file, write_file, shell, read_github_issue",
            "Tavily tools       — tavily_search, verify_claim",
            "scripted demo      — poisoned issue #42 trajectory",
        ),
        hint="All features stay in proxy/. This process never bypasses the guard.",
        accent=_GREEN,
    ),
    "install": Scenario(
        key="install",
        title="INSTALL  (bootstrap)",
        loaded=(
            "pip requirements   — pyyaml, pytest",
            "optional Rust      — llm-map inventory binary",
            "optional Tavily    — TAVILY_API_KEY in .env",
            "assets             — ASCII + HTML wordmark",
        ),
        hint="After install: python -m proxy  |  python -m agent --scripted",
        accent=_YELLOW,
    ),
    "llm-map": Scenario(
        key="llm-map",
        title="LLM-MAP  (Step 1 discovery)",
        loaded=(
            "process scan       — ollama, vLLM, llama.cpp, LM Studio, …",
            "OpenAI probe       — /v1/models on local ports",
            "output             — llm_map.json for the proxy",
        ),
        hint="Inventory only. Enforcement lives in the proxy (Step 2).",
        accent=_BLUE2,
    ),
    "tavily": Scenario(
        key="tavily",
        title="TAVILY  (research + stale-answer)",
        loaded=(
            "tavily_search      — cited live web research",
            "verify_claim       — FRESH / STALE / UNCERTAIN",
            "policy             — api.tavily.com allowlisted; results taint session",
        ),
        hint="Prefer Tavily over raw http_request to unknown hosts.",
        accent=_GREEN,
    ),
    "guard": Scenario(
        key="guard",
        title="GUARD  (policy core)",
        loaded=(
            "files / network / shell / secrets / taint / audit",
            "autonomous mode    — ask → deny",
            "handover           — pause after 3 denials",
        ),
        hint="No LLM on the enforcement path.",
        accent=_RED,
    ),
}


def _color_enabled() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("VARTA_FORCE_COLOR") == "1":
        return True
    return sys.stdout.isatty()


def _enable_windows_ansi() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        pass


def _paint_logo(use_color: bool) -> str:
    lines = ASCII_LOGO.splitlines()
    if not use_color:
        return "\n".join(lines)
    out = []
    n = max(len(lines), 1)
    for i, line in enumerate(lines):
        painted = []
        for j, ch in enumerate(line):
            if ch in "╱ ":
                painted.append(f"{_MUTED}{ch}{_RESET}")
            else:
                t = (i / max(n - 1, 1) + j / max(len(line) - 1, 1)) / 2
                r = int(120 + t * 45)
                g = int(181 + t * 40)
                painted.append(f"\033[38;2;{r};{g};255m{ch}{_RESET}")
        out.append("".join(painted))
    return "\n".join(out)


def render(scenario: str = "proxy", *, extra: str | None = None) -> str:
    sc = SCENARIOS.get(scenario, SCENARIOS["proxy"])
    use = _color_enabled()
    logo = _paint_logo(use)

    def c(code: str, text: str) -> str:
        return f"{code}{text}{_RESET}" if use else text

    lines = [
        "",
        logo,
        "",
        c(_DIM, BASE_TAGLINE),
        c(_MUTED, "─" * min(72, max(len(BASE_TAGLINE), 40))),
        c(_BOLD + sc.accent, f"  VARTA · {sc.title}"),
        c(_DIM, "  LOADED:"),
    ]
    for item in sc.loaded:
        lines.append(c(sc.accent, "    ● ") + item)
    lines.append(c(_YELLOW if use else "", f"  → {sc.hint}"))
    if extra:
        lines.append(c(_DIM, f"  {extra}"))
    lines.append("")
    return "\n".join(lines)


def print_banner(scenario: str = "proxy", *, extra: str | None = None, file=None) -> None:
    if os.environ.get("VARTA_QUIET") == "1":
        return
    _enable_windows_ansi()
    print(render(scenario, extra=extra), file=file or sys.stdout, flush=True)


def known_scenarios() -> list[str]:
    return sorted(SCENARIOS)
