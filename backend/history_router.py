from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit, urlunsplit

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from auth_router import _require_web_client, _session_scope, require_authenticated_user
from history_models import SearchHistoryCreate, SearchHistoryList, SearchHistoryResponse

router = APIRouter(prefix="/history", tags=["search-history"])
RETENTION_DAYS = max(1, int(os.getenv("SEARCH_HISTORY_RETENTION_DAYS", "90")))


def _safe_history_url(raw_url: str) -> tuple[str, str, bytes]:
    try:
        parsed = urlsplit(raw_url.strip())
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="รูปแบบ URL ไม่ถูกต้อง") from error
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="รองรับเฉพาะ URL แบบ http หรือ https")
    try:
        port = f":{parsed.port}" if parsed.port else ""
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="port ใน URL ไม่ถูกต้อง") from error
    hostname = parsed.hostname.rstrip(".").lower()
    display_host = f"[{hostname}]" if ":" in hostname and not hostname.startswith("[") else hostname
    safe_url = urlunsplit(
        (parsed.scheme.lower(), f"{display_host}{port}", parsed.path or "/", "", "")
    )[:2048]
    return safe_url, hostname[:253], hashlib.sha256(safe_url.encode("utf-8")).digest()


def _history_response(row: dict[str, object]) -> SearchHistoryResponse:
    return SearchHistoryResponse(
        history_id=int(row["HistoryId"]),
        url=str(row["Url"]),
        hostname=str(row["Hostname"]),
        rule_score=int(row["RuleScore"]),
        ml_score=int(row["MlScore"]) if row["MlScore"] is not None else None,
        final_score=int(row["FinalScore"]),
        alpha=float(row["Alpha"]) if row["Alpha"] is not None else None,
        decision_threshold=float(row["DecisionThreshold"]) if row["DecisionThreshold"] is not None else None,
        detection_label=str(row["DetectionLabel"]) if row["DetectionLabel"] is not None else None,
        model_status=str(row["ModelStatus"]) if row["ModelStatus"] is not None else None,
        source=str(row["Source"]),
        device_name=str(row["DeviceName"]),
        created_at=row["CreatedAt"],
    )


@router.post("", response_model=SearchHistoryResponse, status_code=status.HTTP_201_CREATED)
def create_history(
    payload: SearchHistoryCreate,
    request: Request,
    current_user: dict[str, object] = Depends(require_authenticated_user),
    database: Session = Depends(_session_scope),
) -> SearchHistoryResponse:
    _require_web_client(request)
    safe_url, hostname, url_hash = _safe_history_url(payload.url)
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=RETENTION_DAYS)
    database.execute(
        text("DELETE FROM auth.SearchHistory WHERE UserId = :user_id AND CreatedAt < :cutoff"),
        {"user_id": current_user["UserId"], "cutoff": cutoff},
    )
    row = database.execute(
        text(
            """
            INSERT INTO auth.SearchHistory
                (UserId, UserDeviceId, Url, UrlHash, Hostname, RuleScore, MlScore,
                 FinalScore, Alpha, DecisionThreshold, DetectionLabel, ModelStatus, Source)
            OUTPUT INSERTED.HistoryId, INSERTED.Url, INSERTED.Hostname,
                   INSERTED.RuleScore, INSERTED.MlScore, INSERTED.FinalScore,
                   INSERTED.Alpha, INSERTED.DecisionThreshold, INSERTED.DetectionLabel,
                   INSERTED.ModelStatus, INSERTED.Source, INSERTED.CreatedAt
            VALUES
                (:user_id, :device_id, :url, :url_hash, :hostname, :rule_score, :ml_score,
                 :final_score, :alpha, :decision_threshold, :detection_label, :model_status, :source)
            """
        ),
        {
            "user_id": current_user["UserId"],
            "device_id": current_user["UserDeviceId"],
            "url": safe_url,
            "url_hash": url_hash,
            "hostname": hostname,
            "rule_score": payload.rule_score,
            "ml_score": payload.ml_score,
            "final_score": payload.final_score,
            "alpha": payload.alpha,
            "decision_threshold": payload.decision_threshold,
            "detection_label": payload.detection_label,
            "model_status": payload.model_status,
            "source": payload.source,
        },
    ).mappings().one()
    database.commit()
    values = dict(row)
    values["DeviceName"] = current_user["DeviceName"]
    return _history_response(values)


@router.get("", response_model=SearchHistoryList)
def list_history(
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
    current_user: dict[str, object] = Depends(require_authenticated_user),
    database: Session = Depends(_session_scope),
) -> SearchHistoryList:
    _require_web_client(request)
    rows = database.execute(
        text(
            """
            SELECT TOP (:limit)
                   h.HistoryId, h.Url, h.Hostname, h.RuleScore, h.MlScore,
                   h.FinalScore, h.Alpha, h.DecisionThreshold, h.DetectionLabel,
                   h.ModelStatus, h.Source, h.CreatedAt, d.DeviceName
            FROM auth.SearchHistory AS h
            INNER JOIN auth.UserDevices AS d ON d.UserDeviceId = h.UserDeviceId
            WHERE h.UserId = :user_id
            ORDER BY h.CreatedAt DESC, h.HistoryId DESC
            """
        ),
        {"limit": limit, "user_id": current_user["UserId"]},
    ).mappings().all()
    items = [_history_response(dict(row)) for row in rows]
    return SearchHistoryList(items=items, count=len(items))


@router.delete("")
def clear_history(
    request: Request,
    current_user: dict[str, object] = Depends(require_authenticated_user),
    database: Session = Depends(_session_scope),
) -> dict[str, int | bool]:
    _require_web_client(request)
    result = database.execute(
        text("DELETE FROM auth.SearchHistory WHERE UserId = :user_id"),
        {"user_id": current_user["UserId"]},
    )
    database.commit()
    return {"ok": True, "deleted": max(0, int(result.rowcount or 0))}
