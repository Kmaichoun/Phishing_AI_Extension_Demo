from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime, timedelta, timezone
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from auth_router import _require_web_client, _session_scope, require_authenticated_user
from history_models import SearchHistoryCreate, SearchHistoryList, SearchHistoryResponse
from workspace_router import audit

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
        risk_probability=(
            float(row["RiskProbability"])
            if row.get("RiskProbability") is not None
            else None
        ),
        risk_score=(
            int(row["RiskScore"]) if row.get("RiskScore") is not None else None
        ),
        decision=(
            str(row["Decision"]) if row.get("Decision") is not None else None
        ),
        warning_threshold=(
            float(row["WarningThreshold"])
            if row.get("WarningThreshold") is not None
            else None
        ),
        blocking_threshold=(
            float(row["BlockingThreshold"])
            if row.get("BlockingThreshold") is not None
            else None
        ),
        model_version=(
            str(row["ModelVersion"]) if row.get("ModelVersion") is not None else None
        ),
        policy_version=(
            str(row["PolicyVersion"]) if row.get("PolicyVersion") is not None else None
        ),
        feature_schema_version=(
            str(row["FeatureSchemaVersion"])
            if row.get("FeatureSchemaVersion") is not None
            else None
        ),
        layer_results=(
            json.loads(str(row["LayerResults"]))
            if row.get("LayerResults")
            else {}
        ),
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
    # Shared hosting migrations omit foreign keys, so delete dependent feedback explicitly.
    database.execute(text("""DELETE f FROM ScanFeedback f JOIN SearchHistory h
        ON h.HistoryId=f.HistoryId WHERE h.UserId=:user_id AND h.CreatedAt<:cutoff"""),
        {"user_id": current_user["UserId"], "cutoff": cutoff})
    database.execute(
        text("DELETE FROM SearchHistory WHERE UserId = :user_id AND CreatedAt < :cutoff"),
        {"user_id": current_user["UserId"], "cutoff": cutoff},
    )
    result = database.execute(
        text(
            """
            INSERT INTO SearchHistory
                (UserId, UserDeviceId, Url, UrlHash, Hostname, RuleScore, MlScore,
                 FinalScore, Alpha, DecisionThreshold, DetectionLabel, ModelStatus, Source,
                 RiskProbability, RiskScore, Decision, WarningThreshold, BlockingThreshold,
                 ModelVersion, PolicyVersion, FeatureSchemaVersion, LayerResults)
            VALUES
                (:user_id, :device_id, :url, :url_hash, :hostname, :rule_score, :ml_score,
                 :final_score, :alpha, :decision_threshold, :detection_label, :model_status, :source,
                 :risk_probability, :risk_score, :decision, :warning_threshold, :blocking_threshold,
                 :model_version, :policy_version, :feature_schema_version, :layer_results)
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
            "risk_probability": payload.risk_probability,
            "risk_score": payload.risk_score,
            "decision": payload.decision,
            "warning_threshold": payload.warning_threshold,
            "blocking_threshold": payload.blocking_threshold,
            "model_version": payload.model_version,
            "policy_version": payload.policy_version,
            "feature_schema_version": payload.feature_schema_version,
            "layer_results": (
                json.dumps(payload.layer_results, ensure_ascii=False, separators=(",", ":"))
                if payload.layer_results
                else None
            ),
        },
    )
    if result.lastrowid is None:
        raise RuntimeError("MySQL did not return HistoryId")
    row = database.execute(
        text(
            """
            SELECT h.HistoryId, h.Url, h.Hostname, h.RuleScore, h.MlScore,
                   h.FinalScore, h.Alpha, h.DecisionThreshold, h.DetectionLabel,
                   h.ModelStatus, h.Source, h.CreatedAt, d.DeviceName,
                   h.RiskProbability, h.RiskScore, h.Decision,
                   h.WarningThreshold, h.BlockingThreshold, h.ModelVersion,
                   h.PolicyVersion, h.FeatureSchemaVersion, h.LayerResults
            FROM SearchHistory AS h
            INNER JOIN UserDevices AS d ON d.UserDeviceId = h.UserDeviceId
            WHERE h.HistoryId = :history_id AND h.UserId = :user_id
            """
        ),
        {"history_id": int(result.lastrowid), "user_id": current_user["UserId"]},
    ).mappings().one()
    database.commit()
    return _history_response(dict(row))


@router.get("", response_model=SearchHistoryList)
def list_history(
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    q: str = Query(default='', max_length=253),
    decision: Literal['allow', 'warn', 'block'] | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    device_id: int | None = None,
    current_user: dict[str, object] = Depends(require_authenticated_user),
    database: Session = Depends(_session_scope),
) -> SearchHistoryList:
    _require_web_client(request)
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, 'วันที่เริ่มต้นต้องไม่เกินวันที่สิ้นสุด')
    filters = """h.UserId = :user_id AND h.Url LIKE :q
        AND (:decision IS NULL OR h.Decision=:decision)
        AND (:date_from IS NULL OR h.CreatedAt>=:date_from)
        AND (:date_to IS NULL OR h.CreatedAt<DATE_ADD(:date_to, INTERVAL 1 DAY))
        AND (:device_id IS NULL OR h.UserDeviceId=:device_id)"""
    params = dict(limit=limit, offset=offset, user_id=current_user['UserId'], q=f'%{q}%',
                  decision=decision, date_from=date_from, date_to=date_to, device_id=device_id)
    rows = database.execute(
        text(
            f"""
            SELECT h.HistoryId, h.Url, h.Hostname, h.RuleScore, h.MlScore,
                   h.FinalScore, h.Alpha, h.DecisionThreshold, h.DetectionLabel,
                   h.ModelStatus, h.Source, h.CreatedAt, d.DeviceName,
                   h.RiskProbability, h.RiskScore, h.Decision,
                   h.WarningThreshold, h.BlockingThreshold, h.ModelVersion,
                   h.PolicyVersion, h.FeatureSchemaVersion, h.LayerResults
            FROM SearchHistory AS h
            INNER JOIN UserDevices AS d ON d.UserDeviceId = h.UserDeviceId
            WHERE {filters}
            ORDER BY h.CreatedAt DESC, h.HistoryId DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).mappings().all()
    items = [_history_response(dict(row)) for row in rows]
    total = database.execute(text(f'SELECT COUNT(*) FROM SearchHistory h WHERE {filters}'), params).scalar_one()
    return SearchHistoryList(items=items, count=len(items), total=total)


@router.delete("")
def clear_history(
    request: Request,
    current_user: dict[str, object] = Depends(require_authenticated_user),
    database: Session = Depends(_session_scope),
) -> dict[str, int | bool]:
    _require_web_client(request)
    database.execute(text("DELETE FROM ScanFeedback WHERE UserId=:user_id"),
                     {"user_id": current_user["UserId"]})
    result = database.execute(
        text("DELETE FROM SearchHistory WHERE UserId = :user_id"),
        {"user_id": current_user["UserId"]},
    )
    deleted = max(0, int(result.rowcount or 0))
    audit(database, current_user["UserId"], "history.clear", "user", current_user["UserId"],
          {"deleted": deleted})
    database.commit()
    return {"ok": True, "deleted": deleted}
