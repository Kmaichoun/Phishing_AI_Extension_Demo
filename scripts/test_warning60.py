"""Threshold boundaries and RF readiness without DB/network operations."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import app


class Model:
    classes_ = np.array([0, 1])

    def __init__(self, p):
        self.p = p

    def predict_proba(self, rows):
        return np.array([[1-self.p, self.p] for _ in rows])


class Warning60Tests(unittest.TestCase):
    def test_boundaries(self):
        for score, decision in [(59.99, 'allow'), (60, 'warn'), (60.01, 'warn'), (79.99, 'warn'), (80, 'block')]:
            self.assertEqual(app.risk_decision(score, 60, 80), decision)

    def test_fallback_default(self):
        self.assertEqual(app.model_policy(None)['warning_threshold'], 60)
        self.assertEqual(app.model_policy(None)['blocking_threshold'], 80)

    def test_ready_rf_does_not_require_fusion_or_rule_score(self):
        for p, decision in [(.59, 'allow'), (.60, 'warn'), (.79, 'warn'), (.80, 'block')]:
            bundle = {'model': Model(p), 'fusion_method': 'ml_only',
                      'policy': {'warning_threshold': 60, 'blocking_threshold': 80}}
            with patch.object(app, 'load_model_bundle', return_value=bundle):
                result = app.predict(app.PredictRequest(url='https://example.com/', rule_score=100))
            self.assertEqual(result['model_status'], 'ready')
            self.assertFalse(result['fusion_applied'])
            self.assertEqual(result['decision'], decision)
            self.assertEqual(result['final_score'], round(p * 100))


if __name__ == '__main__':
    unittest.main()
