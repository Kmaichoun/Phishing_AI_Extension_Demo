from __future__ import annotations

import re
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import URL, make_url

PROJECT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_DIR / "backend"
MIGRATIONS_DIR = PROJECT_DIR / "database" / "sqlserver" / "migrations"
sys.path.insert(0, str(BACKEND_DIR))

from database import _database_url  # noqa: E402


def migration_engine():
    configured = _database_url()
    url = configured if isinstance(configured, URL) else make_url(configured)
    return create_engine(
        url.set(database="master"),
        isolation_level="AUTOCOMMIT",
        pool_pre_ping=True,
        connect_args={"timeout": 10},
    )


def split_batches(script: str) -> list[str]:
    return [
        batch.strip()
        for batch in re.split(r"^\s*GO\s*;?\s*$", script, flags=re.IGNORECASE | re.MULTILINE)
        if batch.strip()
    ]


def main() -> None:
    paths = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not paths:
        raise FileNotFoundError(f"No SQL migrations found in {MIGRATIONS_DIR}")

    engine = migration_engine()
    with engine.connect() as connection:
        for path in paths:
            batches = split_batches(path.read_text(encoding="utf-8-sig"))
            print(f"Applying {path.name} ({len(batches)} batches)")
            for batch in batches:
                connection.exec_driver_sql(batch)
    engine.dispose()
    print("Database migrations completed successfully.")


if __name__ == "__main__":
    main()
