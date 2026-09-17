"""Authenticated account security, feedback review and administrative operations."""
from __future__ import annotations

import json
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from auth_router import _require_web_client, _session_scope, require_authenticated_user
from model_registry import catalog

router = APIRouter(prefix="/workspace", tags=["workspace"])


def member(request: Request, user: dict = Depends(require_authenticated_user)) -> dict:
    _require_web_client(request)
    return user


def administrator(user: dict = Depends(member)) -> dict:
    if user["Role"] != "admin":
        raise HTTPException(403, "ต้องใช้สิทธิ์ผู้ดูแลระบบ")
    return user


def audit(db: Session, actor: int, action: str, kind: str, target: object, details: dict) -> None:
    db.execute(text("""INSERT INTO AuditEvents
        (ActorUserId, Action, TargetType, TargetId, Details)
        VALUES (:actor, :action, :kind, :target, :details)"""),
        dict(actor=actor, action=action, kind=kind, target=str(target),
             details=json.dumps(details, ensure_ascii=False)))


def rows(db: Session, sql: str, params: dict | None = None) -> list[dict]:
    return [dict(row) for row in db.execute(text(sql), params or {}).mappings().all()]


@router.get("/security")
def security(user: dict = Depends(member), db: Session = Depends(_session_scope)):
    devices = rows(db, """SELECT UserDeviceId AS id, DeviceName AS name,
        FirstSeenAt AS first_seen, LastSeenAt AS last_seen, IsRevoked AS revoked
        FROM UserDevices WHERE UserId=:uid ORDER BY LastSeenAt DESC""", {"uid": user["UserId"]})
    sessions = rows(db, """SELECT s.SessionId AS id, d.DeviceName AS device_name,
        s.CreatedAt AS created_at, s.LastSeenAt AS last_seen, s.ExpiresAt AS expires_at
        FROM Sessions s JOIN UserDevices d ON d.UserDeviceId=s.UserDeviceId
        WHERE s.UserId=:uid AND s.RevokedAt IS NULL AND s.ExpiresAt>UTC_TIMESTAMP(3)
        AND d.IsRevoked=0 ORDER BY s.LastSeenAt DESC""", {"uid": user["UserId"]})
    for item in devices:
        item["current"] = item["id"] == user["UserDeviceId"]
    for item in sessions:
        item["current"] = item["id"] == user["SessionId"]
    return {"devices": devices, "sessions": sessions}


@router.delete("/sessions/{session_id}")
def revoke_session(session_id: UUID, user: dict = Depends(member), db: Session = Depends(_session_scope)):
    sid = str(session_id)
    if sid == user["SessionId"]:
        raise HTTPException(400, "ใช้ปุ่มออกจากระบบเพื่อจบ Session ปัจจุบัน")
    result = db.execute(text("""UPDATE Sessions SET RevokedAt=UTC_TIMESTAMP(3)
        WHERE SessionId=:sid AND UserId=:uid AND RevokedAt IS NULL"""),
        {"sid": sid, "uid": user["UserId"]})
    if not result.rowcount:
        raise HTTPException(404, "ไม่พบ Session ที่ยกเลิกได้")
    audit(db, user["UserId"], "session.revoke", "session", sid, {})
    db.commit()
    return {"ok": True}


@router.delete("/devices/{device_id}")
def revoke_device(device_id: int, user: dict = Depends(member), db: Session = Depends(_session_scope)):
    if device_id == user["UserDeviceId"]:
        raise HTTPException(400, "ไม่สามารถยกเลิกอุปกรณ์ที่กำลังใช้งาน")
    result = db.execute(text("""UPDATE UserDevices SET IsRevoked=1, RevokedAt=UTC_TIMESTAMP(3)
        WHERE UserDeviceId=:did AND UserId=:uid AND IsRevoked=0"""),
        {"did": device_id, "uid": user["UserId"]})
    if not result.rowcount:
        raise HTTPException(404, "ไม่พบอุปกรณ์ที่ยกเลิกได้")
    db.execute(text("""UPDATE Sessions SET RevokedAt=UTC_TIMESTAMP(3)
        WHERE UserDeviceId=:did AND UserId=:uid AND RevokedAt IS NULL"""),
        {"did": device_id, "uid": user["UserId"]})
    audit(db, user["UserId"], "device.revoke", "device", device_id, {})
    db.commit()
    return {"ok": True}


class FeedbackCreate(BaseModel):
    history_id: int = Field(gt=0)
    user_label: Literal["dangerous", "safe", "unsure"]


@router.post("/feedback")
def feedback(payload: FeedbackCreate, user: dict = Depends(member), db: Session = Depends(_session_scope)):
    owned = db.execute(text("SELECT HistoryId FROM SearchHistory WHERE HistoryId=:hid AND UserId=:uid FOR UPDATE"),
        {"hid": payload.history_id, "uid": user["UserId"]}).scalar_one_or_none()
    if owned is None:
        raise HTTPException(404, "ไม่พบประวัติของบัญชีนี้ กรุณาบันทึกผลตรวจก่อนส่ง Feedback")
    # An already reviewed report is immutable; repeat submissions cannot erase a review.
    existing = db.execute(text("SELECT ReviewStatus FROM ScanFeedback WHERE HistoryId=:hid AND UserId=:uid FOR UPDATE"),
        {"hid": payload.history_id, "uid": user["UserId"]}).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(409, "ส่ง Feedback สำหรับผลตรวจนี้แล้ว")
    db.execute(text("INSERT INTO ScanFeedback (HistoryId, UserId, UserLabel) VALUES (:hid,:uid,:label)"),
        {"hid": payload.history_id, "uid": user["UserId"], "label": payload.user_label})
    db.commit()
    return {"ok": True}


@router.get("/stats")
def stats(user: dict = Depends(member), db: Session = Depends(_session_scope)):
    params = {"uid": user["UserId"]}
    totals = rows(db, """SELECT COUNT(*) AS total,
        SUM(Decision='allow') AS allowed, SUM(Decision='warn') AS warned,
        SUM(Decision='block') AS blocked FROM SearchHistory WHERE UserId=:uid""", params)[0]
    daily = rows(db, """SELECT DATE(CreatedAt) AS day, COUNT(*) AS total,
        SUM(Decision='allow') AS allowed, SUM(Decision='warn') AS warned, SUM(Decision='block') AS blocked
        FROM SearchHistory WHERE UserId=:uid AND CreatedAt>=UTC_DATE()-INTERVAL 13 DAY
        GROUP BY DATE(CreatedAt) ORDER BY day""", params)
    feedback_stats = rows(db, """SELECT COUNT(*) AS total,
        SUM(f.UserLabel='safe' AND h.Decision IN ('warn','block')) AS reported_false_positives,
        SUM(f.ReviewStatus='confirmed' AND f.UserLabel='safe' AND h.Decision IN ('warn','block')) AS confirmed_false_positives
        FROM ScanFeedback f JOIN SearchHistory h ON h.HistoryId=f.HistoryId
        WHERE f.UserId=:uid""", params)[0]
    return {"totals": totals, "daily": daily, "feedback": feedback_stats, "timezone": "UTC"}


@router.get("/admin/users")
def users(q: str = Query("", max_length=100), offset: int = Query(0, ge=0),
          user: dict = Depends(administrator), db: Session = Depends(_session_scope)):
    params = {"q": f"%{q}%", "offset": offset}
    items = rows(db, """SELECT UserId AS id, Username AS username, Email AS email,
        Role AS role, IsActive AS active, CreatedAt AS created_at, LastLoginAt AS last_login
        FROM Users WHERE Username LIKE :q OR Email LIKE :q ORDER BY UserId DESC LIMIT 30 OFFSET :offset""", params)
    total = db.execute(text("SELECT COUNT(*) FROM Users WHERE Username LIKE :q OR Email LIKE :q"), params).scalar_one()
    return {"items": items, "total": total}


class UserUpdate(BaseModel):
    role: Literal["admin", "user"]
    active: bool


@router.patch("/admin/users/{user_id}")
def update_user(user_id: int, payload: UserUpdate, user: dict = Depends(administrator), db: Session = Depends(_session_scope)):
    if user_id == user["UserId"]:
        raise HTTPException(400, "ไม่สามารถเปลี่ยนสิทธิ์หรือระงับบัญชีของตัวเอง")
    # Serialize role edits and re-check the actor inside the transaction.
    admins = rows(db, "SELECT UserId FROM Users WHERE Role='admin' AND IsActive=1 ORDER BY UserId FOR UPDATE")
    if user["UserId"] not in {item["UserId"] for item in admins}:
        raise HTTPException(403, "สิทธิ์ผู้ดูแลระบบเปลี่ยนแล้ว กรุณาเข้าสู่ระบบใหม่")
    target = rows(db, "SELECT Role, IsActive FROM Users WHERE UserId=:uid FOR UPDATE", {"uid": user_id})
    if not target:
        raise HTTPException(404, "ไม่พบบัญชี")
    if target[0]["Role"] == "admin" and target[0]["IsActive"] and len(admins) <= 1 and (payload.role != "admin" or not payload.active):
        raise HTTPException(400, "ต้องมีผู้ดูแลระบบที่ใช้งานได้อย่างน้อยหนึ่งคน")
    db.execute(text("UPDATE Users SET Role=:role, IsActive=:active WHERE UserId=:uid"),
        {"uid": user_id, "role": payload.role, "active": payload.active})
    db.execute(text("UPDATE Sessions SET RevokedAt=UTC_TIMESTAMP(3) WHERE UserId=:uid AND RevokedAt IS NULL"), {"uid": user_id})
    audit(db, user["UserId"], "user.update", "user", user_id,
          {"before": target[0], "after": payload.model_dump()})
    db.commit()
    return {"ok": True}


@router.get("/admin/feedback")
def feedback_queue(offset: int = Query(0, ge=0), state: Literal['all','pending','confirmed','dismissed'] = 'pending',
                   user: dict = Depends(administrator), db: Session = Depends(_session_scope)):
    params = {"offset": offset, "state": state}
    items = rows(db, """SELECT f.FeedbackId AS id, f.UserLabel AS user_label,
        f.ReviewStatus AS review_status, f.ReviewNote AS review_note, f.CreatedAt AS created_at,
        u.Username AS username, h.Url AS url, h.Decision AS decision, h.FinalScore AS score,
        h.ModelVersion AS model_version FROM ScanFeedback f
        JOIN Users u ON u.UserId=f.UserId JOIN SearchHistory h ON h.HistoryId=f.HistoryId
        WHERE (:state='all' OR f.ReviewStatus=:state)
        ORDER BY f.FeedbackId DESC LIMIT 30 OFFSET :offset""", params)
    total = db.execute(text("""SELECT COUNT(*) FROM ScanFeedback f
        JOIN SearchHistory h ON h.HistoryId=f.HistoryId JOIN Users u ON u.UserId=f.UserId
        WHERE (:state='all' OR f.ReviewStatus=:state)"""), params).scalar_one()
    return {"items": items, "total": total}


class FeedbackReview(BaseModel):
    status: Literal['confirmed', 'dismissed']
    note: str = Field(min_length=3, max_length=1000)

    @field_validator('note')
    @classmethod
    def meaningful_note(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError('กรุณาระบุเหตุผลอย่างน้อย 3 ตัวอักษร')
        return value


@router.patch("/admin/feedback/{feedback_id}")
def review(feedback_id: int, payload: FeedbackReview, user: dict = Depends(administrator), db: Session = Depends(_session_scope)):
    result = db.execute(text("""UPDATE ScanFeedback SET ReviewStatus=:state, ReviewNote=:note,
        ReviewedBy=:uid, ReviewedAt=UTC_TIMESTAMP(3) WHERE FeedbackId=:fid AND ReviewStatus='pending'"""),
        {"state": payload.status, "note": payload.note.strip(), "uid": user["UserId"], "fid": feedback_id})
    if not result.rowcount:
        raise HTTPException(409, "ไม่พบ Feedback ที่รอตรวจ หรือมีผู้ตรวจไปแล้ว")
    audit(db, user["UserId"], "feedback.review", "feedback", feedback_id, payload.model_dump())
    db.commit()
    return {"ok": True}


@router.get("/admin/audit")
def audit_log(offset: int = Query(0, ge=0), user: dict = Depends(administrator), db: Session = Depends(_session_scope)):
    items = rows(db, """SELECT a.AuditId AS id, a.Action AS action, a.TargetType AS target_type,
        a.TargetId AS target_id, a.Details AS details, a.CreatedAt AS created_at,
        u.Username AS actor FROM AuditEvents a LEFT JOIN Users u ON u.UserId=a.ActorUserId
        ORDER BY a.AuditId DESC LIMIT 30 OFFSET :offset""", {"offset": offset})
    return {"items": items, "total": db.execute(text("SELECT COUNT(*) FROM AuditEvents")).scalar_one()}


@router.get('/admin/models')
def model_experiments(user: dict = Depends(administrator)):
    # Reading JSON/hashes only: never train, download, or unpickle from a web request.
    return catalog()


@router.get('/admin/feedback-export')
def export_review_queue(offset: int = Query(0, ge=0), user: dict = Depends(administrator),
                        db: Session = Depends(_session_scope)):
    clause = "f.ReviewStatus='confirmed' AND f.UserLabel IN ('safe','dangerous')"
    items = rows(db, f"""SELECT f.FeedbackId AS feedback_id, h.HistoryId AS history_id,
        h.Url AS sanitized_url, f.UserLabel AS reviewed_label, f.ReviewedAt AS reviewed_at,
        h.CreatedAt AS scan_created_at, h.Decision AS decision, h.FinalScore AS score,
        h.ModelVersion AS model_version, h.PolicyVersion AS policy_version,
        h.WarningThreshold AS warning_threshold, h.BlockingThreshold AS blocking_threshold
        FROM ScanFeedback f JOIN SearchHistory h ON h.HistoryId=f.HistoryId
        WHERE {clause} ORDER BY f.FeedbackId DESC LIMIT 30 OFFSET :offset""", {'offset': offset})
    total = db.execute(text(f"""SELECT COUNT(*) FROM ScanFeedback f
        JOIN SearchHistory h ON h.HistoryId=f.HistoryId WHERE {clause}""")).scalar_one()
    for item in items:
        item['training_eligible'] = False
        item['exclusion_reason'] = 'original_url_unavailable_query_removed'
        item['source'] = 'admin_reviewed_scan_feedback'
    return {'items': items, 'total': total, 'offset': offset,
            'purpose': 'review_queue_only_not_training_data',
            'notice': 'URL ในประวัติตัด query/credentials แล้ว ต้องเก็บ URL ต้นฉบับและหลักฐานใหม่ก่อนใช้ฝึก ไม่อนุมาน label ของทั้งโดเมน'}
