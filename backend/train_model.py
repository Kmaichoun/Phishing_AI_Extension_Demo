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
from sklearn.base import clone
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    brier_score_loss,
    confusion_matrix,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedGroupKFold

from build_dataset import calculate_rule_scores
from feature_extractor import FEATURE_NAMES, feature_vector

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
GENERATED_DATASET_PATH = DATA_DIR / "training_urls.csv"
SEED_DATASET_PATH = DATA_DIR / "seed_urls.csv"
MODEL_PATH = BASE_DIR / "model.pkl"
REPORT_PATH = DATA_DIR / "risk_model_evaluation.json"
# LZMA keeps the calibrated Random Forest bundle materially smaller in Git while
# remaining transparent to joblib.load() in the API and test suite.
MODEL_COMPRESSION: tuple[str, int] = ("lzma", 3)


def parse_args() -> argparse.Namespace:
    default_dataset = (
        GENERATED_DATASET_PATH if GENERATED_DATASET_PATH.exists() else SEED_DATASET_PATH
    )
    parser = argparse.ArgumentParser(
        description="Train and calibrate the Phish Radar Random Forest risk model."
    )
    parser.add_argument("--dataset", type=Path, default=default_dataset)
    parser.add_argument("--outer-folds", type=int, default=5)
    parser.add_argument("--calibration-folds", type=int, default=3)
    parser.add_argument("--trees", type=int, default=250)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-fpr", type=float, default=0.05)
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
        "rule": np.asarray(rule_scores, dtype=np.float64) / 100.0,
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
        raise ValueError("Dataset must contain both legitimate (0) and phishing (1) labels.")
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
        raise ValueError("Not enough hostname groups for stratified group cross-validation.")
    splitter = StratifiedGroupKFold(n_splits=folds, shuffle=True, random_state=seed)
    dummy = np.zeros((len(y), 1), dtype=np.float64)
    return list(splitter.split(dummy, y, groups)), folds


def make_random_forest(seed: int, trees: int) -> RandomForestClassifier:
    return RandomForestClassifier(
        n_estimators=trees,
        random_state=seed,
        class_weight="balanced_subsample",
        min_samples_leaf=2,
        max_features="sqrt",
        n_jobs=-1,
    )


def safe_float(value: float) -> float | None:
    return None if not math.isfinite(value) else round(float(value), 6)


def classification_metrics(
    y_true: np.ndarray,
    scores: np.ndarray,
    threshold: float,
) -> dict[str, float | int | None]:
    predicted = (scores >= threshold).astype(np.int64)
    tn, fp, fn, tp = confusion_matrix(y_true, predicted, labels=[0, 1]).ravel()
    fpr = fp / (fp + tn) if fp + tn else 0.0
    return {
        "threshold": round(float(threshold), 4),
        "precision": safe_float(precision_score(y_true, predicted, zero_division=0)),
        "recall": safe_float(recall_score(y_true, predicted, zero_division=0)),
        "f1": safe_float(f1_score(y_true, predicted, zero_division=0)),
        "roc_auc": safe_float(roc_auc_score(y_true, scores)),
        "false_positive_rate": safe_float(fpr),
        "true_negative": int(tn),
        "false_positive": int(fp),
        "false_negative": int(fn),
        "true_positive": int(tp),
    }


def candidate_rank(candidate: dict[str, object], max_fpr: float) -> tuple[object, ...]:
    fpr = float(candidate["false_positive_rate"])
    feasible = fpr <= max_fpr
    if feasible:
        return (
            1,
            float(candidate["recall"]),
            float(candidate["f1"]),
            float(candidate["precision"]),
            float(candidate["roc_auc"]),
            -fpr,
            -abs(float(candidate["threshold"]) - 0.5),
        )
    return (
        0,
        -fpr,
        float(candidate["f1"]),
        float(candidate["recall"]),
        float(candidate["precision"]),
        float(candidate["roc_auc"]),
        -abs(float(candidate["threshold"]) - 0.5),
    )


def search_policy(
    y: np.ndarray,
    rule_scores: np.ndarray,
    ml_scores: np.ndarray,
    max_fpr: float,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    candidates: list[dict[str, object]] = []
    for alpha in np.linspace(0.0, 1.0, 21):
        combined = alpha * rule_scores + (1.0 - alpha) * ml_scores
        auc = safe_float(roc_auc_score(y, combined))
        for threshold in np.linspace(0.05, 0.95, 91):
            metrics = classification_metrics(y, combined, float(threshold))
            metrics["alpha"] = round(float(alpha), 2)
            metrics["roc_auc"] = auc
            candidates.append(metrics)

    ordered = sorted(candidates, key=lambda item: candidate_rank(item, max_fpr), reverse=True)
    best = dict(ordered[0])
    best["meets_fpr_constraint"] = float(best["false_positive_rate"]) <= max_fpr

    per_alpha: list[dict[str, object]] = []
    for alpha in np.linspace(0.0, 1.0, 21):
        alpha_value = round(float(alpha), 2)
        alpha_candidates = [item for item in candidates if item["alpha"] == alpha_value]
        per_alpha.append(
            dict(max(alpha_candidates, key=lambda item: candidate_rank(item, max_fpr)))
        )
    return best, per_alpha, [dict(item) for item in ordered[:20]]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def train(args: argparse.Namespace) -> None:
    dataset_path = args.dataset.resolve()
    data = load_rows(dataset_path)
    validate_dataset(data)
    x = data["x"]
    y = data["y"]
    rule_scores = data["rule"]
    groups = data["groups"]
    if not all(isinstance(value, np.ndarray) for value in (x, y, rule_scores, groups)):
        raise TypeError("Dataset arrays were not constructed correctly.")

    outer_splits, outer_fold_count = split_indices(
        y, groups, args.outer_folds, args.seed
    )
    calibrated_oof = np.zeros(len(y), dtype=np.float64)
    raw_oof = np.zeros(len(y), dtype=np.float64)
    fold_assignments = np.full(len(y), -1, dtype=np.int64)
    calibration_fold_counts: list[int] = []

    print(
        f"Dataset: {len(y):,} rows | labels={dict(Counter(map(int, y)))} | "
        f"unique hostname groups={len(set(groups)):,}"
    )
    print(
        f"Outer CV: StratifiedGroupKFold({outer_fold_count}) | "
        "calibration: sigmoid"
    )

    for fold, (train_index, test_index) in enumerate(outer_splits, start=1):
        inner_splits, calibration_fold_count = split_indices(
            y[train_index],
            groups[train_index],
            args.calibration_folds,
            args.seed + fold,
        )
        calibration_fold_counts.append(calibration_fold_count)
        base = make_random_forest(args.seed + fold, args.trees)
        calibrated = CalibratedClassifierCV(
            estimator=base,
            method="sigmoid",
            cv=inner_splits,
            ensemble=True,
            n_jobs=-1,
        )
        calibrated.fit(x[train_index], y[train_index])
        calibrated_oof[test_index] = calibrated.predict_proba(x[test_index])[:, 1]

        raw = clone(base)
        raw.fit(x[train_index], y[train_index])
        raw_oof[test_index] = raw.predict_proba(x[test_index])[:, 1]
        fold_assignments[test_index] = fold
        print(
            f"Fold {fold}/{outer_fold_count}: train={len(train_index):,}, "
            f"test={len(test_index):,}, calibration_folds={calibration_fold_count}"
        )

    if np.any(fold_assignments < 0):
        raise RuntimeError("Some rows did not receive an out-of-fold prediction.")

    best, per_alpha, top_candidates = search_policy(
        y, rule_scores, calibrated_oof, args.max_fpr
    )
    alpha = float(best["alpha"])
    threshold = float(best["threshold"])
    final_oof = alpha * rule_scores + (1.0 - alpha) * calibrated_oof

    fold_metrics: list[dict[str, object]] = []
    for fold in range(1, outer_fold_count + 1):
        mask = fold_assignments == fold
        metrics = classification_metrics(y[mask], final_oof[mask], threshold)
        metrics["fold"] = fold
        metrics["row_count"] = int(np.sum(mask))
        fold_metrics.append(metrics)

    final_inner_splits, final_calibration_folds = split_indices(
        y, groups, max(args.calibration_folds, outer_fold_count), args.seed + 10_000
    )
    final_model = CalibratedClassifierCV(
        estimator=make_random_forest(args.seed, args.trees),
        method="sigmoid",
        cv=final_inner_splits,
        ensemble=True,
        n_jobs=-1,
    )
    print(f"Training final calibrated model on all {len(y):,} rows...")
    final_model.fit(x, y)

    calibration_metrics = {
        "raw_random_forest": {
            "brier_score": safe_float(brier_score_loss(y, raw_oof)),
            "log_loss": safe_float(log_loss(y, raw_oof, labels=[0, 1])),
            "roc_auc": safe_float(roc_auc_score(y, raw_oof)),
        },
        "sigmoid_calibrated_random_forest": {
            "brier_score": safe_float(brier_score_loss(y, calibrated_oof)),
            "log_loss": safe_float(log_loss(y, calibrated_oof, labels=[0, 1])),
            "roc_auc": safe_float(roc_auc_score(y, calibrated_oof)),
        },
        "interpretation": "Lower Brier score and log loss indicate better probability calibration.",
    }
    now = datetime.now(timezone.utc).isoformat()
    report = {
        "created_at": now,
        "dataset": {
            "path": str(dataset_path.relative_to(BASE_DIR.parent)),
            "sha256": sha256(dataset_path),
            "row_count": len(y),
            "labels": dict(sorted(Counter(map(int, y)).items())),
            "sources": dict(sorted(Counter(data["sources"]).items())),
            "unique_hostname_groups": len(set(groups)),
        },
        "cross_validation": {
            "strategy": "StratifiedGroupKFold",
            "group": "hostname",
            "outer_folds": outer_fold_count,
            "calibration_method": "sigmoid",
            "calibration_folds_per_outer_fold": calibration_fold_counts,
            "final_model_calibration_folds": final_calibration_folds,
            "random_seed": args.seed,
        },
        "random_forest": {
            "n_estimators": args.trees,
            "class_weight": "balanced_subsample",
            "min_samples_leaf": 2,
            "max_features": "sqrt",
        },
        "calibration_metrics": calibration_metrics,
        "policy_search": {
            "formula": "FinalScore = alpha * RuleScore + (1 - alpha) * MLScore",
            "alpha_values": [round(float(value), 2) for value in np.linspace(0, 1, 21)],
            "threshold_values": [round(float(value), 2) for value in np.linspace(0.05, 0.95, 91)],
            "max_false_positive_rate": args.max_fpr,
            "selection_rule": (
                "Among candidates with FPR <= max_false_positive_rate, maximize recall, "
                "then F1, precision, ROC-AUC, and finally prefer lower FPR. If none qualify, "
                "minimize FPR before the remaining metrics."
            ),
            "selected": best,
            "best_candidate_per_alpha": per_alpha,
            "top_candidates": top_candidates,
        },
        "selected_policy_fold_metrics": fold_metrics,
        "limitations": [
            "The selected policy is estimated from cross-validated out-of-fold predictions; an independent time-split holdout is still recommended before production deployment.",
            "Tranco membership is used as a legitimate-label proxy and does not guarantee that every listed website is safe at every point in time.",
            "Feed distributions and active phishing campaigns change over time, so retraining and drift monitoring are required.",
        ],
    }

    model_bundle = {
        "model": final_model,
        "feature_names": FEATURE_NAMES,
        "alpha": alpha,
        "decision_threshold": threshold * 100.0,
        "calibration": "sigmoid",
        "cv_strategy": "StratifiedGroupKFold(hostname)",
        "metrics": {
            key: best[key]
            for key in ("precision", "recall", "f1", "roc_auc", "false_positive_rate")
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

    print("Selected policy:")
    print(json.dumps(best, ensure_ascii=False, indent=2))
    print("Calibration metrics:")
    print(json.dumps(calibration_metrics, ensure_ascii=False, indent=2))
    print(f"Saved model to {MODEL_PATH}")
    print(f"Saved evaluation report to {REPORT_PATH}")


if __name__ == "__main__":
    train(parse_args())
