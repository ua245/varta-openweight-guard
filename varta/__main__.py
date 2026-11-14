# -*- coding: utf-8 -*-
"""python -m varta  → show loader + help."""
from __future__ import annotations

import argparse
import sys

from varta.banner import known_scenarios, print_banner


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="varta", description="VARTA launch loader")
    p.add_argument(
        "scenario",
        nargs="?",
        default="proxy",
        choices=known_scenarios(),
        help="Which surface is loaded (tells the coding LLM the context)",
    )
    p.add_argument("--install", action="store_true", help="Run custom installer")
    args = p.parse_args(argv)
    if args.install:
        from varta.install import main as install_main

        return install_main([])
    print_banner(args.scenario)
    print("  Launch:")
    print("    python -m varta.install [--with-rust]")
    print("    python -m proxy")
    print("    python -m agent --scripted")
    print("    cargo run --manifest-path llm-map/Cargo.toml")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
