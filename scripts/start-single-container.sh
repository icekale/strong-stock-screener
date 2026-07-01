#!/bin/sh
set -eu

export STRONG_STOCK_DATA_DIR="${STRONG_STOCK_DATA_DIR:-/app/data}"
mkdir -p "$STRONG_STOCK_DATA_DIR"

cd /app/api
/opt/strong-stock-api-venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8010 &
api_pid="$!"

cd /app/web
node node_modules/next/dist/bin/next start -p "${PORT:-3110}" -H "${HOSTNAME:-0.0.0.0}" &
web_pid="$!"

shutdown() {
  kill "$api_pid" "$web_pid" 2>/dev/null || true
  wait "$api_pid" 2>/dev/null || true
  wait "$web_pid" 2>/dev/null || true
}

trap shutdown INT TERM

while true; do
  if ! kill -0 "$api_pid" 2>/dev/null; then
    wait "$api_pid" || exit "$?"
    exit 1
  fi
  if ! kill -0 "$web_pid" 2>/dev/null; then
    wait "$web_pid" || exit "$?"
    exit 1
  fi
  sleep 1
done
