from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SearchHistoryCreate(BaseModel):
    url: str = Field(min_length=1, max_length=4096)
    rule_score: int = Field(ge=0, le=100)
    ml_score: int | None = Field(default=None, ge=0, le=100)
    final_score: int = Field(ge=0, le=100)
    alpha: float | None = Field(default=None, ge=0, le=1)
    decision_threshold: float | None = Field(default=None, ge=0, le=100)
    detection_label: Literal["safe", "phishing"] | None = None
    model_status: str | None = Field(default=None, max_length=50)
    source: Literal["web-app", "qr-scanner"] = "web-app"


class SearchHistoryResponse(BaseModel):
    history_id: int
    url: str
    hostname: str
    rule_score: int
    ml_score: int | None
    final_score: int
    alpha: float | None
    decision_threshold: float | None
    detection_label: str | None
    model_status: str | None
    source: str
    device_name: str
    created_at: datetime


class SearchHistoryList(BaseModel):
    items: list[SearchHistoryResponse]
    count: int
