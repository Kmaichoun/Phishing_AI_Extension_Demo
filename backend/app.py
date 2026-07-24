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
from feature_extractor import FEATURE_NAMES, extract_features, feature_vector
from history_router import router as history_router
from llm_explainer import ExplainRequest, explain_with_llm, llm_status

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "model.pkl"
FEEDBACK_PATH = BASE_DIR / "data" / "feedback.csv"

app = FastAPI(title="Phish Radar API", version="1.2.0")
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
            "alpha": 0.6,
            "decision_threshold": 61.0,
            "calibration": "none_fallback",
            "cv_strategy": None,
            "metrics": None,
        }
    return {
        "alpha": float(bundle.get("alpha", 0.6)),
        "decision_threshold": float(bundle.get("decision_threshold", 61.0)),
        "calibration": bundle.get("calibration", "legacy_uncalibrated"),
        "cv_strategy": bundle.get("cv_strategy"),
        "metrics": bundle.get("metrics"),
        "trained_at": bundle.get("trained_at"),
        "dataset_row_count": bundle.get("dataset_row_count"),
    }


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

    if model is None:
        ml_score_value = min(
            100,
            float(
                features["suspicious_word_count"] * 12
                + features["risky_tld"] * 18
                + features["has_ip_host"] * 16
                + features["has_at_symbol"] * 18
                + features["has_nested_url"] * 14
                + features["is_shortener"] * 12
                + max(0, features["url_length"] - 90) * 0.25
            ),
        )
        ml_score = int(round(ml_score_value))
        confidence = round(ml_score / 100, 4)
        model_status = "fallback_heuristic_no_model"
    else:
        probabilities = model.predict_proba([feature_vector(payload.url)])[0]
        class_values = list(model.classes_)
        phishing_probability = float(probabilities[class_values.index(1)])
        ml_score_value = phishing_probability * 100.0
        ml_score = int(round(ml_score_value))
        confidence = round(phishing_probability, 4)
        model_status = (
            "calibrated_model"
            if policy["calibration"] in {"sigmoid", "isotonic"}
            else "legacy_model"
        )

    rule_score = payload.rule_score
    alpha = float(policy["alpha"])
    threshold = float(policy["decision_threshold"])
    final_score_value = (
        ml_score_value
        if rule_score is None
        else rule_score * alpha + ml_score_value * (1.0 - alpha)
    )
    final_score = int(round(final_score_value))
    label = "phishing" if final_score_value >= threshold else "safe"

    return {
        "ok": True,
        "label": label,
        "ml_score": ml_score,
        "confidence": confidence,
        "final_score": final_score,
        "alpha": alpha,
        "decision_threshold": threshold,
        "risk_margin": round(final_score_value - threshold, 2),
        "model_status": model_status,
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
