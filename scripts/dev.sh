#!/usr/bin/env bash
# Start FastAPI (:8000) and the Vite desk (:5173) together.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -x "$ROOT/.venv/bin/python3" ]]; then
  PYTHON="$ROOT/.venv/bin/python3"
else
  PYTHON="$(command -v python3)"
fi

if ! "$PYTHON" -c "import uvicorn" 2>/dev/null; then
  echo "uvicorn missing in $PYTHON — installing requirements..."
  "$PYTHON" -m pip install -r "$ROOT/requirements.txt"
fi

cleanup() {
  if [[ -n "${API_PID:-}" ]] && kill -0 "$API_PID" 2>/dev/null; then
    kill "$API_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

if ! lsof -nP -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Starting API with $PYTHON on http://127.0.0.1:8000"
  "$PYTHON" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 &
  API_PID=$!
  for _ in $(seq 1 40); do
    if curl -sf "http://127.0.0.1:8000/api/tags" >/dev/null 2>&1; then
      echo "API is up"
      break
    fi
    if ! kill -0 "$API_PID" 2>/dev/null; then
      echo "API process exited before it started listening" >&2
      exit 1
    fi
    sleep 0.25
  done
  if ! curl -sf "http://127.0.0.1:8000/api/tags" >/dev/null 2>&1; then
    echo "API did not become ready on :8000" >&2
    exit 1
  fi
else
  echo "API already listening on :8000"
fi

cd "$ROOT/frontend"
echo "Starting Vite on http://localhost:5173 (proxies /api → :8000)"
npm run dev
