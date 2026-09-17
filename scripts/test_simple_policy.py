"""Runtime contract for simple policies; no DB writes and no model replacement."""
from pathlib import Path
import sys
from unittest.mock import patch
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import app
from train_simple_model import legacy_scores


class FixedModel:
    classes_ = np.array([0, 1])

    def predict_proba(self, rows):
        return np.array([[0.2, 0.8] for _ in rows])


def main():
    for method, expected in [('ml_only', 80), ('weighted_40_60', 84)]:
        bundle = {'model':FixedModel(), 'fusion_method':method,
                  'rule_weight':0 if method == 'ml_only' else .4,
                  'ml_weight':1 if method == 'ml_only' else .6,
                  'risk_formula':'FinalScore = MLScore' if method == 'ml_only' else 'FinalScore = 0.40 * RuleScore + 0.60 * MLScore',
                  'policy':{'warning_threshold':70, 'blocking_threshold':90}}
        with patch.object(app, 'load_model_bundle', return_value=bundle):
            result = app.predict(app.PredictRequest(url='https://example.com/', rule_score=90))
            assert result['final_score'] == expected
            assert result['decision'] == 'warn'
            assert result['consensus_trigger'] is None
            assert result['fusion_applied'] is False
            assert result['risk_formula'] == bundle['risk_formula']
            if method == 'ml_only':
                zero_rule = app.predict(app.PredictRequest(url='https://example.com/', rule_score=0))
                assert zero_rule['final_score'] == result['final_score']
                assert result['layer_results']['local_rule_evidence']['status'] == 'explanation_only'
        # A promoted simple candidate must remain a correctly scored baseline.
        offline = legacy_scores(bundle, np.zeros((1, 34)), np.array([90.0]))[0] * 100
        assert abs(offline - expected) < 1e-9
    print('Simple policy contract passed: exact formula, no consensus escalation, explicit decision.')


if __name__ == '__main__':
    main()
