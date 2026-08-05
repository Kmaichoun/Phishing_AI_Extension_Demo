from __future__ import annotations

import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app import app  # noqa: E402
from database import open_session  # noqa: E402


def expect(response, status_code: int, label: str) -> dict[str, object] | None:
    if response.status_code != status_code:
        raise AssertionError(f"{label}: expected {status_code}, got {response.status_code}: {response.text}")
    if response.status_code == 204:
        return None
    return response.json()


def main() -> None:
    suffix = str(int(time.time() * 1000))[-10:]
    username = f"auth_test_{suffix}"
    email = f"{username}@example.com"
    password = "Test-only-password-2026!"
    headers = {
        "Origin": "http://127.0.0.1:5505",
        "X-Phish-Radar-Client": "web-app",
    }

    client = TestClient(app, base_url="http://127.0.0.1:8765")
    try:
        health = expect(client.get("/auth/health"), 200, "auth health")
        assert health and health["connected"] and health["auth_schema_ready"]

        registered = expect(
            client.post(
                "/auth/register",
                headers=headers,
                json={
                    "username": username,
                    "email": email,
                    "password": password,
                    "device_name": "Automated test device",
                    "role": "admin",
                },
            ),
            201,
            "register",
        )
        assert registered and registered["role"] == "user"
        assert "password" not in registered and "session" not in registered

        current = expect(client.get("/auth/me"), 200, "current user after registration")
        assert current and current["username"] == username and current["role"] == "user"

        with open_session() as database:
            row = database.execute(
                text(
                    """
                    SELECT u.PasswordHash,
                           (SELECT COUNT(*) FROM UserDevices d WHERE d.UserId = u.UserId) AS DeviceCount,
                           (SELECT COUNT(*) FROM Sessions s WHERE s.UserId = u.UserId) AS SessionCount
                    FROM Users u
                    WHERE u.NormalizedUsername = LOWER(:username)
                    """
                ),
                {"username": username},
            ).mappings().one()
            assert str(row["PasswordHash"]).startswith("$argon2")
            assert row["PasswordHash"] != password
            assert int(row["DeviceCount"]) == 1
            assert int(row["SessionCount"]) == 1

        expect(client.post("/auth/logout", headers=headers), 204, "logout after registration")
        expect(client.get("/auth/me"), 401, "revoked session")

        logged_in = expect(
            client.post(
                "/auth/login",
                headers=headers,
                json={
                    "identifier": email.upper(),
                    "password": password,
                    "device_name": "Renamed automated test device",
                },
            ),
            200,
            "login by normalized email",
        )
        assert logged_in and logged_in["username"] == username
        expect(client.get("/auth/me"), 200, "current user after login")
        expect(client.post("/auth/logout", headers=headers), 204, "final logout")

        print("Authentication flow passed: register -> me -> logout -> login -> me -> logout")
    finally:
        with open_session() as database:
            user_id = database.execute(
                text("SELECT UserId FROM Users WHERE NormalizedUsername = LOWER(:username)"),
                {"username": username},
            ).scalar_one_or_none()
            if user_id is not None:
                database.execute(text("DELETE FROM SearchHistory WHERE UserId = :user_id"), {"user_id": user_id})
                database.execute(text("DELETE FROM Sessions WHERE UserId = :user_id"), {"user_id": user_id})
                database.execute(text("DELETE FROM UserDevices WHERE UserId = :user_id"), {"user_id": user_id})
                database.execute(text("DELETE FROM Users WHERE UserId = :user_id"), {"user_id": user_id})
                database.commit()


if __name__ == "__main__":
    main()
