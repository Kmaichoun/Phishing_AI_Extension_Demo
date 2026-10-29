from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from urllib.parse import urlencode

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
    assert report["model"]["family"] == "Random Forest classifier"
    assert report["model"]["risk_formula"].startswith(
        "FinalScore = 100 * ConsensusGuardrail("
    )
    assert report["model"]["fusion_version"] == "logistic-stacking-fusion-1.0"
    assert report["learned_fusion"]["input_order"] == [
        "fuzzy_score",
        "random_forest_score",
    ]
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

    active = joblib.load(MODEL_PATH)
    if active.get('fusion_method') == 'ml_only':
        change = json.loads((PROJECT_DIR / 'output/calibrated-rf-active/status.json').read_text(encoding='utf-8'))
        bundle = joblib.load(change['backup'])
        assert active['metrics'] is None
        assert active['risk_formula'] == 'Score = 100 × Calibrate(Random Forest)'
        assert active['feature_schema_version'] == bundle['feature_schema_version']
        assert active['rule_weight'] == 0.0 and active['ml_weight'] == 1.0
        assert 'fusion_model' not in active
    else:
        bundle = active
    assert bundle["model_version"] == report["model"]["version"]
    assert bundle["model_family"] == "random_forest"
    assert bundle["probability_method"] == "learned_logistic_fusion_probability"
    assert bundle["base_probability_method"] == (
        "random_forest_vote_fraction_then_platt_calibration"
    )
    assert "probability_calibrator" in bundle
    assert bundle["consensus_guardrail_version"] == "two-layer-consensus-1.0"
    assert report["probability_calibration"]["method"] == (
        "Platt scaling (logistic regression)"
    )
    assert bundle["fusion_method"] == "learned_logistic_stacking"
    assert bundle["rule_weight"] is None
    assert bundle["ml_weight"] is None
    assert "fusion_model" in bundle
    assert bundle["risk_formula"] == report["model"]["risk_formula"]
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
    from feature_extractor import feature_vector
    from fuzzy_scoring import fuzzy_memberships, fuzzy_score

    assert feature_vector("https://www.google.com/") == feature_vector(
        "https://google.com/"
    )
    assert fuzzy_score(0) == 0
    assert fuzzy_score(50) == 50
    assert fuzzy_score(100) == 100
    assert fuzzy_memberships(50)["suspicious"] == 1

    safe = predict(PredictRequest(url="https://www.google.com/", rule_score=0))
    long_google_search = "https://www.google.com/search?" + urlencode(
        {
            "q": "เว็บไซต์สำหรับค้นหาข้อมูลภาษาไทย",
            "sca_esv": "588441138e93f763",
            "sxsrf": "AHTn8zqNucIpTLDDAZcisLGLEMlUudcdQw",
            "source": "hp",
            "ei": "e8h1W9opKYnu6oq",
            "iflsig": "AOw8s4IAAAAA",
            "oq": "เว็บไซต์สำหรับค้นหาข้อมูลภาษาไทย",
            "gs_lp": "Egdnd3Mtd2l6IjdQAgEgAMgCQIxjQAhgm" * 4,
            "ved": "0ahUKEwi123456789",
        }
    )
    safe_deep_links = [
        "https://www.youtube.com/watch?v=AwKnraP_Wno",
        "https://www.youtube.com/results?search_query=cybersecurity",
        "https://www.google.com/search?q=phishing+research",
        long_google_search,
        "https://github.com/openai/openai-python/issues/123",
        "https://en.wikipedia.org/wiki/Phishing",
    ]
    safe_deep_link_results = [
        predict(PredictRequest(url=url, rule_score=0))
        for url in safe_deep_links
    ]
    risky = predict(
        PredictRequest(
            url="http://paypal-login-verify.example.xyz/account/confirm?token=test",
            rule_score=90,
        )
    )
    assert safe["model_status"] == "ready"
    assert safe["label"] == "safe"
    assert safe["decision"] == "allow"
    assert all(result["decision"] == "allow" for result in safe_deep_link_results)
    assert all(result["probability_calibrated"] is True for result in safe_deep_link_results)
    assert safe_deep_link_results[0]["final_score"] < 20
    assert safe_deep_link_results[3]["final_score"] < (
        safe_deep_link_results[3]["warning_threshold"] * 0.6
    )
    assert risky["label"] == "phishing"
    assert risky["decision"] == ('warn' if active.get('fusion_method') == 'ml_only' else 'block')
    assert risky["consensus_trigger"] == (None if active.get('fusion_method') == 'ml_only' else 'block_consensus')
    assert safe["risk_score"] == safe["final_score"]
    assert safe["fuzzy_score"] == 0
    assert risky["fuzzy_score"] == 100
    assert safe["random_forest_score"] == safe["ml_score"]
    assert safe["fusion_method"] == active['fusion_method']
    assert safe["fusion_applied"] is (active.get('fusion_method') != 'ml_only')
    assert safe["alpha"] == active['rule_weight']
    assert safe["rule_weight"] == active['rule_weight']
    assert safe["ml_weight"] == active['ml_weight']
    assert safe["formula_applied"] is True
    assert safe["warning_threshold"] == bundle["policy"]["warning_threshold"]
    assert safe["blocking_threshold"] == bundle["policy"]["blocking_threshold"]
    if active.get('fusion_method') == 'ml_only':
        assert safe['layer_results']['local_rule_evidence']['status'] == 'explanation_only'
        assert safe['layer_results']['fuzzy_rule_evidence']['status'] == 'not_used'
        assert safe['layer_results']['learned_fusion']['status'] == 'unavailable'
        for url in ['https://www.ku.ac.th/th', *safe_deep_links, 'http://paypal-login-verify.example.xyz/account/confirm?token=test']:
            raw = active['model'].predict_proba([feature_vector(url, active['feature_schema_version'])])[0][list(active['model'].classes_).index(1)]
            calibrated = active['probability_calibrator'].predict_proba([[raw]])[0][list(active['probability_calibrator'].classes_).index(1)]
            for rule in [0, 39, 100]:
                result = predict(PredictRequest(url=url, rule_score=rule))
                assert result['final_score'] == result['ml_score'] == int(round(100 * calibrated))
                assert result['risk_formula'] == active['risk_formula']
                assert result['consensus_trigger'] is None
    else:
        assert safe['layer_results']['local_rule_evidence']['status'] == 'fuzzy_input'
        assert safe['layer_results']['fuzzy_rule_evidence']['status'] == 'ready'
        assert safe['layer_results']['learned_fusion']['status'] == 'ready'

    print(
        "Risk pipeline test passed: "
        f"warn={bundle['policy']['warning_threshold']}, "
        f"block={bundle['policy']['blocking_threshold']}, "
        f"formula={active['risk_formula']} (historical evaluation checked separately)"
    )


if __name__ == "__main__":
    main()
