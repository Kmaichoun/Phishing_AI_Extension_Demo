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

HEADERS = {
    "Origin": "http://127.0.0.1:5505",
    "X-Phish-Radar-Client": "web-app",
}


def expect(response, status_code: int, label: str) -> dict[str, object]:
    if response.status_code != status_code:
        raise AssertionError(
            f"{label}: expected {status_code}, got {response.status_code}: {response.text}"
        )
    return response.json()


def register(client: TestClient, username: str) -> None:
    expect(
        client.post(
            "/auth/register",
            headers=HEADERS,
            json={
                "username": username,
                "email": f"{username}@example.com",
                "password": "Test-only-password-2026!",
                "device_name": f"{username} test device",
            },
        ),
        201,
        f"register {username}",
    )


def cleanup_users(usernames: list[str]) -> None:
    with open_session() as database:
        for username in usernames:
            user_id = database.execute(
                text(
                    "SELECT UserId FROM Users "
                    "WHERE NormalizedUsername = LOWER(:username)"
                ),
                {"username": username},
            ).scalar_one_or_none()
            if user_id is None:
                continue
            database.execute(
                text("DELETE FROM SearchHistory WHERE UserId = :user_id"),
                {"user_id": user_id},
            )
            database.execute(
                text("DELETE FROM Sessions WHERE UserId = :user_id"),
                {"user_id": user_id},
            )
            database.execute(
                text("DELETE FROM UserDevices WHERE UserId = :user_id"),
                {"user_id": user_id},
            )
            database.execute(
                text("DELETE FROM Users WHERE UserId = :user_id"),
                {"user_id": user_id},
            )
        database.commit()


def cleanup_stale_test_users() -> None:
    with open_session() as database:
        usernames = [
            str(value)
            for value in database.execute(
                text(
                    "SELECT Username FROM Users "
                    "WHERE Username LIKE 'history!_a!_%' ESCAPE '!' "
                    "OR Username LIKE 'history!_b!_%' ESCAPE '!'"
                )
            ).scalars()
        ]
    if usernames:
        cleanup_users(usernames)


def main() -> None:
    cleanup_stale_test_users()
    suffix = str(int(time.time() * 1000))[-9:]
    usernames = [f"history_a_{suffix}", f"history_b_{suffix}"]
    client_a = TestClient(app, base_url="http://127.0.0.1:8765")
    client_b = TestClient(app, base_url="http://127.0.0.1:8765")

    try:
        register(client_a, usernames[0])
        register(client_b, usernames[1])

        created_a = expect(
            client_a.post(
                "/history",
                headers=HEADERS,
                json={
                    "url": "https://user:password@example.com/login?token=secret#private",
                    "rule_score": 35,
                    "risk_probability": 0.72,
                    "risk_score": 72,
                    "decision": "warn",
                    "warning_threshold": 37,
                    "blocking_threshold": 100,
                    "model_version": "url-risk-l1-logistic-1.0",
                    "policy_version": "fpr-two-threshold-1.0",
                    "feature_schema_version": "url-v2",
                    "layer_results": {"url_risk_model": {"status": "ready", "score": 72}},
                    "ml_score": 72,
                    "final_score": 72,
                    "detection_label": "phishing",
                    "model_status": "ready",
                    "source": "web-app",
                },
            ),
            201,
            "create history A",
        )
        assert created_a["url"] == "https://example.com/login"
        assert "secret" not in created_a["url"]
        assert "password" not in created_a["url"]
        assert created_a["risk_probability"] == 0.72
        assert created_a["risk_score"] == 72
        assert created_a["decision"] == "warn"
        assert created_a["model_version"] == "url-risk-l1-logistic-1.0"
        assert created_a["layer_results"]["url_risk_model"]["status"] == "ready"

        list_a = expect(client_a.get("/history", headers=HEADERS), 200, "list A")
        list_b = expect(client_b.get("/history", headers=HEADERS), 200, "list B")
        assert list_a["count"] == 1
        assert list_b["count"] == 0

        expect(
            client_b.post(
                "/history",
                headers=HEADERS,
                json={
                    "url": "https://example.org/",
                    "rule_score": 0,
                    "risk_probability": 0.04,
                    "risk_score": 4,
                    "decision": "allow",
                    "warning_threshold": 37,
                    "blocking_threshold": 100,
                    "model_version": "url-risk-l1-logistic-1.0",
                    "policy_version": "fpr-two-threshold-1.0",
                    "feature_schema_version": "url-v2",
                    "layer_results": {"url_risk_model": {"status": "ready", "score": 4}},
                    "ml_score": 4,
                    "final_score": 4,
                    "detection_label": "safe",
                    "model_status": "ready",
                    "source": "web-app",
                },
            ),
            201,
            "create history B",
        )
        expect(client_a.delete("/history", headers=HEADERS), 200, "clear A")
        assert expect(client_a.get("/history", headers=HEADERS), 200, "list cleared A")["count"] == 0
        assert expect(client_b.get("/history", headers=HEADERS), 200, "list retained B")["count"] == 1

        print("History flow passed: sanitized URL, per-user isolation, list and clear")
    finally:
        cleanup_users(usernames)


if __name__ == "__main__":
    main()
