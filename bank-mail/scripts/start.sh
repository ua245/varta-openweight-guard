#!/usr/bin/env bash
# Start Imperial Demo Bank mail stack + desk UI.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO="$(cd "$ROOT/.." && pwd)"
cd "$ROOT"

mkdir -p "$ROOT/data" "$ROOT/logs"

echo "==> Mailpit"
docker compose up -d

echo "==> Wait for Mailpit API"
for i in $(seq 1 40); do
  if curl -fsS --max-time 2 http://127.0.0.1:8025/api/v1/info >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done
curl -fsS --max-time 3 http://127.0.0.1:8025/api/v1/info | head -c 200; echo

echo "==> Seed sample bank emails (idempotent)"
# shellcheck disable=SC1091
source "$REPO/.venv/bin/activate"
export MAILPIT_URL=http://127.0.0.1:8025
export BANK_SMTP_HOST=127.0.0.1
export BANK_SMTP_PORT=1025
export BANK_LLM_BASE="${BANK_LLM_BASE:-http://127.0.0.1:8080/v1}"
export BANK_LLM_MODEL="${BANK_LLM_MODEL:-gpt-oss-20b}"
python - <<'PY'
import app
n = app.seed_messages()
print(f"seeded {n} message(s)")
PY

echo "==> Bank mail desk on http://127.0.0.1:8090"
pkill -f "uvicorn app:app --host 127.0.0.1 --port 8090" 2>/dev/null || true
nohup uvicorn app:app --host 127.0.0.1 --port 8090 \
  >"$ROOT/logs/bank-mail.log" 2>&1 &
echo $! >"$ROOT/logs/bank-mail.pid"
sleep 1
curl -fsS --max-time 5 http://127.0.0.1:8090/api/health | python -m json.tool || true
echo
echo "Desk UI:    http://127.0.0.1:8090"
echo "Mailpit UI: http://127.0.0.1:8025"
echo "SMTP in:    127.0.0.1:1025  (send from any From: address)"
echo "Inbox:      treasury@imperial-demo.bank"
