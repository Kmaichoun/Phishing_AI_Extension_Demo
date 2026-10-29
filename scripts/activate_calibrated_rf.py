"""Activate the user's RF-only formula using existing trained components.

Back up the previous bundle, preserve its feature schema and decision cutoffs,
and remove evaluation claims belonging to the previous fusion formula.
This is an operational formula change, not retraining or a validated FPR gain.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FORMULA = 'Score = 100 × Calibrate(Random Forest)'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def activate(path):
    bundle = joblib.load(path)
    if bundle.get('fusion_method') == 'ml_only' and bundle.get('risk_formula') == FORMULA:
        return {'already_active': True, 'model_sha256': digest(path)}
    if bundle.get('model_family') != 'random_forest' or bundle.get('probability_calibrator') is None:
        raise ValueError('A fitted Random Forest and probability calibrator are required')
    if bundle.get('production_ready') is False:
        raise ValueError('A research draft cannot supply the operating decision policy')
    model, calibrator = bundle['model'], bundle['probability_calibrator']
    if set(model.classes_) != {0, 1} or set(calibrator.classes_) != {0, 1}:
        raise ValueError('Expected binary labels 0/1')
    probe = calibrator.predict_proba(np.linspace(0, 1, 101).reshape(-1, 1))[:, list(calibrator.classes_).index(1)]
    if not np.isfinite(probe).all() or np.any(np.diff(probe) < -1e-12):
        raise ValueError('Calibration must be finite and monotonic')
    policy = bundle.get('policy')
    if not isinstance(policy, dict) or not 0 <= policy['warning_threshold'] <= policy['blocking_threshold'] <= 100:
        raise ValueError('Existing operating cutoffs are required')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup = path.parent / 'model_backups' / ('before-calibrated-rf-' + stamp)
    backup.mkdir(parents=True, exist_ok=False)
    old_bytes = path.read_bytes()
    (backup / 'model.pkl').write_bytes(old_bytes)
    old_hash = hashlib.sha256(old_bytes).hexdigest()
    # Keep the fitted forest, fitted calibration and exact feature meanings.
    converted = dict(bundle)
    for key in ('fusion_model', 'fusion_input_order', 'consensus_guardrail', 'consensus_guardrail_version'):
        converted.pop(key, None)
    converted.update({
        'model_version': str(bundle.get('model_version', 'random-forest')) + '-rf-only',
        'policy_version': 'calibrated-rf-only-operating-cutoffs-' + stamp,
        'fusion_method': 'ml_only', 'fusion_version': None,
        'risk_formula': FORMULA, 'rule_weight': 0.0, 'ml_weight': 1.0,
        'probability_method': 'random_forest_vote_fraction_then_platt_calibration',
        'metrics': None, 'evaluation_design': None,
        'formula_changed_at': datetime.now(timezone.utc).isoformat(),
        'formula_change_source_sha256': old_hash,
        'policy_validation_status': 'pending_rf_only_evaluation',
        'retrained_during_formula_change': False,
        'policy': {'warning_threshold': float(policy['warning_threshold']),
                   'blocking_threshold': float(policy['blocking_threshold']),
                   'validation_status': 'Existing operating cutoffs retained at user-requested formula change; RF-only FPR not validated'},
    })
    temporary = path.with_suffix('.rf-only.tmp')
    joblib.dump(converted, temporary, compress=3)
    loaded = joblib.load(temporary)
    assert loaded['fusion_method'] == 'ml_only' and loaded['metrics'] is None
    assert loaded.get('feature_schema_version') == bundle.get('feature_schema_version')
    np.testing.assert_array_equal(loaded['probability_calibrator'].predict_proba([[0.0], [0.5], [1.0]]),
                                  calibrator.predict_proba([[0.0], [0.5], [1.0]]))
    if digest(path) != old_hash:
        raise ValueError('Operating model changed concurrently; refusing to overwrite')
    os.replace(temporary, path)
    summary = {'formula': FORMULA, 'model_version': converted['model_version'],
               'previous_model_sha256': old_hash, 'active_model_sha256': digest(path),
               'backup': str(backup / 'model.pkl'), 'policy': converted['policy'],
               'maximum_calibrated_score': float(probe.max() * 100),
               'automatic_block_reachable': bool(probe.max() * 100 >= policy['blocking_threshold']),
               'metrics': None, 'retrained': False, 'false_positive_improvement_verified': False}
    (backup / 'formula-change.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    output = ROOT / 'output/calibrated-rf-active'
    output.mkdir(parents=True, exist_ok=True)
    (output / 'status.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, default=ROOT / 'backend/model.pkl')
    print(json.dumps(activate(parser.parse_args().model.resolve()), ensure_ascii=True, indent=2))
