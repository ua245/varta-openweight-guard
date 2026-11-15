"""python -m cview  — ASCII coding desk against local qwen8b."""

from __future__ import annotations

import argparse

from .app import run


def main() -> None:
    p = argparse.ArgumentParser(
        prog="cview",
        description="ASCII coding view for local FreeToken (no OpenCode)",
    )
    p.add_argument(
        "--base-url",
        default=None,
        help="OpenAI-compatible base URL (default http://127.0.0.1:1921/v1)",
    )
    p.add_argument("--model", default=None, help="Model id (default qwen8b)")
    p.add_argument(
        "--system",
        default=None,
        help="Override system prompt",
    )
    args = p.parse_args()
    raise SystemExit(run(base_url=args.base_url, model=args.model, system=args.system))


if __name__ == "__main__":
    main()
