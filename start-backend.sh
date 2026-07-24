#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_EXE="$ROOT_DIR/.venv/Scripts/python.exe"

if [[ ! -x "$PYTHON_EXE" ]]; then
  echo "Python virtual environment not found: $PYTHON_EXE" >&2
  exit 1
fi

export PYTHONDONTWRITEBYTECODE=1
export AUTH_WEB_ORIGINS="${AUTH_WEB_ORIGINS:-http://app.phishradar.localhost:5505,http://127.0.0.1:5505,http://localhost:5505}"

echo "Backend: http://127.0.0.1:8765"
exec "$PYTHON_EXE" -m uvicorn app:app \
  --app-dir "$ROOT_DIR/backend" \
  --host 127.0.0.1 \
  --port "${BACKEND_PORT:-8765}"
