#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEB_DIR="$ROOT_DIR/web-app"

if ! command -v node >/dev/null 2>&1; then
  echo "Node.js is not available in Git Bash." >&2
  exit 1
fi

cd "$WEB_DIR"
if [[ ! -d node_modules ]]; then
  echo "React dependencies are not installed. Run: cd web-app && npm install" >&2
  exit 1
fi

PORT="${WEB_PORT:-5505}"
echo "React Web App: http://app.phishradar.localhost:${PORT}/#/login"
echo "Fallback: http://127.0.0.1:${PORT}/#/login"
exec npm run dev -- --port "$PORT"
