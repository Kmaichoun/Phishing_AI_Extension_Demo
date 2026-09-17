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
from fuzzy_scoring import FUZZY_SCHEMA_VERSION, fuzzy_audit, fuzzy_score
from history_router import router as history_router
from workspace_router import router as workspace_router
from llm_explainer import ExplainRequest, explain_with_llm, llm_status
from risk_policy import apply_consensus_guardrail

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "model.pkl"
FEEDBACK_PATH = BASE_DIR / "data" / "feedback.csv"
LEGACY_RULE_WEIGHT = 0.40
LEGACY_ML_WEIGHT = 0.60
RISK_FORMULA = "FinalScore = 100 * LearnedFusion(FuzzyScore, RandomForestScore)"
LEGACY_RISK_FORMULA = "FinalScore = 0.40 * RuleScore + 0.60 * MLScore"

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
app.include_router(workspace_router)


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


@lru_cache(maxsize=2)
def _load_model_bundle(model_modified_ns: int) -> dict[str, object]:
    """Load one immutable model revision while avoiding disk I/O per request."""
    bundle = joblib.load(MODEL_PATH)
    if isinstance(bundle, dict) and "model" in bundle:
        return bundle
    return {"model": bundle}


def load_model_bundle() -> dict[str, object] | None:
    """Reload the model automatically whenever model.pkl is replaced."""
    try:
        model_modified_ns = MODEL_PATH.stat().st_mtime_ns
    except FileNotFoundError:
        return None
    return _load_model_bundle(model_modified_ns)


def model_policy(bundle: dict[str, object] | None) -> dict[str, object]:
    if bundle is None:
        return {
            "model_version": None,
            "policy_version": "local-evidence-fallback-1.0",
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "warning_threshold": 61.0,
            "blocking_threshold": 81.0,
            "probability_method": "unavailable",
            "rule_weight": None,
            "ml_weight": None,
            "risk_formula": RISK_FORMULA,
            "fusion_method": "unavailable",
            "fuzzy_schema_version": FUZZY_SCHEMA_VERSION,
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
            "rule_weight": bundle.get("rule_weight"),
            "ml_weight": bundle.get("ml_weight"),
            "risk_formula": bundle.get("risk_formula", RISK_FORMULA),
            "fusion_method": bundle.get("fusion_method"),
            "fusion_version": bundle.get("fusion_version"),
            "calibration_version": bundle.get("calibration_version"),
            "fuzzy_schema_version": bundle.get(
                "fuzzy_schema_version", FUZZY_SCHEMA_VERSION
            ),
            "cv_strategy": bundle.get("cv_strategy"),
            "metrics": bundle.get("metrics"),
            "trained_at": bundle.get("trained_at"),
            "dataset_row_count": bundle.get("dataset_row_count"),
            "evaluation_design": bundle.get("evaluation_design"),
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
        "rule_weight": float(bundle.get("alpha", LEGACY_RULE_WEIGHT)),
        "ml_weight": 1.0 - float(bundle.get("alpha", LEGACY_RULE_WEIGHT)),
        "risk_formula": bundle.get("risk_formula", LEGACY_RISK_FORMULA),
        "fusion_method": "legacy_fixed_blend",
        "fuzzy_schema_version": None,
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
    fusion_model = bundle.get("fusion_model") if bundle else None
    probability_calibrator = (
        bundle.get("probability_calibrator") if bundle else None
    )

    warning_threshold = float(policy["warning_threshold"])
    blocking_threshold = float(policy["blocking_threshold"])
    rule_score_value = (
        float(payload.rule_score)
        if payload.rule_score is not None
        else local_evidence_score(features)
    )
    rule_score = int(round(rule_score_value))
    fuzzy_audit_result = fuzzy_audit(rule_score_value)
    fuzzy_score_value = fuzzy_score(rule_score_value)
    fuzzy_score_rounded = int(round(fuzzy_score_value))
    rule_weight = policy.get("rule_weight")
    ml_weight = policy.get("ml_weight")
    applied_formula = str(policy.get("risk_formula") or RISK_FORMULA)
    fusion_method = policy.get("fusion_method")

    if model is not None:
        probabilities = model.predict_proba([feature_vector(payload.url)])[0]
        class_values = list(model.classes_)
        raw_phishing_probability = float(probabilities[class_values.index(1)])
        if probability_calibrator is not None:
            calibrated = probability_calibrator.predict_proba(
                [[raw_phishing_probability]]
            )[0]
            calibration_classes = list(probability_calibrator.classes_)
            phishing_probability = float(
                calibrated[calibration_classes.index(1)]
            )
            probability_calibrated = True
        else:
            phishing_probability = raw_phishing_probability
            probability_calibrated = False
        ml_score_value = phishing_probability * 100.0
        ml_score: int | None = int(round(ml_score_value))
        if fusion_method in {"ml_only", "weighted_40_60"}:
            learned_fusion_probability = None
            consensus_trigger = None
            if fusion_method == "ml_only":
                risk_score_value = ml_score_value
            else:
                risk_score_value = 0.40 * rule_score_value + 0.60 * ml_score_value
            risk_probability_value = risk_score_value / 100.0
            risk_source = "calibrated_random_forest" if fusion_method == "ml_only" else "simple_rule_ml_blend"
            fusion_applied = False
        elif fusion_model is not None:
            fusion_probabilities = fusion_model.predict_proba(
                [[fuzzy_score_value / 100.0, phishing_probability]]
            )[0]
            fusion_classes = list(fusion_model.classes_)
            risk_probability_value = float(
                fusion_probabilities[fusion_classes.index(1)]
            )
            learned_fusion_probability = risk_probability_value
            risk_probability_value, consensus_trigger = apply_consensus_guardrail(
                fuzzy_score_value / 100.0,
                phishing_probability,
                learned_fusion_probability,
            )
            risk_score_value = risk_probability_value * 100.0
            risk_source = (
                "fuzzy_random_forest_consensus_guardrail"
                if consensus_trigger
                else "fuzzy_random_forest_learned_fusion"
            )
            fusion_applied = True
        else:
            learned_fusion_probability = None
            consensus_trigger = None
            legacy_rule_weight = float(rule_weight or LEGACY_RULE_WEIGHT)
            legacy_ml_weight = float(ml_weight or LEGACY_ML_WEIGHT)
            risk_score_value = (
                legacy_rule_weight * rule_score + legacy_ml_weight * ml_score
            )
            risk_probability_value = phishing_probability
            risk_source = "legacy_fixed_rule_ml_blend"
            fusion_method = "legacy_fixed_blend"
            fusion_applied = False
        risk_probability: float | None = round(risk_probability_value, 6)
        risk_score = int(round(risk_score_value))
        confidence = round(risk_probability_value, 4)
        model_status = "ready"
        formula_applied = True
    else:
        raw_phishing_probability = None
        probability_calibrated = False
        learned_fusion_probability = None
        consensus_trigger = None
        risk_score_value = fuzzy_score_value
        risk_probability = None
        risk_score = int(round(risk_score_value))
        ml_score = None
        confidence = None
        model_status = "model_unavailable_fuzzy_evidence"
        risk_source = "local_fuzzy_evidence"
        fusion_method = "unavailable"
        fusion_applied = False
        formula_applied = False

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
        "risk_formula": applied_formula,
        "rule_weight": rule_weight,
        "ml_weight": ml_weight,
        "fuzzy_score": fuzzy_score_rounded,
        "random_forest_score": ml_score,
        "random_forest_raw_score": (
            int(round(raw_phishing_probability * 100.0))
            if raw_phishing_probability is not None
            else None
        ),
        "probability_calibrated": probability_calibrated,
        "fusion_method": fusion_method,
        "fusion_applied": fusion_applied,
        "learned_fusion_probability": (
            round(learned_fusion_probability, 6)
            if learned_fusion_probability is not None
            else None
        ),
        "consensus_trigger": consensus_trigger,
        "formula_applied": formula_applied,
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
                "score": ml_score,
                "raw_score": (
                    int(round(raw_phishing_probability * 100.0))
                    if raw_phishing_probability is not None
                    else None
                ),
                "calibrated": probability_calibrated,
                "family": bundle.get("model_family") if bundle else None,
            },
            "local_rule_evidence": {
                "status": ("explanation_only" if fusion_method == "ml_only" else
                           "weighted_input" if fusion_method == "weighted_40_60" else
                           "fuzzy_input" if model is not None else "fallback"),
                "score": rule_score,
            },
            "fuzzy_rule_evidence": {
                "status": "ready",
                "score": fuzzy_score_rounded,
                "audit": fuzzy_audit_result,
            },
            "learned_fusion": {
                "status": "ready" if fusion_applied else "unavailable",
                "method": fusion_method,
                "score": risk_score if fusion_applied else None,
            },
            "consensus_guardrail": {
                "status": ("not_used" if fusion_method in {"ml_only", "weighted_40_60"}
                           else "triggered" if consensus_trigger else "not_triggered"),
                "trigger": consensus_trigger,
            },
            "external_reputation": {"status": "not_configured"},
            "page_context": {"status": "client_side"},
            "llm_explanation": {"status": "on_demand"},
        },
        # Temporary response aliases keep older Web/Extension builds working.
        "ml_score": ml_score,
        "confidence": confidence,
        "final_score": risk_score,
        "alpha": rule_weight,
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
