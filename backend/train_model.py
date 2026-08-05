from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from build_dataset import calculate_rule_scores
from feature_extractor import FEATURE_NAMES, FEATURE_SCHEMA_VERSION, feature_vector

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
GENERATED_DATASET_PATH = DATA_DIR / "training_urls.csv"
SEED_DATASET_PATH = DATA_DIR / "seed_urls.csv"
MODEL_PATH = BASE_DIR / "model.pkl"
REPORT_PATH = DATA_DIR / "risk_model_evaluation.json"
MODEL_COMPRESSION: tuple[str, int] = ("lzma", 3)
MODEL_VERSION = "url-risk-l1-logistic-1.1"
POLICY_VERSION = "fixed-blend-40-60-fpr-1.0"
RULE_WEIGHT = 0.40
ML_WEIGHT = 0.60
RISK_FORMULA = "FinalScore = 0.40 * RuleScore + 0.60 * MLScore"
DEFAULT_C_VALUES = (0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0)


def parse_args() -> argparse.Namespace:
    default_dataset = (
        GENERATED_DATASET_PATH if GENERATED_DATASET_PATH.exists() else SEED_DATASET_PATH
    )
    parser = argparse.ArgumentParser(
        description=(
            "Train an explainable L1-logistic URL risk model and select warning/blocking "
            "thresholds under explicit false-positive-rate constraints."
        )
    )
    parser.add_argument("--dataset", type=Path, default=default_dataset)
    parser.add_argument("--cv-folds", type=int, default=5)
    parser.add_argument("--holdout-folds", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--warn-max-fpr", type=float, default=0.01)
    parser.add_argument("--block-max-fpr", type=float, default=0.001)
    parser.add_argument(
        "--c-values",
        type=float,
        nargs="+",
        default=list(DEFAULT_C_VALUES),
        help="Inverse L1 regularization strengths evaluated with grouped cross-validation.",
    )
    return parser.parse_args()


def clean_key(value: object) -> str:
    return str(value or "").strip().lstrip("\ufeff").lower()


def hostname_group(url: str) -> str:
    try:
        return (urlsplit(url).hostname or url).rstrip(".").lower()
    except ValueError:
        return url.casefold()


def load_rows(path: Path) -> dict[str, object]:
    urls: list[str] = []
    labels: list[int] = []
    rule_scores: list[float | None] = []
    groups: list[str] = []
    sources: list[str] = []

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        reader.fieldnames = [clean_key(name) for name in (reader.fieldnames or [])]
        if "url" not in reader.fieldnames or "label" not in reader.fieldnames:
            raise ValueError(
                "CSV must have columns named url,label. "
                f"Found columns: {reader.fieldnames}"
            )

        seen_urls: set[str] = set()
        for raw_row in reader:
            row = {clean_key(key): value for key, value in raw_row.items()}
            url = (row.get("url") or "").strip()
            label_text = (row.get("label") or "").strip()
            if not url or label_text not in {"0", "1"}:
                continue
            url_key = url.casefold()
            if url_key in seen_urls:
                continue
            seen_urls.add(url_key)
            urls.append(url)
            labels.append(int(label_text))
            groups.append((row.get("group") or "").strip() or hostname_group(url))
            sources.append((row.get("source") or "unknown").strip() or "unknown")
            score_text = (row.get("rule_score") or "").strip()
            rule_scores.append(float(score_text) if score_text else None)

    missing = [index for index, score in enumerate(rule_scores) if score is None]
    if missing:
        print(f"Calculating {len(missing):,} missing RuleScore values...")
        calculated = calculate_rule_scores([urls[index] for index in missing])
        for index, score in zip(missing, calculated, strict=True):
            rule_scores[index] = float(score)

    return {
        "urls": urls,
        "x": np.asarray([feature_vector(url) for url in urls], dtype=np.float64),
        "y": np.asarray(labels, dtype=np.int64),
        "rule": np.asarray(rule_scores, dtype=np.float64),
        "groups": np.asarray(groups, dtype=object),
        "sources": sources,
    }


def validate_dataset(data: dict[str, object]) -> None:
    y = data["y"]
    groups = data["groups"]
    if not isinstance(y, np.ndarray) or not isinstance(groups, np.ndarray):
        raise TypeError("Dataset arrays were not loaded correctly.")
    if len(y) < 10:
        raise ValueError(f"Dataset is too small: {len(y)} rows")
    if set(np.unique(y)) != {0, 1}:
        raise ValueError("Dataset must contain legitimate (0) and phishing (1) labels.")
    for label in (0, 1):
        unique_groups = len(set(groups[y == label]))
        if unique_groups < 2:
            raise ValueError(f"Class {label} needs at least two unique hostname groups.")


def supported_fold_count(y: np.ndarray, groups: np.ndarray, requested: int) -> int:
    per_class = [len(set(groups[y == label])) for label in (0, 1)]
    return min(requested, min(per_class))


def split_indices(
    y: np.ndarray,
    groups: np.ndarray,
    requested_folds: int,
    seed: int,
) -> tuple[list[tuple[np.ndarray, np.ndarray]], int]:
    folds = supported_fold_count(y, groups, requested_folds)
    if folds < 2:
        raise ValueError("Not enough hostname groups for grouped cross-validation.")
    splitter = StratifiedGroupKFold(n_splits=folds, shuffle=True, random_state=seed)
    dummy = np.zeros((len(y), 1), dtype=np.float64)
    return list(splitter.split(dummy, y, groups)), folds


def make_model(c_value: float, seed: int) -> Pipeline:
    return Pipeline(
        [
            ("scale", StandardScaler()),
            (
                "logistic",
                LogisticRegression(
                    penalty="l1",
                    solver="liblinear",
                    C=float(c_value),
                    class_weight="balanced",
                    max_iter=5_000,
                    random_state=seed,
                ),
            ),
        ]
    )


def safe_float(value: float) -> float | None:
    return None if not math.isfinite(value) else round(float(value), 6)


def probability_metrics(y_true: np.ndarray, scores: np.ndarray) -> dict[str, float | None]:
    return {
        "brier_score": safe_float(brier_score_loss(y_true, scores)),
        "log_loss": safe_float(log_loss(y_true, scores, labels=[0, 1])),
        "roc_auc": safe_float(roc_auc_score(y_true, scores)),
        "pr_auc": safe_float(average_precision_score(y_true, scores)),
    }


def blend_scores(rule_scores: np.ndarray, ml_probabilities: np.ndarray) -> np.ndarray:
    """Return the fixed 40% RuleScore + 60% MLScore on a normalized 0-1 scale."""
    rounded_rule_scores = np.rint(np.clip(rule_scores, 0.0, 1.0) * 100.0)
    rounded_ml_scores = np.rint(np.clip(ml_probabilities, 0.0, 1.0) * 100.0)
    return (
        RULE_WEIGHT * rounded_rule_scores + ML_WEIGHT * rounded_ml_scores
    ) / 100.0


def classification_metrics(
    y_true: np.ndarray,
    scores: np.ndarray,
    threshold: float,
) -> dict[str, float | int | None]:
    predicted = (scores >= threshold).astype(np.int64)
    tn, fp, fn, tp = confusion_matrix(y_true, predicted, labels=[0, 1]).ravel()
    fpr = fp / (fp + tn) if fp + tn else 0.0
    negative_count = fp + tn
    # One-sided 95% Wilson upper confidence bound. Selecting against the
    # bound is deliberately more conservative than selecting against the
    # observed FPR alone, especially for the blocking policy.
    z = 1.6448536269514722
    if negative_count:
        denominator = 1.0 + (z * z / negative_count)
        center = fpr + (z * z / (2.0 * negative_count))
        spread = z * math.sqrt(
            (fpr * (1.0 - fpr) / negative_count)
            + (z * z / (4.0 * negative_count * negative_count))
        )
        fpr_upper_95 = min(1.0, (center + spread) / denominator)
    else:
        fpr_upper_95 = 0.0
    return {
        "threshold": round(float(threshold), 4),
        "precision": safe_float(precision_score(y_true, predicted, zero_division=0)),
        "recall": safe_float(recall_score(y_true, predicted, zero_division=0)),
        "f1": safe_float(f1_score(y_true, predicted, zero_division=0)),
        "roc_auc": safe_float(roc_auc_score(y_true, scores)),
        "pr_auc": safe_float(average_precision_score(y_true, scores)),
        "false_positive_rate": safe_float(fpr),
        "false_positive_rate_upper_95": safe_float(fpr_upper_95),
        "true_negative": int(tn),
        "false_positive": int(fp),
        "false_negative": int(fn),
        "true_positive": int(tp),
    }


def oof_probabilities(
    x: np.ndarray,
    y: np.ndarray,
    groups: np.ndarray,
    c_value: float,
    folds: int,
    seed: int,
) -> tuple[np.ndarray, int]:
    splits, fold_count = split_indices(y, groups, folds, seed)
    scores = np.zeros(len(y), dtype=np.float64)
    assigned = np.zeros(len(y), dtype=bool)
    for fold, (train_index, test_index) in enumerate(splits, start=1):
        model = make_model(c_value, seed + fold)
        model.fit(x[train_index], y[train_index])
        scores[test_index] = model.predict_proba(x[test_index])[:, 1]
        assigned[test_index] = True
    if not np.all(assigned):
        raise RuntimeError("Every development row must receive one out-of-fold probability.")
    return scores, fold_count


def choose_regularization(
    x: np.ndarray,
    y: np.ndarray,
    groups: np.ndarray,
    c_values: list[float],
    folds: int,
    seed: int,
) -> tuple[float, np.ndarray, list[dict[str, object]], int]:
    candidates: list[dict[str, object]] = []
    score_by_c: dict[float, np.ndarray] = {}
    effective_folds = 0
    for c_value in sorted({float(value) for value in c_values if value > 0}):
        scores, effective_folds = oof_probabilities(
            x, y, groups, c_value, folds, seed
        )
        score_by_c[c_value] = scores
        metrics = probability_metrics(y, scores)
        candidates.append({"c": c_value, **metrics})
        print(
            f"C={c_value:g}: log_loss={metrics['log_loss']}, "
            f"brier={metrics['brier_score']}, ROC-AUC={metrics['roc_auc']}"
        )
    if not candidates:
        raise ValueError("At least one positive C value is required.")
    ordered = sorted(
        candidates,
        key=lambda item: (
            float(item["log_loss"]),
            float(item["brier_score"]),
            -float(item["roc_auc"]),
            float(item["c"]),
        ),
    )
    selected_c = float(ordered[0]["c"])
    return selected_c, score_by_c[selected_c], ordered, effective_folds


def select_threshold(
    y: np.ndarray,
    scores: np.ndarray,
    max_fpr: float,
    minimum_threshold: float = 0.01,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    candidates: list[dict[str, object]] = []
    threshold_grid = np.unique(
        np.append(np.linspace(max(0.01, minimum_threshold), 0.99, 99), 1.0)
    )
    for threshold in threshold_grid:
        metrics = classification_metrics(y, scores, float(threshold))
        candidates.append(metrics)

    feasible = [
        item for item in candidates
        if float(item["false_positive_rate_upper_95"]) <= max_fpr
    ]
    if feasible:
        ordered = sorted(
            feasible,
            key=lambda item: (
                float(item["recall"]),
                float(item["f1"]),
                float(item["precision"]),
                -float(item["false_positive_rate"]),
                -float(item["threshold"]),
            ),
            reverse=True,
        )
    else:
        ordered = sorted(
            candidates,
            key=lambda item: (
                -float(item["false_positive_rate"]),
                float(item["recall"]),
                float(item["f1"]),
                float(item["precision"]),
            ),
            reverse=True,
        )
    selected = dict(ordered[0])
    selected["max_false_positive_rate"] = max_fpr
    selected["meets_fpr_constraint"] = (
        float(selected["false_positive_rate_upper_95"]) <= max_fpr
    )
    return selected, [dict(item) for item in ordered[:20]]


def select_policy(
    y: np.ndarray,
    scores: np.ndarray,
    warn_max_fpr: float,
    block_max_fpr: float,
) -> dict[str, object]:
    warning, warning_candidates = select_threshold(y, scores, warn_max_fpr)
    blocking, blocking_candidates = select_threshold(
        y,
        scores,
        block_max_fpr,
        minimum_threshold=float(warning["threshold"]),
    )
    if float(blocking["threshold"]) < float(warning["threshold"]):
        raise RuntimeError("Blocking threshold cannot be below warning threshold.")
    return {
        "version": POLICY_VERSION,
        "warning": warning,
        "blocking": blocking,
        "top_warning_candidates": warning_candidates,
        "top_blocking_candidates": blocking_candidates,
        "selection_rule": (
            "For each operational FPR ceiling, require the one-sided 95% Wilson "
            "upper confidence bound for FPR to remain below the ceiling; then "
            "maximize recall, F1 and precision. The blocking threshold is "
            "constrained to be no lower than the warning threshold."
        ),
    }


def evaluate_policy(
    y: np.ndarray,
    risk_scores: np.ndarray,
    policy: dict[str, object],
    ml_probabilities: np.ndarray | None = None,
) -> dict[str, object]:
    warning = policy["warning"]
    blocking = policy["blocking"]
    if not isinstance(warning, dict) or not isinstance(blocking, dict):
        raise TypeError("Policy thresholds are malformed.")
    probability_scores = risk_scores if ml_probabilities is None else ml_probabilities
    return {
        "probability": probability_metrics(y, probability_scores),
        "final_score_ranking": {
            "roc_auc": safe_float(roc_auc_score(y, risk_scores)),
            "pr_auc": safe_float(average_precision_score(y, risk_scores)),
        },
        "warning": classification_metrics(y, risk_scores, float(warning["threshold"])),
        "blocking": classification_metrics(y, risk_scores, float(blocking["threshold"])),
    }


def coefficient_report(model: Pipeline) -> list[dict[str, object]]:
    logistic = model.named_steps["logistic"]
    coefficients = logistic.coef_[0]
    ranked = sorted(
        zip(FEATURE_NAMES, coefficients, strict=True),
        key=lambda item: abs(float(item[1])),
        reverse=True,
    )
    return [
        {
            "feature": name,
            "scaled_coefficient": safe_float(float(coefficient)),
            "direction": "risk" if coefficient > 0 else "legitimate",
        }
        for name, coefficient in ranked
        if abs(float(coefficient)) > 1e-10
    ]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def train(args: argparse.Namespace) -> None:
    if not 0 <= args.block_max_fpr <= args.warn_max_fpr < 1:
        raise ValueError(
            "FPR constraints must satisfy 0 <= block_max_fpr <= warn_max_fpr < 1."
        )

    dataset_path = args.dataset.resolve()
    data = load_rows(dataset_path)
    validate_dataset(data)
    x = data["x"]
    y = data["y"]
    groups = data["groups"]
    rule = data["rule"]
    if not all(isinstance(value, np.ndarray) for value in (x, y, groups, rule)):
        raise TypeError("Dataset arrays were not constructed correctly.")

    holdout_splits, holdout_fold_count = split_indices(
        y, groups, args.holdout_folds, args.seed + 9_000
    )
    development_index, holdout_index = holdout_splits[0]
    x_development = x[development_index]
    y_development = y[development_index]
    groups_development = groups[development_index]
    rule_development = rule[development_index] / 100.0

    print(
        f"Dataset: {len(y):,} rows | labels={dict(Counter(map(int, y)))} | "
        f"unique hostname groups={len(set(groups)):,}"
    )
    print(
        f"Independent grouped holdout: development={len(development_index):,}, "
        f"holdout={len(holdout_index):,}"
    )

    selected_c, development_oof, c_candidates, cv_fold_count = choose_regularization(
        x_development,
        y_development,
        groups_development,
        list(args.c_values),
        args.cv_folds,
        args.seed,
    )
    development_final_scores = blend_scores(rule_development, development_oof)
    policy = select_policy(
        y_development,
        development_final_scores,
        args.warn_max_fpr,
        args.block_max_fpr,
    )

    holdout_model = make_model(selected_c, args.seed)
    holdout_model.fit(x_development, y_development)
    holdout_scores = holdout_model.predict_proba(x[holdout_index])[:, 1]
    holdout_final_scores = blend_scores(rule[holdout_index] / 100.0, holdout_scores)
    holdout_evaluation = evaluate_policy(
        y[holdout_index], holdout_final_scores, policy, holdout_scores
    )

    # Preserve the hyperparameter chosen without access to the independent
    # holdout. Re-selecting C on the full dataset here would leak holdout
    # information into the final deployment policy.
    final_c = selected_c
    full_oof, final_cv_folds = oof_probabilities(
        x,
        y,
        groups,
        final_c,
        args.cv_folds,
        args.seed + 20_000,
    )
    full_final_scores = blend_scores(rule / 100.0, full_oof)
    final_model = make_model(final_c, args.seed)
    final_model.fit(x, y)

    now = datetime.now(timezone.utc).isoformat()
    warning = policy["warning"]
    blocking = policy["blocking"]
    if not isinstance(warning, dict) or not isinstance(blocking, dict):
        raise TypeError("Selected policy is malformed.")

    report = {
        "created_at": now,
        "model": {
            "version": MODEL_VERSION,
            "family": "L1-regularized logistic regression",
            "ml_score_formula": "MLScore = 100 * sigmoid(w dot x + b)",
            "risk_formula": RISK_FORMULA,
            "rule_weight": RULE_WEIGHT,
            "ml_weight": ML_WEIGHT,
            "selected_c_on_development": selected_c,
            "selected_c_for_final_model": final_c,
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "feature_names": FEATURE_NAMES,
        },
        "dataset": {
            "path": str(dataset_path.relative_to(BASE_DIR.parent)),
            "sha256": sha256(dataset_path),
            "row_count": len(y),
            "labels": dict(sorted(Counter(map(int, y)).items())),
            "sources": dict(sorted(Counter(data["sources"]).items())),
            "unique_hostname_groups": len(set(groups)),
        },
        "evaluation_design": {
            "group": "hostname",
            "holdout_strategy": "one untouched StratifiedGroupKFold partition",
            "holdout_folds": holdout_fold_count,
            "development_rows": len(development_index),
            "holdout_rows": len(holdout_index),
            "model_selection_cv": "StratifiedGroupKFold",
            "model_selection_folds": cv_fold_count,
            "final_model_selection_folds": final_cv_folds,
            "random_seed": args.seed,
        },
        "regularization_search": {
            "development_candidates": c_candidates,
            "selection_dataset": "development partition only",
        },
        "probability_quality": {
            "development_out_of_fold": probability_metrics(
                y_development, development_oof
            ),
            "independent_holdout": probability_metrics(
                y[holdout_index], holdout_scores
            ),
            "interpretation": (
                "Logistic regression directly estimates sigmoid probabilities; "
                "lower Brier score and log loss indicate better probability quality."
            ),
        },
        "fixed_score_blend": {
            "formula": RISK_FORMULA,
            "rule_weight": RULE_WEIGHT,
            "ml_weight": ML_WEIGHT,
            "development_out_of_fold": {
                "roc_auc": safe_float(
                    roc_auc_score(y_development, development_final_scores)
                ),
                "pr_auc": safe_float(
                    average_precision_score(y_development, development_final_scores)
                ),
            },
            "threshold_selection_input": "blended development out-of-fold FinalScore",
        },
        "policy": policy,
        "independent_holdout": holdout_evaluation,
        "final_model_oof_probability": probability_metrics(y, full_oof),
        "final_model_oof_risk_score": {
            "roc_auc": safe_float(roc_auc_score(y, full_final_scores)),
            "pr_auc": safe_float(average_precision_score(y, full_final_scores)),
        },
        "coefficients": coefficient_report(final_model),
        "rule_engine": {
            "role": (
                "Local/offline evidence and weighted input. RuleScore contributes "
                "40 percent to FinalScore when the ML model is available."
            ),
            "audit_only_summary": {
                str(label): {
                    "mean": safe_float(float(np.mean(data["rule"][y == label]))),
                    "median": safe_float(float(np.median(data["rule"][y == label]))),
                }
                for label in (0, 1)
            },
        },
        "limitations": [
            "The independent holdout is group-disjoint but not time-disjoint because the current dataset does not contain reliable first-seen timestamps.",
            "The current legitimate holdout is too small to make a statistically stable production claim at a 0.01% false-positive rate.",
            "Tranco membership is a legitimate-label proxy and does not guarantee that every listed website is safe at every point in time.",
            "DOM, form, email-provider metadata, and live reputation are separate evidence layers and are not represented in this URL-only model.",
            "Feed distributions and phishing campaigns change over time; external source-split testing, time-split testing, retraining, and drift monitoring remain required.",
        ],
    }

    model_bundle = {
        "model": final_model,
        "model_version": MODEL_VERSION,
        "policy_version": POLICY_VERSION,
        "feature_names": FEATURE_NAMES,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "risk_formula": RISK_FORMULA,
        "rule_weight": RULE_WEIGHT,
        "ml_weight": ML_WEIGHT,
        "policy": {
            "warning_threshold": float(warning["threshold"]) * 100.0,
            "blocking_threshold": float(blocking["threshold"]) * 100.0,
            "warning_max_fpr": args.warn_max_fpr,
            "blocking_max_fpr": args.block_max_fpr,
        },
        "probability_method": "intrinsic_logistic_sigmoid",
        "cv_strategy": "StratifiedGroupKFold(hostname) with untouched grouped holdout",
        "metrics": {
            "development_oof": {
                "warning": {
                    key: warning[key]
                    for key in (
                        "precision",
                        "recall",
                        "f1",
                        "roc_auc",
                        "pr_auc",
                        "false_positive_rate",
                        "false_positive_rate_upper_95",
                    )
                },
                "blocking": {
                    key: blocking[key]
                    for key in (
                        "precision",
                        "recall",
                        "f1",
                        "roc_auc",
                        "pr_auc",
                        "false_positive_rate",
                        "false_positive_rate_upper_95",
                    )
                },
            },
            "independent_holdout": holdout_evaluation,
        },
        "trained_at": now,
        "dataset_sha256": report["dataset"]["sha256"],
        "dataset_row_count": len(y),
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    report_temporary = REPORT_PATH.with_suffix(REPORT_PATH.suffix + ".tmp")
    report_temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    report_temporary.replace(REPORT_PATH)

    model_temporary = MODEL_PATH.with_suffix(MODEL_PATH.suffix + ".tmp")
    joblib.dump(model_bundle, model_temporary, compress=MODEL_COMPRESSION)
    model_temporary.replace(MODEL_PATH)

    print("Selected warning policy:")
    print(json.dumps(warning, ensure_ascii=False, indent=2))
    print("Selected blocking policy:")
    print(json.dumps(blocking, ensure_ascii=False, indent=2))
    print("Independent holdout:")
    print(json.dumps(holdout_evaluation, ensure_ascii=False, indent=2))
    print(f"Saved model to {MODEL_PATH}")
    print(f"Saved evaluation report to {REPORT_PATH}")


if __name__ == "__main__":
    train(parse_args())
