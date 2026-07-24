from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app import app  # noqa: E402


def main() -> None:
    origin = "http://app.phishradar.localhost:5505"
    client = TestClient(app, base_url="http://api.phishradar.localhost:8765")

    response = client.options(
        "/auth/login",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-phish-radar-client",
        },
    )

    if response.status_code != 200:
        raise AssertionError(
            f"Domain CORS preflight expected 200, got {response.status_code}: {response.text}"
        )
    if response.headers.get("access-control-allow-origin") != origin:
        raise AssertionError("Backend did not return the custom Web App origin.")
    if response.headers.get("access-control-allow-credentials") != "true":
        raise AssertionError("Credentialed authentication requests are not enabled.")

    print("Custom Web App domain CORS passed.")


if __name__ == "__main__":
    main()
