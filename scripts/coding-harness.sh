#!/usr/bin/env bash
# ASCII coding view → local GPT-OSS 20B (no OpenCode).
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
PY="$REPO/.venv/bin/python"
[[ -x "$PY" ]] || PY=python3
export CVIEW_BASE_URL="${CVIEW_BASE_URL:-http://127.0.0.1:8080/v1}"
export CVIEW_MODEL="${CVIEW_MODEL:-gpt-oss-20b}"
if ! curl -sf -m 2 "${CVIEW_BASE_URL}/models" >/dev/null; then
  echo "GPT-OSS not up at $CVIEW_BASE_URL" >&2
  echo "  systemctl --user start gpt-oss-server" >&2
  exit 1
fi
cd "$REPO"
exec "$PY" -m cview "$@"
