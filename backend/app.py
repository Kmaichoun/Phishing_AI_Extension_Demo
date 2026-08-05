from __future__ import annotations

import csv
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Literal

import joblib
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from auth_router import WEB_ORIGINS, router as auth_router
from database import database_status
from feature_extractor import (
    FEATURE_NAMES,
    FEATURE_SCHEMA_VERSION,
    extract_features,
    feature_vector,
)
from history_router import router as history_router
from llm_explainer import ExplainRequest, explain_with_llm, llm_status

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "model.pkl"
FEEDBACK_PATH = BASE_DIR / "data" / "feedback.csv"

app = FastAPI(title="Phish Radar API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(WEB_ORIGINS),
    allow_origin_regex=r"chrome-extension://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)
app.include_router(history_router)


class PredictRequest(BaseModel):
    url: str
    rule_score: int | None = Field(default=None, ge=0, le=100)


class FeedbackRequest(BaseModel):
    url: str
    user_label: Literal["dangerous", "safe", "unsure"]
    rule_score: int | None = Field(default=None, ge=0, le=100)
    ml_score: int | None = Field(default=None, ge=0, le=100)
    final_score: int | None = Field(default=None, ge=0, le=100)
    source: str | None = None


@lru_cache(maxsize=1)
def load_model_bundle() -> dict[str, object] | None:
    if not MODEL_PATH.exists():
        return None
    bundle = joblib.load(MODEL_PATH)
    if isinstance(bundle, dict) and "model" in bundle:
        return bundle
    return {"model": bundle}


def model_policy(bundle: dict[str, object] | None) -> dict[str, object]:
    if bundle is None:
        return {
            "model_version": None,
            "policy_version": "local-evidence-fallback-1.0",
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "warning_threshold": 61.0,
            "blocking_threshold": 81.0,
            "probability_method": "unavailable",
            "cv_strategy": None,
            "metrics": None,
        }
    policy = bundle.get("policy")
    if isinstance(policy, dict):
        return {
            "model_version": bundle.get("model_version"),
            "policy_version": bundle.get("policy_version"),
            "feature_schema_version": bundle.get(
                "feature_schema_version", FEATURE_SCHEMA_VERSION
            ),
            "warning_threshold": float(policy.get("warning_threshold", 61.0)),
            "blocking_threshold": float(policy.get("blocking_threshold", 81.0)),
            "warning_max_fpr": policy.get("warning_max_fpr"),
            "blocking_max_fpr": policy.get("blocking_max_fpr"),
            "probability_method": bundle.get(
                "probability_method", "intrinsic_logistic_sigmoid"
            ),
            "cv_strategy": bundle.get("cv_strategy"),
            "metrics": bundle.get("metrics"),
            "trained_at": bundle.get("trained_at"),
            "dataset_row_count": bundle.get("dataset_row_count"),
        }

    # Compatibility for a model bundle produced before Risk Model v2.
    legacy_threshold = float(bundle.get("decision_threshold", 61.0))
    return {
        "model_version": "legacy-alpha-model",
        "policy_version": "legacy-single-threshold",
        "feature_schema_version": bundle.get(
            "feature_schema_version", FEATURE_SCHEMA_VERSION
        ),
        "warning_threshold": legacy_threshold,
        "blocking_threshold": min(100.0, max(81.0, legacy_threshold + 20.0)),
        "probability_method": bundle.get("calibration", "legacy_uncalibrated"),
        "cv_strategy": bundle.get("cv_strategy"),
        "metrics": bundle.get("metrics"),
        "trained_at": bundle.get("trained_at"),
        "dataset_row_count": bundle.get("dataset_row_count"),
    }


def local_evidence_score(features: dict[str, float | int]) -> float:
    """Deterministic offline evidence score; never presented as ML probability."""
    return min(
        100.0,
        float(
            features["suspicious_word_count"] * 12
            + features["risky_tld"] * 18
            + features["has_ip_host"] * 16
            + features["has_at_symbol"] * 18
            + features["has_nested_url"] * 14
            + features["is_shortener"] * 12
            + features["credential_parameter_count"] * 5
            + features["redirect_parameter_count"] * 4
            + max(0, features["url_length"] - 90) * 0.25
        ),
    )


def risk_decision(score: float, warning_threshold: float, blocking_threshold: float) -> str:
    if score >= blocking_threshold:
        return "block"
    if score >= warning_threshold:
        return "warn"
    return "allow"


def write_feedback_csv(path: Path, row: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "timestamp",
                "url",
                "user_label",
                "rule_score",
                "ml_score",
                "final_score",
                "source",
            ],
        )
        if not exists:
            writer.writeheader()
        writer.writerow(row)
    return path


@app.get("/health")
def health():
    bundle = load_model_bundle()
    return {
        "ok": True,
        "model_ready": bundle is not None,
        "model_policy": model_policy(bundle),
        "llm": llm_status(),
        "database": database_status(),
        "feedback_path": str(FEEDBACK_PATH),
    }


@app.post("/predict")
def predict(payload: PredictRequest):
    features = extract_features(payload.url)
    bundle = load_model_bundle()
    policy = model_policy(bundle)
    model = bundle.get("model") if bundle else None

    warning_threshold = float(policy["warning_threshold"])
    blocking_threshold = float(policy["blocking_threshold"])
    rule_score = payload.rule_score

    if model is not None:
        probabilities = model.predict_proba([feature_vector(payload.url)])[0]
        class_values = list(model.classes_)
        phishing_probability = float(probabilities[class_values.index(1)])
        risk_score_value = phishing_probability * 100.0
        risk_probability: float | None = round(phishing_probability, 6)
        risk_score = int(round(risk_score_value))
        ml_score: int | None = risk_score
        confidence = round(phishing_probability, 4)
        model_status = "ready"
        risk_source = "url_risk_model"
    else:
        risk_score_value = (
            float(rule_score)
            if rule_score is not None
            else local_evidence_score(features)
        )
        risk_probability = None
        risk_score = int(round(risk_score_value))
        ml_score = None
        confidence = None
        model_status = "model_unavailable_local_evidence"
        risk_source = "local_rule_evidence"

    decision = risk_decision(
        risk_score_value, warning_threshold, blocking_threshold
    )
    label = "safe" if decision == "allow" else "phishing"

    return {
        "ok": True,
        "label": label,
        "decision": decision,
        "risk_probability": risk_probability,
        "risk_score": risk_score,
        "risk_source": risk_source,
        "warning_threshold": warning_threshold,
        "blocking_threshold": blocking_threshold,
        "risk_margin": round(risk_score_value - warning_threshold, 2),
        "model_version": policy.get("model_version"),
        "policy_version": policy.get("policy_version"),
        "feature_schema_version": policy.get("feature_schema_version"),
        "probability_method": policy.get("probability_method"),
        "model_status": model_status,
        "layer_results": {
            "normalization": {"status": "complete"},
            "url_risk_model": {
                "status": "ready" if model is not None else "unavailable",
                "score": risk_score if model is not None else None,
            },
            "local_rule_evidence": {
                "status": "evidence_only",
                "score": rule_score,
            },
            "external_reputation": {"status": "not_configured"},
            "page_context": {"status": "client_side"},
            "llm_explanation": {"status": "on_demand"},
        },
        # Temporary response aliases keep older Web/Extension builds working.
        "ml_score": ml_score,
        "confidence": confidence,
        "final_score": risk_score,
        "alpha": None,
        "decision_threshold": warning_threshold,
        "features": {name: features[name] for name in FEATURE_NAMES},
    }


@app.post("/explain")
def explain(payload: ExplainRequest):
    return explain_with_llm(payload)


@app.post("/feedback")
def feedback(payload: FeedbackRequest):
    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "url": payload.url,
        "user_label": payload.user_label,
        "rule_score": payload.rule_score,
        "ml_score": payload.ml_score,
        "final_score": payload.final_score,
        "source": payload.source or "",
    }

    try:
        saved_path = write_feedback_csv(FEEDBACK_PATH, row)
        return {"ok": True, "saved_to": str(saved_path)}
    except OSError as error:
        raise HTTPException(
            status_code=500,
            detail=f"Could not save feedback to {FEEDBACK_PATH}: {error}",
        ) from error
