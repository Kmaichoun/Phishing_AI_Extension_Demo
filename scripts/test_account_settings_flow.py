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
    original_username = f"settings_{suffix}"
    updated_username = f"edited_{suffix}"
    original_email = f"{original_username}@example.com"
    updated_email = f"{updated_username}@example.com"
    original_password = "Settings-test-password-2026!"
    updated_password = "Updated-settings-password-2026!"
    headers = {
        "Origin": "http://127.0.0.1:5505",
        "X-Phish-Radar-Client": "web-app",
    }

    primary = TestClient(app, base_url="http://127.0.0.1:8765")
    secondary = TestClient(app, base_url="http://127.0.0.1:8765")
    fresh_login = TestClient(app, base_url="http://127.0.0.1:8765")
    try:
        registered = expect(
            primary.post(
                "/auth/register",
                headers=headers,
                json={
                    "username": original_username,
                    "email": original_email,
                    "password": original_password,
                    "device_name": "Primary settings test",
                },
            ),
            201,
            "register primary account",
        )
        assert registered and registered["role"] == "user"

        expect(
            secondary.post(
                "/auth/login",
                headers=headers,
                json={
                    "identifier": original_email,
                    "password": original_password,
                    "device_name": "Secondary settings test",
                },
            ),
            200,
            "create second session",
        )

        expect(
            primary.patch(
                "/auth/profile",
                json={
                    "username": updated_username,
                    "email": updated_email,
                    "current_password": original_password,
                },
            ),
            403,
            "reject profile update without web client headers",
        )
        expect(
            primary.patch(
                "/auth/profile",
                headers=headers,
                json={
                    "username": updated_username,
                    "email": updated_email,
                    "current_password": "incorrect password",
                },
            ),
            401,
            "reject profile update with wrong password",
        )

        updated = expect(
            primary.patch(
                "/auth/profile",
                headers=headers,
                json={
                    "username": updated_username,
                    "email": updated_email,
                    "current_password": original_password,
                },
            ),
            200,
            "update profile",
        )
        assert updated and updated["username"] == updated_username and updated["email"] == updated_email
        current = expect(primary.get("/auth/me"), 200, "read updated profile")
        assert current and current["username"] == updated_username

        expect(
            primary.post(
                "/auth/change-password",
                headers=headers,
                json={"current_password": original_password, "new_password": original_password},
            ),
            400,
            "reject reused password",
        )
        changed = expect(
            primary.post(
                "/auth/change-password",
                headers=headers,
                json={"current_password": original_password, "new_password": updated_password},
            ),
            200,
            "change password",
        )
        assert changed and changed["ok"] and int(changed["other_sessions_revoked"]) >= 1

        expect(primary.get("/auth/me"), 200, "keep current session after password change")
        expect(secondary.get("/auth/me"), 401, "revoke other session after password change")

        with open_session() as database:
            stored_hash = database.execute(
                text("SELECT PasswordHash FROM Users WHERE NormalizedUsername = LOWER(:username)"),
                {"username": updated_username},
            ).scalar_one()
            assert str(stored_hash).startswith("$argon2")
            assert stored_hash not in {original_password, updated_password}

        expect(primary.post("/auth/logout", headers=headers), 204, "logout primary")
        expect(
            fresh_login.post(
                "/auth/login",
                headers=headers,
                json={
                    "identifier": updated_email,
                    "password": original_password,
                    "device_name": "Fresh settings test",
                },
            ),
            401,
            "reject old password",
        )
        expect(
            fresh_login.post(
                "/auth/login",
                headers=headers,
                json={
                    "identifier": updated_email,
                    "password": updated_password,
                    "device_name": "Fresh settings test",
                },
            ),
            200,
            "login with updated credentials",
        )
        expect(fresh_login.post("/auth/logout", headers=headers), 204, "final logout")

        print("Account settings flow passed: profile update -> password change -> revoke other sessions -> new login")
    finally:
        with open_session() as database:
            user_id = database.execute(
                text(
                    """
                    SELECT UserId FROM Users
                    WHERE NormalizedUsername IN (LOWER(:original_username), LOWER(:updated_username))
                    """
                ),
                {"original_username": original_username, "updated_username": updated_username},
            ).scalar_one_or_none()
            if user_id is not None:
                database.execute(text("DELETE FROM SearchHistory WHERE UserId = :user_id"), {"user_id": user_id})
                database.execute(text("DELETE FROM Sessions WHERE UserId = :user_id"), {"user_id": user_id})
                database.execute(text("DELETE FROM UserDevices WHERE UserId = :user_id"), {"user_id": user_id})
                database.execute(text("DELETE FROM Users WHERE UserId = :user_id"), {"user_id": user_id})
                database.commit()


if __name__ == "__main__":
    main()
