"""Exercise fresh import and legacy upgrade in an empty disposable local database.

Set DATABASE_URL to a database named phish_radar_device_removal_test_* first.
This test never connects to the department database or existing user data.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient
from sqlalchemy import text

from app import app
from database import database_status, engine


def execute_file(path: Path) -> None:
    sql = path.read_text(encoding="utf-8-sig")
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.S)
    sql = re.sub(r"(?m)^--[^\n]*", "", sql)
    with engine.begin() as db:
        for statement in sql.split(";"):
            if statement.strip():
                db.exec_driver_sql(statement.strip())


def snapshot(table: str) -> list[dict]:
    with engine.connect() as db:
        return [dict(row) for row in db.execute(text(f"SELECT * FROM `{table}`")).mappings()]


def main() -> None:
    assert engine.url.host in {"127.0.0.1", "localhost", "::1"}
    assert (engine.url.database or "").startswith("phish_radar_device_removal_test_")
    with engine.connect() as db:
        assert db.execute(text("SHOW TABLES")).all() == [], "Use a new empty test database"

    execute_file(ROOT / "database/mysql/phish_radar_phpmyadmin_import.sql")
    assert database_status()["auth_schema_ready"]
    headers = {"Origin": "http://127.0.0.1:5505", "X-Phish-Radar-Client": "web-app"}
    client = TestClient(app, base_url="http://127.0.0.1:8765", headers=headers)
    client.cookies.set("phish_radar_device", "legacy-identifier", domain="127.0.0.1", path="/")
    account = client.post("/auth/register", json={
        "username": "migration_test", "email": "migration_test@example.com",
        "password": "Migration-test-password-2026!",
    })
    assert account.status_code == 201, account.text
    assert "device_name" not in account.json()
    assert "phish_radar_device" not in client.cookies
    history = client.post("/history", json={
        "url": "https://example.com/test?secret=hidden", "rule_score": 10,
        "final_score": 10, "decision": "allow", "source": "web-app",
    })
    assert history.status_code == 201, history.text
    feedback = client.post("/workspace/feedback", json={
        "history_id": history.json()["history_id"], "user_label": "safe",
    })
    assert feedback.status_code == 200, feedback.text
    before = {name: snapshot(name) for name in ["Users", "Sessions", "SearchHistory", "ScanFeedback"]}

    # Reproduce the old device columns and indexes on populated tables.
    with engine.begin() as db:
        db.exec_driver_sql("""CREATE TABLE UserDevices (
            UserDeviceId BIGINT UNSIGNED PRIMARY KEY, UserId BIGINT UNSIGNED NOT NULL,
            DeviceName VARCHAR(200) NOT NULL, DeviceKeyHash BINARY(32)
        ) ENGINE=InnoDB""")
        db.exec_driver_sql("INSERT INTO UserDevices VALUES (1, 1, 'Legacy browser', UNHEX(SHA2('legacy',256)))")
        for table in ["Sessions", "SearchHistory"]:
            db.exec_driver_sql(f"""ALTER TABLE `{table}`
                ADD UserDeviceId BIGINT UNSIGNED NOT NULL DEFAULT 1,
                ADD INDEX `IX_{table}_UserDeviceId` (UserDeviceId)""")
        db.exec_driver_sql("""INSERT INTO AuditEvents
            (ActorUserId, Action, TargetType, TargetId, Details) VALUES
            (1, 'device.revoke', 'device', '1', '{}'),
            (1, 'session.revoke', 'session', 'test', '{}')""")

    assert not database_status()["auth_schema_ready"]
    assert not database_status()["history_schema_ready"]
    upgrade = ROOT / "database/mysql/upgrades/007_remove_user_devices.sql"
    execute_file(upgrade)
    execute_file(upgrade)  # A second import must be harmless.
    assert database_status()["auth_schema_ready"]
    assert database_status()["history_schema_ready"]
    for table, expected in before.items():
        assert snapshot(table) == expected, f"Upgrade changed retained rows in {table}"
    with engine.connect() as db:
        tables = {row[0].lower() for row in db.execute(text("SHOW TABLES"))}
        assert tables == {"users", "sessions", "searchhistory", "scanfeedback", "auditevents"}
        assert db.execute(text("""SELECT COUNT(*) FROM information_schema.columns
            WHERE table_schema=DATABASE() AND column_name='UserDeviceId'""")).scalar_one() == 0
    assert [row["Action"] for row in snapshot("AuditEvents")] == ["session.revoke"]
    assert client.get("/auth/me").status_code == 200
    restored = client.get("/history")
    assert restored.status_code == 200 and restored.json()["total"] == 1
    assert "device_name" not in restored.json()["items"][0]
    assert set(client.get("/workspace/security").json()) == {"sessions"}
    print("Device removal passed: fresh import, legacy upgrade, repeat import, retained data, cookie cleanup and active login.")


if __name__ == "__main__":
    main()
