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
from sklearn.ensemble import RandomForestClassifier
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

from build_dataset import calculate_rule_scores
from feature_extractor import (
    FEATURE_NAMES,
    FEATURE_SCHEMA_VERSION,
    extract_features,
    feature_vector,
)
from fuzzy_scoring import FUZZY_SCHEMA_VERSION, fuzzy_score
from risk_policy import (
    CONSENSUS_GUARDRAIL_VERSION,
    apply_consensus_guardrail,
    consensus_guardrail_config,
)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
GENERATED_DATASET_PATH = DATA_DIR / "training_urls.csv"
SEED_DATASET_PATH = DATA_DIR / "seed_urls.csv"
MODEL_PATH = BASE_DIR / "model.pkl"
REPORT_PATH = DATA_DIR / "risk_model_evaluation.json"
MODEL_COMPRESSION: tuple[str, int] = ("lzma", 3)
MODEL_VERSION = "url-risk-random-forest-1.3"
POLICY_VERSION = "fuzzy-calibrated-rf-consensus-fpr-1.3"
FUSION_VERSION = "logistic-stacking-fusion-1.0"
CALIBRATION_VERSION = "platt-group-oof-1.0"
RISK_FORMULA = (
    "FinalScore = 100 * ConsensusGuardrail("
    "LearnedFusion(FuzzyScore, RandomForestScore), FuzzyScore, RandomForestScore)"
)


def parse_args() -> argparse.Namespace:
    default_dataset = (
        GENERATED_DATASET_PATH if GENERATED_DATASET_PATH.exists() else SEED_DATASET_PATH
    )
    parser = argparse.ArgumentParser(
        description=(
            "Train a Random Forest URL model with FuzzyScore learned fusion and select "
            "thresholds under explicit false-positive-rate constraints."
        )
    )
    parser.add_argument("--dataset", type=Path, default=default_dataset)
    parser.add_argument("--output-dir", type=Path, required=True,
                        help="New experiment directory; this legacy trainer never writes production model.pkl.")
    parser.add_argument("--cv-folds", type=int, default=5)
    parser.add_argument("--holdout-folds", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--warn-max-fpr", type=float, default=0.01)
    parser.add_argument("--block-max-fpr", type=float, default=0.001)
    parser.add_argument("--trees", type=int, default=240)
    parser.add_argument("--max-depth", type=int, default=18)
    parser.add_argument("--min-samples-leaf", type=int, default=2)
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


def make_model(
    seed: int,
    trees: int,
    max_depth: int | None,
    min_samples_leaf: int,
) -> RandomForestClassifier:
    return RandomForestClassifier(
        n_estimators=trees,
        max_depth=max_depth,
        min_samples_leaf=min_samples_leaf,
        max_features="sqrt",
        class_weight="balanced_subsample",
        n_jobs=-1,
        random_state=seed,
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


def url_shape_report(urls: np.ndarray, labels: np.ndarray) -> dict[str, object]:
    report: dict[str, object] = {}
    for label in (0, 1):
        selected = urls[labels == label]
        features = [extract_features(str(url)) for url in selected]
        count = len(features)
        deep_links = sum(item["path_depth"] > 0 for item in features)
        queries = sum(item["query_length"] > 0 for item in features)
        subdomains = sum(item["subdomain_count"] > 0 for item in features)
        report[str(label)] = {
            "count": count,
            "deep_link_count": deep_links,
            "deep_link_ratio": safe_float(deep_links / count if count else 0.0),
            "query_count": queries,
            "query_ratio": safe_float(queries / count if count else 0.0),
            "subdomain_count": subdomains,
            "subdomain_ratio": safe_float(subdomains / count if count else 0.0),
        }
    return report


def legitimate_segment_evaluation(
    urls: np.ndarray,
    labels: np.ndarray,
    scores: np.ndarray,
    policy: dict[str, object],
) -> dict[str, object]:
    warning = policy["warning"]
    blocking = policy["blocking"]
    if not isinstance(warning, dict) or not isinstance(blocking, dict):
        raise TypeError("Policy thresholds are malformed.")
    warning_threshold = float(warning["threshold"])
    blocking_threshold = float(blocking["threshold"])
    features = [extract_features(str(url)) for url in urls]
    segment_masks = {
        "all_legitimate": np.asarray(labels == 0, dtype=bool),
        "root_url": np.asarray(
            [label == 0 and item["path_depth"] == 0 for label, item in zip(labels, features)],
            dtype=bool,
        ),
        "deep_link": np.asarray(
            [label == 0 and item["path_depth"] > 0 for label, item in zip(labels, features)],
            dtype=bool,
        ),
        "query_url": np.asarray(
            [label == 0 and item["query_length"] > 0 for label, item in zip(labels, features)],
            dtype=bool,
        ),
        "subdomain_url": np.asarray(
            [label == 0 and item["subdomain_count"] > 0 for label, item in zip(labels, features)],
            dtype=bool,
        ),
    }
    output: dict[str, object] = {}
    for name, mask in segment_masks.items():
        selected_scores = scores[mask]
        count = len(selected_scores)
        warning_fp = int(np.sum(selected_scores >= warning_threshold))
        blocking_fp = int(np.sum(selected_scores >= blocking_threshold))
        output[name] = {
            "count": count,
            "warning_false_positive": warning_fp,
            "warning_false_positive_rate": safe_float(
                warning_fp / count if count else 0.0
            ),
            "blocking_false_positive": blocking_fp,
            "blocking_false_positive_rate": safe_float(
                blocking_fp / count if count else 0.0
            ),
        }
    return output


def fuzzy_scores(rule_scores: np.ndarray) -> np.ndarray:
    return np.asarray(
        [fuzzy_score(float(value)) / 100.0 for value in rule_scores],
        dtype=np.float64,
    )


def fusion_inputs(
    fuzzy_probabilities: np.ndarray,
    forest_probabilities: np.ndarray,
) -> np.ndarray:
    return np.column_stack(
        [
            np.clip(fuzzy_probabilities, 0.0, 1.0),
            np.clip(forest_probabilities, 0.0, 1.0),
        ]
    )


def make_fusion_model(seed: int) -> LogisticRegression:
    return LogisticRegression(
        penalty="l2",
        solver="liblinear",
        class_weight="balanced",
        max_iter=2_000,
        random_state=seed,
    )


def fit_probability_calibrator(
    raw_probabilities: np.ndarray,
    labels: np.ndarray,
    seed: int,
) -> LogisticRegression:
    """Fit Platt scaling on predictions that were generated out-of-fold."""
    calibrator = LogisticRegression(
        penalty="l2",
        solver="liblinear",
        max_iter=2_000,
        random_state=seed,
    )
    calibrator.fit(raw_probabilities.reshape(-1, 1), labels)
    return calibrator


def calibrated_probabilities(
    calibrator: LogisticRegression,
    raw_probabilities: np.ndarray,
) -> np.ndarray:
    return calibrator.predict_proba(raw_probabilities.reshape(-1, 1))[:, 1]


def cross_calibrated_probabilities(
    raw_oof_probabilities: np.ndarray,
    labels: np.ndarray,
    groups: np.ndarray,
    folds: int,
    seed: int,
) -> tuple[np.ndarray, int]:
    """Calibrate without allowing a row's label into its own calibrator fit."""
    splits, fold_count = split_indices(labels, groups, folds, seed)
    calibrated = np.zeros(len(labels), dtype=np.float64)
    assigned = np.zeros(len(labels), dtype=bool)
    for fold, (train_index, test_index) in enumerate(splits, start=1):
        calibrator = fit_probability_calibrator(
            raw_oof_probabilities[train_index],
            labels[train_index],
            seed + fold,
        )
        calibrated[test_index] = calibrated_probabilities(
            calibrator,
            raw_oof_probabilities[test_index],
        )
        assigned[test_index] = True
    if not np.all(assigned):
        raise RuntimeError("Every row must receive one cross-calibrated probability.")
    return calibrated, fold_count


def fit_fusion_model(
    fuzzy_probabilities: np.ndarray,
    forest_probabilities: np.ndarray,
    labels: np.ndarray,
    seed: int,
) -> LogisticRegression:
    model = make_fusion_model(seed)
    model.fit(fusion_inputs(fuzzy_probabilities, forest_probabilities), labels)
    return model


def learned_fusion_scores(
    model: LogisticRegression,
    fuzzy_probabilities: np.ndarray,
    forest_probabilities: np.ndarray,
) -> np.ndarray:
    return model.predict_proba(
        fusion_inputs(fuzzy_probabilities, forest_probabilities)
    )[:, 1]


def operational_risk_scores(
    fuzzy_probabilities: np.ndarray,
    forest_probabilities: np.ndarray,
    fusion_probabilities: np.ndarray,
) -> tuple[np.ndarray, dict[str, int]]:
    scores = np.zeros(len(fusion_probabilities), dtype=np.float64)
    triggers = {"warning_consensus": 0, "block_consensus": 0}
    for index, (fuzzy, forest, fusion) in enumerate(
        zip(
            fuzzy_probabilities,
            forest_probabilities,
            fusion_probabilities,
            strict=True,
        )
    ):
        score, trigger = apply_consensus_guardrail(fuzzy, forest, fusion)
        scores[index] = score
        if trigger:
            triggers[trigger] += 1
    return scores, triggers


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
    folds: int,
    seed: int,
    trees: int,
    max_depth: int | None,
    min_samples_leaf: int,
) -> tuple[np.ndarray, int]:
    splits, fold_count = split_indices(y, groups, folds, seed)
    scores = np.zeros(len(y), dtype=np.float64)
    assigned = np.zeros(len(y), dtype=bool)
    for fold, (train_index, test_index) in enumerate(splits, start=1):
        model = make_model(
            seed + fold,
            trees=trees,
            max_depth=max_depth,
            min_samples_leaf=min_samples_leaf,
        )
        model.fit(x[train_index], y[train_index])
        scores[test_index] = model.predict_proba(x[test_index])[:, 1]
        assigned[test_index] = True
    if not np.all(assigned):
        raise RuntimeError("Every development row must receive one out-of-fold probability.")
    return scores, fold_count

def select_threshold(
    y: np.ndarray,
    scores: np.ndarray,
    max_fpr: float,
    minimum_threshold: float = 0.01,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    candidates: list[dict[str, object]] = []
    negative_scores = scores[y == 0]
    zero_false_positive_cutoff = (
        np.nextafter(float(np.max(negative_scores)), 1.0)
        if len(negative_scores)
        else 1.0
    )
    threshold_grid = np.unique(
        np.concatenate(
            [
                np.linspace(max(0.01, minimum_threshold), 0.99, 99),
                np.asarray([zero_false_positive_cutoff, 1.0]),
            ]
        )
    )
    threshold_grid = threshold_grid[
        (threshold_grid >= minimum_threshold) & (threshold_grid <= 1.0)
    ]
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


def feature_importance_report(
    model: RandomForestClassifier,
) -> list[dict[str, object]]:
    ranked = sorted(
        zip(FEATURE_NAMES, model.feature_importances_, strict=True),
        key=lambda item: float(item[1]),
        reverse=True,
    )
    return [
        {
            "feature": name,
            "importance": safe_float(float(importance)),
        }
        for name, importance in ranked
    ]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def train(args: argparse.Namespace) -> None:
    output = args.output_dir.resolve()
    if output == BASE_DIR.resolve():
        raise ValueError('Training cannot overwrite the production directory')
    output.mkdir(parents=True, exist_ok=False)
    model_path = output / 'candidate.pkl'
    report_path = output / 'evaluation.json'
    if not 0 <= args.block_max_fpr <= args.warn_max_fpr < 1:
        raise ValueError(
            "FPR constraints must satisfy 0 <= block_max_fpr <= warn_max_fpr < 1."
        )
    if args.trees < 20 or args.min_samples_leaf < 1:
        raise ValueError("Random Forest requires at least 20 trees and a positive leaf size.")

    dataset_path = args.dataset.resolve()
    data = load_rows(dataset_path)
    validate_dataset(data)
    x = data["x"]
    y = data["y"]
    groups = data["groups"]
    rule = data["rule"]
    urls = np.asarray(data["urls"], dtype=object)
    if not all(isinstance(value, np.ndarray) for value in (x, y, groups, rule)):
        raise TypeError("Dataset arrays were not constructed correctly.")

    holdout_splits, holdout_fold_count = split_indices(
        y, groups, args.holdout_folds, args.seed + 9_000
    )
    development_index, holdout_index = holdout_splits[0]
    x_development = x[development_index]
    y_development = y[development_index]
    groups_development = groups[development_index]
    fuzzy_all = fuzzy_scores(rule)
    fuzzy_development = fuzzy_all[development_index]

    print(
        f"Dataset: {len(y):,} rows | labels={dict(Counter(map(int, y)))} | "
        f"unique hostname groups={len(set(groups)):,}"
    )
    print(
        f"Independent grouped holdout: development={len(development_index):,}, "
        f"holdout={len(holdout_index):,}"
    )

    development_raw_oof, cv_fold_count = oof_probabilities(
        x_development,
        y_development,
        groups_development,
        args.cv_folds,
        args.seed,
        args.trees,
        args.max_depth,
        args.min_samples_leaf,
    )
    development_oof, calibration_fold_count = cross_calibrated_probabilities(
        development_raw_oof,
        y_development,
        groups_development,
        args.cv_folds,
        args.seed + 3_000,
    )
    development_calibrator = fit_probability_calibrator(
        development_raw_oof,
        y_development,
        args.seed + 4_000,
    )
    development_fusion_model = fit_fusion_model(
        fuzzy_development,
        development_oof,
        y_development,
        args.seed + 5_000,
    )
    development_fusion_scores = learned_fusion_scores(
        development_fusion_model,
        fuzzy_development,
        development_oof,
    )
    development_final_scores, development_consensus_triggers = operational_risk_scores(
        fuzzy_development,
        development_oof,
        development_fusion_scores,
    )
    policy = select_policy(
        y_development,
        development_final_scores,
        args.warn_max_fpr,
        args.block_max_fpr,
    )

    holdout_model = make_model(
        args.seed,
        trees=args.trees,
        max_depth=args.max_depth,
        min_samples_leaf=args.min_samples_leaf,
    )
    holdout_model.fit(x_development, y_development)
    holdout_raw_scores = holdout_model.predict_proba(x[holdout_index])[:, 1]
    holdout_scores = calibrated_probabilities(
        development_calibrator,
        holdout_raw_scores,
    )
    holdout_fusion_scores = learned_fusion_scores(
        development_fusion_model,
        fuzzy_all[holdout_index],
        holdout_scores,
    )
    holdout_final_scores, holdout_consensus_triggers = operational_risk_scores(
        fuzzy_all[holdout_index],
        holdout_scores,
        holdout_fusion_scores,
    )
    holdout_evaluation = evaluate_policy(
        y[holdout_index], holdout_final_scores, policy
    )
    holdout_legitimate_segments = legitimate_segment_evaluation(
        urls[holdout_index],
        y[holdout_index],
        holdout_final_scores,
        policy,
    )

    full_raw_oof, final_cv_folds = oof_probabilities(
        x,
        y,
        groups,
        args.cv_folds,
        args.seed + 20_000,
        args.trees,
        args.max_depth,
        args.min_samples_leaf,
    )
    full_oof, final_calibration_folds = cross_calibrated_probabilities(
        full_raw_oof,
        y,
        groups,
        args.cv_folds,
        args.seed + 23_000,
    )
    final_calibrator = fit_probability_calibrator(
        full_raw_oof,
        y,
        args.seed + 24_000,
    )
    final_fusion_model = fit_fusion_model(
        fuzzy_all,
        full_oof,
        y,
        args.seed + 25_000,
    )
    full_fusion_scores = learned_fusion_scores(
        final_fusion_model,
        fuzzy_all,
        full_oof,
    )
    full_final_scores, full_consensus_triggers = operational_risk_scores(
        fuzzy_all,
        full_oof,
        full_fusion_scores,
    )
    final_model = make_model(
        args.seed,
        trees=args.trees,
        max_depth=args.max_depth,
        min_samples_leaf=args.min_samples_leaf,
    )
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
            "family": "Random Forest classifier",
            "ml_score_formula": (
                "RandomForestScore = 100 * PlattCalibration(mean(tree phishing votes))"
            ),
            "risk_formula": RISK_FORMULA,
            "fusion_version": FUSION_VERSION,
            "consensus_guardrail_version": CONSENSUS_GUARDRAIL_VERSION,
            "fuzzy_schema_version": FUZZY_SCHEMA_VERSION,
            "hyperparameters": {
                "n_estimators": args.trees,
                "max_depth": args.max_depth,
                "min_samples_leaf": args.min_samples_leaf,
                "max_features": "sqrt",
                "class_weight": "balanced_subsample",
            },
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
            "url_shapes_by_label": url_shape_report(urls, y),
        },
        "evaluation_design": {
            "group": "hostname",
            "holdout_strategy": "one untouched StratifiedGroupKFold partition",
            "holdout_folds": holdout_fold_count,
            "development_rows": len(development_index),
            "holdout_rows": len(holdout_index),
            "base_model_oof_cv": "StratifiedGroupKFold",
            "base_model_oof_folds": cv_fold_count,
            "final_base_model_oof_folds": final_cv_folds,
            "calibration": "group-disjoint cross-fitted Platt scaling",
            "calibration_version": CALIBRATION_VERSION,
            "calibration_oof_folds": calibration_fold_count,
            "final_calibration_oof_folds": final_calibration_folds,
            "fusion_training_input": "out-of-fold RandomForestScore plus deterministic FuzzyScore",
            "random_seed": args.seed,
        },
        "probability_quality": {
            "random_forest_raw_development_out_of_fold": probability_metrics(
                y_development, development_raw_oof
            ),
            "random_forest_development_out_of_fold": probability_metrics(
                y_development, development_oof
            ),
            "random_forest_raw_independent_holdout": probability_metrics(
                y[holdout_index], holdout_raw_scores
            ),
            "random_forest_independent_holdout": probability_metrics(
                y[holdout_index], holdout_scores
            ),
            "fusion_development_out_of_fold": probability_metrics(
                y_development, development_fusion_scores
            ),
            "fusion_independent_holdout": probability_metrics(
                y[holdout_index], holdout_fusion_scores
            ),
            "operational_development_out_of_fold": probability_metrics(
                y_development, development_final_scores
            ),
            "operational_independent_holdout": probability_metrics(
                y[holdout_index], holdout_final_scores
            ),
            "interpretation": (
                "Random Forest vote fractions are calibrated with group-disjoint, "
                "cross-fitted Platt scaling. A separate logistic meta-model learns the "
                "final probability from FuzzyScore and calibrated out-of-fold scores."
            ),
        },
        "probability_calibration": {
            "version": CALIBRATION_VERSION,
            "method": "Platt scaling (logistic regression)",
            "training_input": "group-disjoint Random Forest out-of-fold probabilities",
            "coefficient": safe_float(float(final_calibrator.coef_[0][0])),
            "intercept": safe_float(float(final_calibrator.intercept_[0])),
        },
        "learned_fusion": {
            "formula": "LearnedFusion(FuzzyScore, RandomForestScore)",
            "version": FUSION_VERSION,
            "input_order": ["fuzzy_score", "random_forest_score"],
            "coefficients": [
                safe_float(float(value))
                for value in final_fusion_model.coef_[0]
            ],
            "intercept": safe_float(float(final_fusion_model.intercept_[0])),
            "development_out_of_fold": {
                "roc_auc": safe_float(
                    roc_auc_score(y_development, development_final_scores)
                ),
                "pr_auc": safe_float(
                    average_precision_score(y_development, development_final_scores)
                ),
            },
            "threshold_selection_input": (
                "operational score after learned fusion and consensus guardrail"
            ),
        },
        "consensus_guardrail": {
            **consensus_guardrail_config(),
            "development_trigger_counts": development_consensus_triggers,
            "independent_holdout_trigger_counts": holdout_consensus_triggers,
            "full_oof_trigger_counts": full_consensus_triggers,
            "role": (
                "Raise the operational score only when strong fuzzy-rule and "
                "calibrated-ML evidence agree; threshold selection and evaluation "
                "use the guarded score."
            ),
        },
        "policy": policy,
        "independent_holdout": holdout_evaluation,
        "independent_holdout_legitimate_segments": holdout_legitimate_segments,
        "final_model_raw_oof_probability": probability_metrics(y, full_raw_oof),
        "final_model_oof_probability": probability_metrics(y, full_oof),
        "final_model_oof_risk_score": {
            "roc_auc": safe_float(roc_auc_score(y, full_final_scores)),
            "pr_auc": safe_float(average_precision_score(y, full_final_scores)),
        },
        "feature_importances": feature_importance_report(final_model),
        "rule_engine": {
            "role": (
                "RuleScore is converted to an explainable FuzzyScore. Learned fusion "
                "determines how FuzzyScore and RandomForestScore combine; no fixed weight is used."
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
            "Synthetic benign URL shapes remove source-format shortcuts but are not a substitute for a large externally collected benign deep-link test set.",
            "DOM, form, email-provider metadata, and live reputation are separate evidence layers and are not represented in this URL-only model.",
            "Feed distributions and phishing campaigns change over time; external source-split testing, time-split testing, retraining, and drift monitoring remain required.",
        ],
    }

    model_bundle = {
        "model": final_model,
        "probability_calibrator": final_calibrator,
        "fusion_model": final_fusion_model,
        "model_version": MODEL_VERSION,
        "policy_version": POLICY_VERSION,
        "model_family": "random_forest",
        "fusion_version": FUSION_VERSION,
        "consensus_guardrail_version": CONSENSUS_GUARDRAIL_VERSION,
        "consensus_guardrail": consensus_guardrail_config(),
        "calibration_version": CALIBRATION_VERSION,
        "fusion_method": "learned_logistic_stacking",
        "fusion_input_order": ["fuzzy_score", "random_forest_score"],
        "fuzzy_schema_version": FUZZY_SCHEMA_VERSION,
        "feature_names": FEATURE_NAMES,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "risk_formula": RISK_FORMULA,
        "rule_weight": None,
        "ml_weight": None,
        "policy": {
            "warning_threshold": float(warning["threshold"]) * 100.0,
            "blocking_threshold": float(blocking["threshold"]) * 100.0,
            "warning_max_fpr": args.warn_max_fpr,
            "blocking_max_fpr": args.block_max_fpr,
        },
        "probability_method": "learned_logistic_fusion_probability",
        "base_probability_method": "random_forest_vote_fraction_then_platt_calibration",
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

    report_temporary = report_path.with_suffix(report_path.suffix + ".tmp")
    report_temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    report_temporary.replace(report_path)

    model_temporary = model_path.with_suffix(model_path.suffix + ".tmp")
    joblib.dump(model_bundle, model_temporary, compress=MODEL_COMPRESSION)
    model_temporary.replace(model_path)

    print("Selected warning policy:")
    print(json.dumps(warning, ensure_ascii=False, indent=2))
    print("Selected blocking policy:")
    print(json.dumps(blocking, ensure_ascii=False, indent=2))
    print("Independent holdout:")
    print(json.dumps(holdout_evaluation, ensure_ascii=False, indent=2))
    print(f"Saved research-only candidate to {model_path}; production unchanged")
    print(f"Saved evaluation report to {report_path}")


if __name__ == "__main__":
    train(parse_args())
