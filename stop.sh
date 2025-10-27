#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

stop_pid_file() {
  local f="$1"
  if [[ -f "$f" ]]; then
    local pid
    pid=$(cat "$f" || true)
    if [[ -n "${pid:-}" ]] && ps -p "$pid" >/dev/null 2>&1; then
      echo "[i] Stopping PID $pid from $f"
      kill "$pid" || true
      sleep 1
      if ps -p "$pid" >/dev/null 2>&1; then
        echo "[i] Force killing PID $pid"
        kill -9 "$pid" || true
      fi
    fi
    rm -f "$f"
  fi
}

stop_pid_file "$ROOT_DIR/var/state/dashboard.pid"
stop_pid_file "$ROOT_DIR/var/state/orchestrator.pid"

echo "[i] Stop signal sent. If miners keep running, use the dashboard or run:"
echo "    curl -s -H 'X-API-KEY: <token>' http://127.0.0.1:8765/api/miners/all/stop -X POST"
