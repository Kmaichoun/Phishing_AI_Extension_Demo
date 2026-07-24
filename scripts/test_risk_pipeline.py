from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import joblib

PROJECT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_DIR / "backend"
DATA_DIR = BACKEND_DIR / "data"
MODEL_PATH = BACKEND_DIR / "model.pkl"
REPORT_PATH = DATA_DIR / "risk_model_evaluation.json"
DATASET_PATH = DATA_DIR / "training_urls.csv"


def main() -> None:
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    selected = report["policy_search"]["selected"]
    max_fpr = float(report["policy_search"]["max_false_positive_rate"])
    assert 0.0 <= float(selected["alpha"]) <= 1.0
    assert 0.0 < float(selected["threshold"]) < 1.0
    assert float(selected["false_positive_rate"]) <= max_fpr
    assert len(report["policy_search"]["alpha_values"]) == 21
    assert len(report["policy_search"]["threshold_values"]) == 91

    bundle = joblib.load(MODEL_PATH)
    assert bundle["calibration"] == "sigmoid"
    assert abs(float(bundle["alpha"]) - float(selected["alpha"])) < 1e-9
    assert abs(
        float(bundle["decision_threshold"]) - float(selected["threshold"]) * 100.0
    ) < 1e-9

    if DATASET_PATH.exists():
        with DATASET_PATH.open("r", encoding="utf-8-sig", newline="") as file:
            rows = list(csv.DictReader(file))
        urls = [row["url"].casefold() for row in rows]
        labels = [int(row["label"]) for row in rows]
        assert len(rows) == int(report["dataset"]["row_count"])
        assert len(urls) == len(set(urls))
        assert labels.count(0) == labels.count(1)

    sys.path.insert(0, str(BACKEND_DIR))
    from app import PredictRequest, predict

    safe = predict(PredictRequest(url="https://www.google.com/", rule_score=0))
    risky = predict(
        PredictRequest(
            url="http://paypal-login-verify.example.xyz/account/confirm?token=test",
            rule_score=90,
        )
    )
    assert safe["model_status"] == "calibrated_model"
    assert safe["label"] == "safe"
    assert risky["label"] == "phishing"
    assert safe["alpha"] == bundle["alpha"]
    assert safe["decision_threshold"] == bundle["decision_threshold"]

    print(
        "Risk pipeline test passed: "
        f"alpha={bundle['alpha']}, threshold={bundle['decision_threshold']}, "
        f"FPR={selected['false_positive_rate']}"
    )


if __name__ == "__main__":
    main()
