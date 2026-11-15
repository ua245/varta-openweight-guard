#!/usr/bin/env bash
# Bring up mail desk + GPT-OSS 20B + agent preflight (guard-core).
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"

if [[ -f .env ]]; then
  set -a; # shellcheck disable=SC1091
  source .env; set +a
else
  echo "No .env — copy example.env and fill keys:" >&2
  echo "  cp example.env .env && chmod 600 .env" >&2
fi

export AGENT_BASE_URL="${AGENT_BASE_URL:-http://127.0.0.1:8080/v1}"
export AGENT_MODEL="${AGENT_MODEL:-gpt-oss-20b}"
export AGENT_API_KEY="${AGENT_API_KEY:-local}"
export BANK_LLM_BASE="${BANK_LLM_BASE:-$AGENT_BASE_URL}"
export BANK_LLM_MODEL="${BANK_LLM_MODEL:-$AGENT_MODEL}"

PORT="${GPT_OSS_PORT:-8080}"
if ss -tlnH "sport = :$PORT" 2>/dev/null | grep -q .; then
  if curl -sf -m 2 "$AGENT_BASE_URL/models" | grep -q gpt-oss-20b; then
    echo "==> GPT-OSS already on :$PORT"
  else
    echo "ERROR: :$PORT is busy but not serving gpt-oss-20b." >&2
    echo "  Free it (e.g. docker stop sensible-sandbox-api) or set GPT_OSS_PORT + AGENT_BASE_URL." >&2
    exit 1
  fi
else
  echo "==> Starting GPT-OSS 20B"
  if systemctl --user cat gpt-oss-server.service >/dev/null 2>&1; then
    systemctl --user start gpt-oss-server.service
  else
    bash "$REPO/local-ai/install-user-unit.sh"
    systemctl --user start gpt-oss-server.service
  fi
fi

echo "==> Waiting for model"
for i in $(seq 1 120); do
  if curl -sf -m 2 "$AGENT_BASE_URL/models" 2>/dev/null | grep -q gpt-oss-20b; then
    echo "model ready (${i}s)"
    break
  fi
  sleep 2
  if [[ "$i" -eq 120 ]]; then
    echo "Timed out waiting for $AGENT_BASE_URL" >&2
    exit 1
  fi
done

if [[ -x "$REPO/bank-mail/scripts/start.sh" ]]; then
  echo "==> Bank mail desk"
  bash "$REPO/bank-mail/scripts/start.sh" || true
fi

PY="${REPO}/.venv/bin/python"
[[ -x "$PY" ]] || PY="${PYTHON:-python3}"
echo "==> Agent preflight"
"$PY" -m agent.check --base-url "$AGENT_BASE_URL" --model "$AGENT_MODEL" --api-key "$AGENT_API_KEY"
echo
echo "Guarded demo:"
echo "  $PY -m agent.run --model $AGENT_MODEL --issue poisoned_issue_v3.md"
echo "ASCII coding desk:"
echo "  bash scripts/cview"
