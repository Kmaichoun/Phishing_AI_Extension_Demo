from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SearchHistoryCreate(BaseModel):
    url: str = Field(min_length=1, max_length=4096)
    rule_score: int = Field(ge=0, le=100)
    risk_probability: float | None = Field(default=None, ge=0, le=1)
    risk_score: int | None = Field(default=None, ge=0, le=100)
    decision: Literal["allow", "warn", "block"] | None = None
    warning_threshold: float | None = Field(default=None, ge=0, le=100)
    blocking_threshold: float | None = Field(default=None, ge=0, le=100)
    model_version: str | None = Field(default=None, max_length=100)
    policy_version: str | None = Field(default=None, max_length=100)
    feature_schema_version: str | None = Field(default=None, max_length=100)
    layer_results: dict[str, object] = Field(default_factory=dict)
    # Legacy aliases stay writable during the Web/Extension migration.
    ml_score: int | None = Field(default=None, ge=0, le=100)
    final_score: int = Field(ge=0, le=100)
    alpha: float | None = Field(default=None, ge=0, le=1)
    decision_threshold: float | None = Field(default=None, ge=0, le=100)
    detection_label: Literal["safe", "phishing"] | None = None
    model_status: str | None = Field(default=None, max_length=50)
    source: Literal["web-app", "qr-scanner", "web-app-react"] = "web-app"


class SearchHistoryResponse(BaseModel):
    history_id: int
    url: str
    hostname: str
    rule_score: int
    risk_probability: float | None
    risk_score: int | None
    decision: str | None
    warning_threshold: float | None
    blocking_threshold: float | None
    model_version: str | None
    policy_version: str | None
    feature_schema_version: str | None
    layer_results: dict[str, object]
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
    total: int = 0
