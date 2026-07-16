#!/bin/sh
set -eu

export STRONG_STOCK_DATA_DIR="${STRONG_STOCK_DATA_DIR:-/app/data}"
mkdir -p "$STRONG_STOCK_DATA_DIR"

cd /app/api
/opt/strong-stock-api-venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8010 &
api_pid="$!"

wait_for_api_ready() {
  attempt=1
  while [ "$attempt" -le 60 ]; do
    if ! kill -0 "$api_pid" 2>/dev/null; then
      wait "$api_pid" || exit "$?"
      exit 1
    fi

    if /opt/strong-stock-api-venv/bin/python - <<'PY'
import sys
import urllib.request

try:
    with urllib.request.urlopen("http://127.0.0.1:8010/health", timeout=1) as response:
        sys.exit(0 if response.status == 200 else 1)
except Exception:
    sys.exit(1)
PY
    then
      return 0
    fi

    attempt=$((attempt + 1))
    sleep 1
  done

  echo "API did not become ready within 60 seconds" >&2
  kill "$api_pid" 2>/dev/null || true
  wait "$api_pid" 2>/dev/null || true
  exit 1
}

wait_for_api_ready

cd /app/web
export PORT="${PORT:-3110}"
export HOSTNAME="${HOSTNAME:-0.0.0.0}"
export API_INTERNAL_URL="${API_INTERNAL_URL:-http://127.0.0.1:8010}"
node server.mjs &
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
