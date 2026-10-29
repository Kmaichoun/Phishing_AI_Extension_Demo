from __future__ import annotations

import hashlib
import os
import secrets
import threading
import time
import uuid
from collections import defaultdict, deque
from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pwdlib import PasswordHash
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from auth_models import (
    LoginRequest,
    PasswordChangeRequest,
    PasswordChangeResponse,
    ProfileUpdateRequest,
    RegisterRequest,
    UserResponse,
)
from database import database_status, open_session

router = APIRouter(prefix="/auth", tags=["authentication"])
password_hash = PasswordHash.recommended()

SESSION_COOKIE = "phish_radar_session"
SESSION_HOURS = max(1, int(os.getenv("AUTH_SESSION_HOURS", "168")))
COOKIE_SECURE = os.getenv("AUTH_COOKIE_SECURE", "false").lower() in {"1", "true", "yes"}
WEB_ORIGINS = {
    value.strip()
    for value in os.getenv(
        "AUTH_WEB_ORIGINS",
        "http://app.phishradar.localhost:5505,http://127.0.0.1:5505,http://localhost:5505",
    ).split(",")
    if value.strip()
}
if render_origin := os.getenv("RENDER_EXTERNAL_URL", "").strip().rstrip("/"):
    WEB_ORIGINS.add(render_origin)

FAIL_WINDOW_SECONDS = 300
FAIL_LIMIT = 5
_failed_logins: dict[str, deque[float]] = defaultdict(deque)
_failed_login_lock = threading.Lock()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _token_hash(value: str) -> bytes:
    return hashlib.sha256(value.encode("utf-8")).digest()


def _session_scope() -> Generator[Session, None, None]:
    database = open_session()
    try:
        yield database
    except SQLAlchemyError as error:
        database.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ระบบบัญชียังเชื่อมต่อฐานข้อมูลไม่ได้ กรุณาตรวจสอบ MySQL/MariaDB",
        ) from error
    finally:
        database.close()


def _require_web_client(request: Request) -> None:
    origin = request.headers.get("origin", "")
    client = request.headers.get("x-phish-radar-client", "")
    host = request.headers.get("host", "").lower()
    same_origin_get = (
        request.method in {"GET", "HEAD"}
        and not origin
        and any(urlsplit(allowed).netloc.lower() == host for allowed in WEB_ORIGINS)
    )
    if client != "web-app" or (origin not in WEB_ORIGINS and not same_origin_get):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="คำขอนี้ไม่ได้มาจาก Web App ที่อนุญาต")


def _set_auth_cookies(response: Response, session_token: str) -> None:
    max_age = SESSION_HOURS * 60 * 60
    common = {
        "httponly": True,
        "secure": COOKIE_SECURE,
        "samesite": "lax",
        "path": "/",
    }
    response.set_cookie(SESSION_COOKIE, session_token, max_age=max_age, **common)
    _clear_legacy_device_cookie(response)


def _clear_legacy_device_cookie(response: Response) -> None:
    # Remove the persistent identifier issued by older versions, without reading it.
    response.delete_cookie("phish_radar_device", path="/", httponly=True,
                           secure=COOKIE_SECURE, samesite="lax")


def _clear_session_cookie(response: Response) -> None:
    _clear_legacy_device_cookie(response)
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
    )


def _attempt_key(request: Request, identifier: str) -> str:
    address = request.client.host if request.client else "unknown"
    return f"{address}:{identifier.strip().lower()}"


def _is_rate_limited(key: str) -> bool:
    now = time.monotonic()
    with _failed_login_lock:
        attempts = _failed_logins[key]
        while attempts and now - attempts[0] > FAIL_WINDOW_SECONDS:
            attempts.popleft()
        return len(attempts) >= FAIL_LIMIT


def _record_failure(key: str) -> None:
    with _failed_login_lock:
        _failed_logins[key].append(time.monotonic())


def _clear_failures(key: str) -> None:
    with _failed_login_lock:
        _failed_logins.pop(key, None)


def _verify_current_password(
    database: Session,
    request: Request,
    user_id: int,
    candidate: str,
) -> None:
    key = _attempt_key(request, f"account-settings:{user_id}")
    if _is_rate_limited(key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="ยืนยันรหัสผ่านผิดหลายครั้งเกินไป กรุณารอ 5 นาทีแล้วลองใหม่",
        )

    stored_hash = database.execute(
        text("SELECT PasswordHash FROM Users WHERE UserId = :user_id AND IsActive = 1"),
        {"user_id": user_id},
    ).scalar_one_or_none()

    valid = False
    if stored_hash is not None:
        try:
            valid = password_hash.verify(candidate, str(stored_hash))
        except Exception:
            valid = False

    if not valid:
        _record_failure(key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="รหัสผ่านปัจจุบันไม่ถูกต้อง",
        )
    _clear_failures(key)


def _create_session(database: Session, user_id: int, previous_token: str | None = None) -> str:
    session_token = secrets.token_urlsafe(32)
    session_id = str(uuid.uuid4())
    now = _utc_now()
    # Replace only the session presented by this client; other logins stay active.
    if previous_token:
        database.execute(
            text("""UPDATE Sessions SET RevokedAt = :now
                WHERE TokenHash = :token_hash AND UserId = :user_id AND RevokedAt IS NULL"""),
            {"token_hash": _token_hash(previous_token), "user_id": user_id, "now": now},
        )
    database.execute(
        text(
            """
            INSERT INTO Sessions
                (SessionId, UserId, TokenHash, CreatedAt, LastSeenAt, ExpiresAt)
            VALUES
                (:session_id, :user_id, :token_hash, :now, :now, :expires_at)
            """
        ),
        {
            "session_id": session_id,
            "user_id": user_id,
            "token_hash": _token_hash(session_token),
            "now": now,
            "expires_at": now + timedelta(hours=SESSION_HOURS),
        },
    )
    return session_token


def _user_response(row: dict[str, object]) -> UserResponse:
    return UserResponse(
        user_id=int(row["UserId"]),
        username=str(row["Username"]),
        email=str(row["Email"]),
        role=str(row["Role"]),
    )


def require_authenticated_user(
    request: Request,
    response: Response,
    database: Session = Depends(_session_scope),
) -> dict[str, object]:
    session_token = request.cookies.get(SESSION_COOKIE)
    if not session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="ยังไม่ได้เข้าสู่ระบบ")

    row = database.execute(
        text(
            """
            SELECT u.UserId, u.Username, u.Email, u.Role,
                   s.SessionId
            FROM Sessions AS s
            INNER JOIN Users AS u ON u.UserId = s.UserId
            WHERE s.TokenHash = :token_hash
              AND s.RevokedAt IS NULL
              AND s.ExpiresAt > UTC_TIMESTAMP(3)
              AND u.IsActive = 1
            """
        ),
        {"token_hash": _token_hash(session_token)},
    ).mappings().first()
    if row is None:
        _clear_session_cookie(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session หมดอายุ กรุณาเข้าสู่ระบบใหม่")

    database.execute(
        text(
            """
            UPDATE Sessions
            SET LastSeenAt = UTC_TIMESTAMP(3)
            WHERE SessionId = :session_id
            """
        ),
        {"session_id": row["SessionId"]},
    )
    _clear_legacy_device_cookie(response)
    database.commit()
    return dict(row)


@router.get("/health")
def auth_health() -> dict[str, object]:
    return database_status()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    database: Session = Depends(_session_scope),
) -> UserResponse:
    _require_web_client(request)
    hashed_password = password_hash.hash(payload.password.get_secret_value())

    try:
        result = database.execute(
            text(
                """
                INSERT INTO Users (Username, PasswordHash, Email, Role)
                VALUES (:username, :password_hash, :email, 'user')
                """
            ),
            {
                "username": payload.username,
                "password_hash": hashed_password,
                "email": str(payload.email).lower(),
            },
        )
        if result.lastrowid is None:
            raise RuntimeError("MySQL did not return UserId")
        user_id = int(result.lastrowid)
        session_token = _create_session(database, user_id, request.cookies.get(SESSION_COOKIE))
        database.commit()
    except IntegrityError as error:
        database.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="ชื่อผู้ใช้หรืออีเมลนี้ถูกใช้งานแล้ว",
        ) from error

    _set_auth_cookies(response, session_token)
    return UserResponse(
        user_id=user_id,
        username=payload.username,
        email=str(payload.email).lower(),
        role="user",
    )


@router.post("/login", response_model=UserResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    database: Session = Depends(_session_scope),
) -> UserResponse:
    _require_web_client(request)
    key = _attempt_key(request, payload.identifier)
    if _is_rate_limited(key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="ลองเข้าสู่ระบบหลายครั้งเกินไป กรุณารอ 5 นาทีแล้วลองใหม่",
        )

    row = database.execute(
        text(
            """
            SELECT UserId, Username, Email, PasswordHash, Role, IsActive
            FROM Users
            WHERE NormalizedUsername = LOWER(TRIM(:identifier))
               OR NormalizedEmail = LOWER(TRIM(:identifier))
            """
        ),
        {"identifier": payload.identifier},
    ).mappings().first()

    valid = False
    if row is not None and bool(row["IsActive"]):
        try:
            valid = password_hash.verify(payload.password.get_secret_value(), str(row["PasswordHash"]))
        except Exception:
            valid = False

    if not valid:
        _record_failure(key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ชื่อผู้ใช้ อีเมล หรือรหัสผ่านไม่ถูกต้อง",
        )

    _clear_failures(key)
    session_token = _create_session(database, int(row["UserId"]), request.cookies.get(SESSION_COOKIE))
    database.execute(
        text("UPDATE Users SET LastLoginAt = UTC_TIMESTAMP(3), UpdatedAt = UTC_TIMESTAMP(3) WHERE UserId = :user_id"),
        {"user_id": row["UserId"]},
    )
    database.commit()

    _set_auth_cookies(response, session_token)
    return UserResponse(
        user_id=int(row["UserId"]),
        username=str(row["Username"]),
        email=str(row["Email"]),
        role=str(row["Role"]),
    )


@router.get("/me", response_model=UserResponse)
def me(
    current_user: dict[str, object] = Depends(require_authenticated_user),
) -> UserResponse:
    return _user_response(current_user)


@router.patch("/profile", response_model=UserResponse)
def update_profile(
    payload: ProfileUpdateRequest,
    request: Request,
    current_user: dict[str, object] = Depends(require_authenticated_user),
    database: Session = Depends(_session_scope),
) -> UserResponse:
    _require_web_client(request)
    user_id = int(current_user["UserId"])
    _verify_current_password(
        database,
        request,
        user_id,
        payload.current_password.get_secret_value(),
    )
    email = str(payload.email).lower()

    try:
        result = database.execute(
            text(
                """
                UPDATE Users
                SET Username = :username,
                    EmailVerified = CASE
                        WHEN LOWER(TRIM(Email)) <> :email THEN 0
                        ELSE EmailVerified
                    END,
                    Email = :email,
                    UpdatedAt = UTC_TIMESTAMP(3)
                WHERE UserId = :user_id AND IsActive = 1
                """
            ),
            {"username": payload.username, "email": email, "user_id": user_id},
        )
        if result.rowcount != 1:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="ไม่พบบัญชีที่ใช้งานอยู่")
        row = database.execute(
            text(
                """
                SELECT Username, Email, Role
                FROM Users
                WHERE UserId = :user_id AND IsActive = 1
                """
            ),
            {"user_id": user_id},
        ).mappings().one()
        database.commit()
    except IntegrityError as error:
        database.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="ชื่อผู้ใช้หรืออีเมลนี้ถูกใช้งานแล้ว",
        ) from error

    return UserResponse(
        user_id=user_id,
        username=str(row["Username"]),
        email=str(row["Email"]),
        role=str(row["Role"]),
    )


@router.post("/change-password", response_model=PasswordChangeResponse)
def change_password(
    payload: PasswordChangeRequest,
    request: Request,
    current_user: dict[str, object] = Depends(require_authenticated_user),
    database: Session = Depends(_session_scope),
) -> PasswordChangeResponse:
    _require_web_client(request)
    user_id = int(current_user["UserId"])
    current_password = payload.current_password.get_secret_value()
    new_password = payload.new_password.get_secret_value()
    _verify_current_password(database, request, user_id, current_password)
    if current_password == new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="รหัสผ่านใหม่ต้องไม่ซ้ำกับรหัสผ่านปัจจุบัน",
        )

    database.execute(
        text(
            """
            UPDATE Users
            SET PasswordHash = :password_hash, UpdatedAt = UTC_TIMESTAMP(3)
            WHERE UserId = :user_id AND IsActive = 1
            """
        ),
        {"password_hash": password_hash.hash(new_password), "user_id": user_id},
    )
    revoked = database.execute(
        text(
            """
            UPDATE Sessions
            SET RevokedAt = COALESCE(RevokedAt, UTC_TIMESTAMP(3))
            WHERE UserId = :user_id
              AND SessionId <> :session_id
              AND RevokedAt IS NULL
            """
        ),
        {"user_id": user_id, "session_id": current_user["SessionId"]},
    ).rowcount
    database.commit()
    return PasswordChangeResponse(ok=True, other_sessions_revoked=max(0, int(revoked or 0)))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    database: Session = Depends(_session_scope),
) -> Response:
    _require_web_client(request)
    session_token = request.cookies.get(SESSION_COOKIE)
    if session_token:
        database.execute(
            text(
                """
                UPDATE Sessions
                SET RevokedAt = COALESCE(RevokedAt, UTC_TIMESTAMP(3))
                WHERE TokenHash = :token_hash
                """
            ),
            {"token_hash": _token_hash(session_token)},
        )
        database.commit()
    _clear_session_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
