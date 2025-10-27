#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"
mkdir -p "$ROOT_DIR/logs" "$ROOT_DIR/var/state"

ORCH_PORT=$(awk '/port:/{print $2; exit}' "$ROOT_DIR/config/config.yaml" 2>/dev/null || echo 8765)

if [[ ! -x "$ROOT_DIR/.venv/bin/uvicorn" ]]; then
  echo "[!] Python venv not found. Run ./setup.sh first." >&2
  exit 1
fi

# Start orchestrator API
nohup "$ROOT_DIR/.venv/bin/uvicorn" orchestrator.app.main:app \
  --host 0.0.0.0 --port "$ORCH_PORT" \
  --log-level info \
  > "$ROOT_DIR/logs/orchestrator.out" 2>&1 &
ORCH_PID=$!
echo $ORCH_PID > "$ROOT_DIR/var/state/orchestrator.pid"

echo "[i] Orchestrator started (PID $ORCH_PID) at http://127.0.0.1:$ORCH_PORT"

# Start PHP dashboard (localhost:8080)
nohup php -S 127.0.0.1:8080 -t "$ROOT_DIR/dashboard/public" \
  > "$ROOT_DIR/logs/dashboard.out" 2>&1 &
DASH_PID=$!
echo $DASH_PID > "$ROOT_DIR/var/state/dashboard.pid"

echo "[i] Dashboard started (PID $DASH_PID) at http://127.0.0.1:8080"
