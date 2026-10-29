"""Check that a built web app and its API work under one hosted origin."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ["RENDER_EXTERNAL_URL"] = "https://phishradar.example"

from app import app  # noqa: E402
from auth_router import _require_web_client  # noqa: E402


def request(method: str, host: str, origin: str | None = None) -> Request:
    headers = [(b"host", host.encode()), (b"x-phish-radar-client", b"web-app")]
    if origin is not None:
        headers.append((b"origin", origin.encode()))
    return Request({"type": "http", "method": method, "path": "/history", "headers": headers})


def main() -> None:
    assert (ROOT / "web-app/dist/index.html").is_file(), "Build the web app first"
    client = TestClient(app, base_url="https://phishradar.example")
    homepage = client.get("/")
    assert homepage.status_code == 200 and 'id="root"' in homepage.text
    assert client.get("/docs").status_code == 200
    assert client.get("/not-a-file").status_code == 404

    _require_web_client(request("GET", "phishradar.example"))
    _require_web_client(request("POST", "phishradar.example", "https://phishradar.example"))
    for candidate in (
        request("GET", "other.example"),
        request("POST", "phishradar.example"),
        request("POST", "phishradar.example", "https://other.example"),
    ):
        try:
            _require_web_client(candidate)
        except HTTPException as error:
            assert error.status_code == 403
        else:
            raise AssertionError("Unexpected client origin was accepted")
    print("Same-origin hosting passed: React, API docs, browser GET and write-origin checks.")


if __name__ == "__main__":
    main()
