"""Feature compatibility and calibrated score contract, without production writes."""
import sys
from pathlib import Path
from unittest.mock import patch
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from feature_extractor import extract_features, FEATURE_SCHEMA_VERSION, LEGACY_FEATURE_SCHEMA_VERSION
from domain_parts import domain_parts
import app

assert extract_features('https://www.ku.ac.th/th')['subdomain_count'] == 0
assert extract_features('https://login.ku.ac.th/')['subdomain_count'] == 1
assert extract_features('https://www.ku.ac.th/th', LEGACY_FEATURE_SCHEMA_VERSION)['subdomain_count'] == 1
assert domain_parts('www.city.kawasaki.jp') == ('city.kawasaki.jp', 'city', 0)
assert domain_parts('a.b.ck') == ('a.b.ck', 'a', 0)
assert domain_parts('ku.ac.th.evil.example')[0] == 'evil.example'
assert domain_parts('127.0.0.1')[2] == 0
assert extract_features('https://ku.ac.th')['domain_vowel_ratio'] == .5

class Forest:
    classes_ = np.array([1, 0])  # Ensure lookup is by label, not column index.
    def predict_proba(self, rows):
        return np.array([[.81, .19] for _ in rows])

class Calibrator:
    classes_ = np.array([0, 1])
    def predict_proba(self, rows):
        assert all(abs(row[0] - .81) < 1e-9 for row in rows)
        return np.array([[.80, .20] for _ in rows])

bundle = {'model':Forest(), 'probability_calibrator':Calibrator(), 'fusion_method':'ml_only',
          'feature_schema_version':FEATURE_SCHEMA_VERSION, 'risk_formula':'FinalScore = MLScore',
          'policy':{'warning_threshold':60, 'blocking_threshold':85}}
with patch.object(app, 'load_model_bundle', return_value=bundle):
    for rule in [0, 39, 100]:
        r = app.predict(app.PredictRequest(url='https://www.ku.ac.th/th', rule_score=rule))
        assert r['final_score'] == r['ml_score'] == 20
        assert r['random_forest_raw_score'] == 81
        assert r['decision'] == 'allow'
        assert r['probability_calibrated']
        assert r['consensus_trigger'] is None and not r['fusion_applied']
        assert r['layer_results']['local_rule_evidence']['status'] == 'explanation_only'
        assert r['layer_results']['fuzzy_rule_evidence']['status'] == 'not_used'
        assert r['features']['subdomain_count'] == 0
    bundle['feature_schema_version'] = LEGACY_FEATURE_SCHEMA_VERSION
    assert app.predict(app.PredictRequest(url='https://www.ku.ac.th/th'))['features']['subdomain_count'] == 1
print('PSL features, legacy compatibility, calibration and ML-only formula passed.')
