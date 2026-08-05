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
    warning = report["policy"]["warning"]
    blocking = report["policy"]["blocking"]
    assert report["model"]["family"] == "L1-regularized logistic regression"
    assert report["model"]["risk_formula"] == "RiskScore = 100 * sigmoid(w dot x + b)"
    assert report["evaluation_design"]["group"] == "hostname"
    assert float(warning["threshold"]) <= float(blocking["threshold"])
    assert float(warning["false_positive_rate_upper_95"]) <= float(
        warning["max_false_positive_rate"]
    )
    assert float(blocking["false_positive_rate_upper_95"]) <= float(
        blocking["max_false_positive_rate"]
    )
    assert warning["meets_fpr_constraint"] is True
    assert blocking["meets_fpr_constraint"] is True

    bundle = joblib.load(MODEL_PATH)
    assert bundle["model_version"] == report["model"]["version"]
    assert bundle["probability_method"] == "intrinsic_logistic_sigmoid"
    assert "alpha" not in bundle
    assert abs(
        float(bundle["policy"]["warning_threshold"])
        - float(warning["threshold"]) * 100.0
    ) < 1e-9
    assert abs(
        float(bundle["policy"]["blocking_threshold"])
        - float(blocking["threshold"]) * 100.0
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
    assert safe["model_status"] == "ready"
    assert safe["label"] == "safe"
    assert safe["decision"] == "allow"
    assert risky["label"] == "phishing"
    assert risky["decision"] in {"warn", "block"}
    assert safe["risk_score"] == safe["ml_score"] == safe["final_score"]
    assert safe["alpha"] is None
    assert safe["warning_threshold"] == bundle["policy"]["warning_threshold"]
    assert safe["blocking_threshold"] == bundle["policy"]["blocking_threshold"]
    assert safe["layer_results"]["local_rule_evidence"]["status"] == "evidence_only"

    print(
        "Risk pipeline test passed: "
        f"warn={bundle['policy']['warning_threshold']}, "
        f"block={bundle['policy']['blocking_threshold']}, "
        f"holdout ROC-AUC={report['independent_holdout']['probability']['roc_auc']}"
    )


if __name__ == "__main__":
    main()
