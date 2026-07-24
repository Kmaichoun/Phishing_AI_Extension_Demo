#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_EXE="$ROOT_DIR/.venv/Scripts/python.exe"

export PYTHONDONTWRITEBYTECODE=1
exec "$PYTHON_EXE" "$ROOT_DIR/scripts/apply_database_migrations.py"
