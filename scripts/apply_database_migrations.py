from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_DIR / "backend"
MIGRATIONS_DIR = PROJECT_DIR / "database" / "mysql" / "migrations"
sys.path.insert(0, str(BACKEND_DIR))

from database import database_status, engine  # noqa: E402


def main() -> None:
    paths = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not paths:
        raise FileNotFoundError(f"No SQL migrations found in {MIGRATIONS_DIR}")

    with engine.begin() as connection:
        for path in paths:
            statement = path.read_text(encoding="utf-8-sig").strip()
            print(f"Applying {path.name}")
            connection.exec_driver_sql(statement)

    # Upgrade files contain simple statements only (no routines or semicolons in strings).
    # All statements of an upgrade share one connection for PREPARE/session variables.
    for path in sorted((MIGRATIONS_DIR.parent / "upgrades").glob("*.sql")):
        sql = re.sub(r"(?m)^--[^\n]*", "", path.read_text(encoding="utf-8-sig"))
        print(f"Applying {path.name}")
        with engine.begin() as connection:
            for statement in sql.split(";"):
                if statement.strip():
                    connection.exec_driver_sql(statement.strip())

    result = database_status()
    if not (
        result.get("connected")
        and result.get("auth_schema_ready")
        and result.get("history_schema_ready")
        and result.get("risk_audit_schema_ready")
        and result.get("workspace_schema_ready")
    ):
        raise RuntimeError(f"Migration verification failed: {result}")
    print(
        "MySQL/MariaDB migrations completed successfully "
        f"for database {result.get('database')}."
    )


if __name__ == "__main__":
    main()
