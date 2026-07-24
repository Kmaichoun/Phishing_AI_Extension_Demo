from __future__ import annotations

import hashlib
import os
import secrets
import threading
import time
from collections import defaultdict, deque
from collections.abc import Generator
from datetime import datetime, timedelta, timezone

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
DEVICE_COOKIE = "phish_radar_device"
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
            detail="ระบบบัญชียังเชื่อมต่อฐานข้อมูลไม่ได้ กรุณาตรวจสอบ SQL Server",
        ) from error
    finally:
        database.close()


def _require_web_client(request: Request) -> None:
    origin = request.headers.get("origin", "")
    client = request.headers.get("x-phish-radar-client", "")
    if origin not in WEB_ORIGINS or client != "web-app":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="คำขอนี้ไม่ได้มาจาก Web App ที่อนุญาต")


def _set_auth_cookies(response: Response, session_token: str, device_token: str) -> None:
    max_age = SESSION_HOURS * 60 * 60
    common = {
        "httponly": True,
        "secure": COOKIE_SECURE,
        "samesite": "lax",
        "path": "/",
    }
    response.set_cookie(SESSION_COOKIE, session_token, max_age=max_age, **common)
    response.set_cookie(DEVICE_COOKIE, device_token, max_age=60 * 60 * 24 * 365, **common)


def _clear_session_cookie(response: Response) -> None:
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
        text("SELECT PasswordHash FROM auth.Users WHERE UserId = :user_id AND IsActive = 1"),
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


def _create_or_update_device(
    database: Session,
    user_id: int,
    device_name: str,
    device_token: str,
) -> int:
    key_hash = _token_hash(device_token)
    existing = database.execute(
        text(
            """
            SELECT UserDeviceId
            FROM auth.UserDevices
            WHERE UserId = :user_id AND DeviceKeyHash = :key_hash
            """
        ),
        {"user_id": user_id, "key_hash": key_hash},
    ).scalar_one_or_none()

    if existing is not None:
        database.execute(
            text(
                """
                UPDATE auth.UserDevices
                SET DeviceName = :device_name,
                    IsRevoked = 0,
                    RevokedAt = NULL,
                    LastSeenAt = SYSUTCDATETIME()
                WHERE UserDeviceId = :device_id
                """
            ),
            {"device_name": device_name, "device_id": existing},
        )
        return int(existing)

    return int(
        database.execute(
            text(
                """
                INSERT INTO auth.UserDevices (UserId, DeviceName, DeviceKeyHash)
                OUTPUT INSERTED.UserDeviceId
                VALUES (:user_id, :device_name, :key_hash)
                """
            ),
            {"user_id": user_id, "device_name": device_name, "key_hash": key_hash},
        ).scalar_one()
    )


def _create_session(database: Session, user_id: int, device_id: int) -> str:
    session_token = secrets.token_urlsafe(32)
    now = _utc_now()
    database.execute(
        text(
            """
            UPDATE auth.Sessions
            SET RevokedAt = COALESCE(RevokedAt, :now)
            WHERE UserDeviceId = :device_id AND RevokedAt IS NULL
            """
        ),
        {"device_id": device_id, "now": now},
    )
    database.execute(
        text(
            """
            INSERT INTO auth.Sessions
                (UserId, UserDeviceId, TokenHash, CreatedAt, LastSeenAt, ExpiresAt)
            VALUES
                (:user_id, :device_id, :token_hash, :now, :now, :expires_at)
            """
        ),
        {
            "user_id": user_id,
            "device_id": device_id,
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
        device_name=str(row["DeviceName"]),
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
                   d.UserDeviceId, d.DeviceName, s.SessionId
            FROM auth.Sessions AS s
            INNER JOIN auth.Users AS u ON u.UserId = s.UserId
            INNER JOIN auth.UserDevices AS d ON d.UserDeviceId = s.UserDeviceId
            WHERE s.TokenHash = :token_hash
              AND s.RevokedAt IS NULL
              AND s.ExpiresAt > SYSUTCDATETIME()
              AND u.IsActive = 1
              AND d.IsRevoked = 0
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
            UPDATE auth.Sessions SET LastSeenAt = SYSUTCDATETIME() WHERE SessionId = :session_id;
            UPDATE auth.UserDevices SET LastSeenAt = SYSUTCDATETIME()
            WHERE UserDeviceId = (SELECT UserDeviceId FROM auth.Sessions WHERE SessionId = :session_id);
            """
        ),
        {"session_id": row["SessionId"]},
    )
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
    device_token = request.cookies.get(DEVICE_COOKIE) or secrets.token_urlsafe(32)
    hashed_password = password_hash.hash(payload.password.get_secret_value())

    try:
        user_id = int(
            database.execute(
                text(
                    """
                    INSERT INTO auth.Users (Username, PasswordHash, Email, Role)
                    OUTPUT INSERTED.UserId
                    VALUES (:username, :password_hash, :email, N'user')
                    """
                ),
                {
                    "username": payload.username,
                    "password_hash": hashed_password,
                    "email": str(payload.email).lower(),
                },
            ).scalar_one()
        )
        device_id = _create_or_update_device(database, user_id, payload.device_name, device_token)
        session_token = _create_session(database, user_id, device_id)
        database.commit()
    except IntegrityError as error:
        database.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="ชื่อผู้ใช้หรืออีเมลนี้ถูกใช้งานแล้ว",
        ) from error

    _set_auth_cookies(response, session_token, device_token)
    return UserResponse(
        user_id=user_id,
        username=payload.username,
        email=str(payload.email).lower(),
        role="user",
        device_name=payload.device_name,
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
            FROM auth.Users
            WHERE NormalizedUsername = LOWER(LTRIM(RTRIM(:identifier)))
               OR NormalizedEmail = LOWER(LTRIM(RTRIM(:identifier)))
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
    device_token = request.cookies.get(DEVICE_COOKIE) or secrets.token_urlsafe(32)
    device_id = _create_or_update_device(database, int(row["UserId"]), payload.device_name, device_token)
    session_token = _create_session(database, int(row["UserId"]), device_id)
    database.execute(
        text("UPDATE auth.Users SET LastLoginAt = SYSUTCDATETIME(), UpdatedAt = SYSUTCDATETIME() WHERE UserId = :user_id"),
        {"user_id": row["UserId"]},
    )
    database.commit()

    _set_auth_cookies(response, session_token, device_token)
    return UserResponse(
        user_id=int(row["UserId"]),
        username=str(row["Username"]),
        email=str(row["Email"]),
        role=str(row["Role"]),
        device_name=payload.device_name,
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
        row = database.execute(
            text(
                """
                UPDATE auth.Users
                SET Username = :username,
                    EmailVerified = CASE
                        WHEN LOWER(LTRIM(RTRIM(Email))) <> :email THEN 0
                        ELSE EmailVerified
                    END,
                    Email = :email,
                    UpdatedAt = SYSUTCDATETIME()
                OUTPUT INSERTED.Username, INSERTED.Email, INSERTED.Role
                WHERE UserId = :user_id AND IsActive = 1
                """
            ),
            {"username": payload.username, "email": email, "user_id": user_id},
        ).mappings().one_or_none()
        if row is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="ไม่พบบัญชีที่ใช้งานอยู่")
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
        device_name=str(current_user["DeviceName"]),
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
            UPDATE auth.Users
            SET PasswordHash = :password_hash, UpdatedAt = SYSUTCDATETIME()
            WHERE UserId = :user_id AND IsActive = 1
            """
        ),
        {"password_hash": password_hash.hash(new_password), "user_id": user_id},
    )
    revoked = database.execute(
        text(
            """
            UPDATE auth.Sessions
            SET RevokedAt = COALESCE(RevokedAt, SYSUTCDATETIME())
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
                UPDATE auth.Sessions
                SET RevokedAt = COALESCE(RevokedAt, SYSUTCDATETIME())
                WHERE TokenHash = :token_hash
                """
            ),
            {"token_hash": _token_hash(session_token)},
        )
        database.commit()
    _clear_session_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
