#!/usr/bin/env bash
# Run CrabSweeper and its smee relay together for local development.
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

: "${SMEE_URL:?set SMEE_URL in .env (e.g. https://smee.io/9131e4d377683994)}"
PORT="${PORT:-8000}"

pids=()
cleanup() {
  for pid in "${pids[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

echo "relay: $SMEE_URL  ->  http://localhost:$PORT/webhook"
npx --yes smee-client --url "$SMEE_URL" --target "http://localhost:$PORT/webhook" &
pids+=($!)

echo "app:   http://localhost:$PORT"
uv run uvicorn crabsweeper.app:app --reload --port "$PORT" &
pids+=($!)

wait
