"""Manual detector test from the terminal."""
import os

from .detector import DetectorError, from_policy


def main():
    # Manual test: python3 -m guard.scan <file> [<file> ...]   or   echo "text" | python3 -m guard.scan
    import sys
    import time
    from pathlib import Path
    from .policy import load_policy

    for line in (open(".env").read().splitlines() if Path(".env").exists() else []):
        if "=" in line and not line.startswith("#"):
            os.environ.setdefault(*line.split("=", 1))
    det = from_policy(load_policy())
    if det is None:
        sys.exit("No ADAPTION_API_KEY (put it in .env or export it).")
    inputs = [(f, Path(f).read_text(errors="replace")) for f in sys.argv[1:]] or [("stdin", sys.stdin.read())]
    for name, text in inputs:
        t = time.time()
        try:
            verdict = "INJECTION" if det.scan(text) else "SAFE"
        except DetectorError as e:
            verdict = f"ERROR ({e})"
        print(f"{name}: {verdict}  [{time.time() - t:.1f}s]")


if __name__ == "__main__":
    main()
