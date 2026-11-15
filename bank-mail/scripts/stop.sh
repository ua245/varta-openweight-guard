#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -f "$ROOT/logs/bank-mail.pid" ]]; then
  kill "$(cat "$ROOT/logs/bank-mail.pid")" 2>/dev/null || true
  rm -f "$ROOT/logs/bank-mail.pid"
fi
pkill -f "uvicorn app:app --host 127.0.0.1 --port 8090" 2>/dev/null || true
cd "$ROOT" && docker compose down
echo "Bank mail stopped."
