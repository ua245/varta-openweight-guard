# -*- coding: utf-8 -*-
"""Custom VARTA install UX.

  python -m varta.install
  python -m varta.install --with-rust
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from varta.banner import print_banner

ROOT = Path(__file__).resolve().parent.parent


def _ok(msg: str) -> None:
    print(f"  [ok]  {msg}")


def _skip(msg: str) -> None:
    print(f"  [--]  {msg}")


def _fail(msg: str) -> None:
    print(f"  [!!]  {msg}")


def _step(title: str) -> None:
    print()
    print(f"  ▸ {title}")
    print("  " + "·" * 48)


def install_python_deps() -> bool:
    _step("Python dependencies")
    req = ROOT / "requirements.txt"
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", str(req)],
            cwd=str(ROOT),
        )
        _ok(f"pip install -r {req.name}")
        return True
    except subprocess.CalledProcessError as e:
        _fail(f"pip failed: {e}")
        return False


def ensure_env_example() -> None:
    _step("Environment")
    example = ROOT / ".env.example"
    env = ROOT / ".env"
    if env.exists():
        _skip(".env already present")
    elif example.exists():
        shutil.copy(example, env)
        _ok("copied .env.example → .env  (set TAVILY_API_KEY for live search)")
    else:
        _skip("no .env.example found")


def build_llm_map(with_rust: bool) -> None:
    _step("Rust llm-map (Step 1)")
    if not with_rust:
        _skip("pass --with-rust to cargo build llm-map")
        return
    cargo = shutil.which("cargo")
    if not cargo:
        _fail("cargo not on PATH — install rustup + (Windows) VS Build Tools")
        return
    try:
        subprocess.check_call(
            [cargo, "build", "--manifest-path", "llm-map/Cargo.toml"],
            cwd=str(ROOT),
        )
        _ok("cargo build --manifest-path llm-map/Cargo.toml")
    except subprocess.CalledProcessError as e:
        _fail(f"cargo build failed: {e}")


def verify_import() -> bool:
    _step("Sanity import")
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    try:
        subprocess.check_call(
            [
                sys.executable,
                "-c",
                "from guard import Guard; from proxy.tools import build_guard",
            ],
            cwd=str(ROOT),
            env=env,
        )
        _ok("guard + proxy import clean")
        return True
    except subprocess.CalledProcessError:
        _fail("import failed — check PYTHONPATH / install")
        return False


def print_next_steps() -> None:
    _step("Next")
    print(
        """
  ┌─────────────────────────────────────────────────────────┐
  │  1.  python -m proxy              ← THE VARTA proxy     │
  │  2.  python -m agent --scripted   ← guarded demo loop   │
  │  3.  cargo run --manifest-path llm-map/Cargo.toml       │
  │      (optional) map local open-weight LLMs              │
  │  4.  set TAVILY_API_KEY in .env   ← live stale-answer   │
  └─────────────────────────────────────────────────────────┘
"""
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="VARTA custom installer")
    p.add_argument("--with-rust", action="store_true", help="Also cargo build llm-map")
    p.add_argument("--quiet-banner", action="store_true")
    args = p.parse_args(argv)

    if not args.quiet_banner:
        print_banner("install", extra=f"root={ROOT}  python={sys.executable}")

    ok = install_python_deps()
    ensure_env_example()
    build_llm_map(args.with_rust)
    ok = verify_import() and ok
    print_next_steps()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
