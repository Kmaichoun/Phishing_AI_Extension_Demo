#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_PID=""
WEB_PID=""

cleanup() {
  [[ -n "$BACKEND_PID" ]] && kill "$BACKEND_PID" 2>/dev/null || true
  [[ -n "$WEB_PID" ]] && kill "$WEB_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

"$ROOT_DIR/start-backend.sh" &
BACKEND_PID=$!
"$ROOT_DIR/start-web.sh" &
WEB_PID=$!

echo "Phish Radar is starting. Keep this Git Bash window open."
echo "Open http://app.phishradar.localhost:5505/login.html in your browser."
echo "Fallback: http://127.0.0.1:5505/login.html"
wait
