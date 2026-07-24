#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEB_DIR="$ROOT_DIR/web-app"

if ! command -v node >/dev/null 2>&1; then
  echo "Node.js is not available in Git Bash." >&2
  exit 1
fi

cd "$WEB_DIR"
export PORT="${WEB_PORT:-5505}"
echo "Web App: http://app.phishradar.localhost:${PORT}/login.html"
echo "Fallback: http://127.0.0.1:${PORT}/login.html"
exec node server.js
