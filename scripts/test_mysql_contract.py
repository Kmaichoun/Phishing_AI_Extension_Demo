from __future__ import annotations

import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
MIGRATIONS_DIR = PROJECT_ROOT / "database" / "mysql" / "migrations"
sys.path.insert(0, str(BACKEND_DIR))

EXPECTED_TABLES = {
    "001_create_users.sql": {
        "Users",
        "UserId",
        "Username",
        "NormalizedUsername",
        "PasswordHash",
        "Email",
        "NormalizedEmail",
        "Role",
    },
    "002_create_user_devices.sql": {
        "UserDevices",
        "UserDeviceId",
        "UserId",
        "DeviceName",
        "DeviceKeyHash",
    },
    "003_create_sessions.sql": {
        "Sessions",
        "SessionId",
        "UserId",
        "UserDeviceId",
        "TokenHash",
        "ExpiresAt",
    },
    "004_create_search_history.sql": {
        "SearchHistory",
        "HistoryId",
        "UserId",
        "UserDeviceId",
        "Url",
        "RiskProbability",
        "RiskScore",
        "Decision",
        "ModelVersion",
        "LayerResults",
    },
}


def main() -> None:
    migration_paths = sorted(MIGRATIONS_DIR.glob("*.sql"))
    assert [path.name for path in migration_paths] == list(EXPECTED_TABLES)

    for path in migration_paths:
        sql = path.read_text(encoding="utf-8-sig")
        executable_sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
        assert len(re.findall(r"\bCREATE\s+TABLE\b", sql, flags=re.IGNORECASE)) == 1
        assert "ENGINE=InnoDB" in sql
        assert "utf8mb4" in sql
        assert not re.search(
            r"\b(?:GO|IDENTITY|NVARCHAR|SYSUTCDATETIME|OUTPUT\s+INSERTED|SELECT\s+TOP)\b",
            sql,
            flags=re.IGNORECASE,
        )
        assert not re.search(
            r"\bFOREIGN\s+KEY\b|\bCHECK\s*\(",
            executable_sql,
            flags=re.IGNORECASE,
        ), f"{path.name} requires privileges or parser support unavailable on shared hosting"
        for identifier in EXPECTED_TABLES[path.name]:
            assert f"`{identifier}`" in sql, f"{path.name} is missing {identifier}"

    users_sql = (MIGRATIONS_DIR / "001_create_users.sql").read_text(
        encoding="utf-8-sig"
    )
    assert not re.search(r"(?im)^\s*`Password`\s+", users_sql)
    assert "`PasswordHash` VARCHAR(255) NOT NULL" in users_sql

    source_paths = [
        BACKEND_DIR / "database.py",
        BACKEND_DIR / "auth_router.py",
        BACKEND_DIR / "history_router.py",
    ]
    source = "\n".join(path.read_text(encoding="utf-8-sig") for path in source_paths)
    for legacy_token in (
        "mssql+pyodbc",
        "auth.Users",
        "auth.UserDevices",
        "auth.Sessions",
        "auth.SearchHistory",
        "SYSUTCDATETIME",
        "OUTPUT INSERTED",
        "SELECT TOP",
    ):
        assert legacy_token not in source, f"legacy SQL Server token remains: {legacy_token}"

    os.environ.setdefault("MYSQL_DATABASE", "ip_std6730202581")
    from database import _database_url  # noqa: PLC0415

    url = _database_url()
    assert getattr(url, "drivername", "") == "mysql+pymysql"
    assert getattr(url, "database", "") == "ip_std6730202581"

    requirements = (BACKEND_DIR / "requirements.txt").read_text(encoding="utf-8")
    assert "PyMySQL==" in requirements
    assert "pyodbc" not in requirements.lower()

    print("MySQL contract passed: schema, driver and Backend contain no SQL Server SQL")


if __name__ == "__main__":
    main()
