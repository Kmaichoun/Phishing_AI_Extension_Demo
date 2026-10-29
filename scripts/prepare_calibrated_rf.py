"""Prepare an RF-only research artifact without reusing fusion thresholds/metrics.

This is formula isolation, not retraining or calibrated-policy validation.
The output is intentionally not a production bundle and cannot be passed to
manage_model.py promote. The deployed model is never changed.
"""
import argparse
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone
import joblib
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def prepare(source, destination):
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    bundle = joblib.load(source)
    if not isinstance(bundle, dict) or bundle.get('probability_calibrator') is None:
        raise ValueError('A trained forest AND a fitted probability calibrator are required.')
    if bundle.get('model_family') != 'random_forest':
        raise ValueError('Source must identify its model family as random_forest.')
    model, calibrator = bundle['model'], bundle['probability_calibrator']
    if set(model.classes_) != {0, 1} or set(calibrator.classes_) != {0, 1}:
        raise ValueError('Expected binary labels 0/1.')
    probe = calibrator.predict_proba(np.linspace(0, 1, 101).reshape(-1, 1))[:, list(calibrator.classes_).index(1)]
    if not np.isfinite(probe).all() or np.any(np.diff(probe) < -1e-12):
        raise ValueError('Calibrator must be finite and monotonic.')
    destination.mkdir(parents=True, exist_ok=False)
    # Retain schema and calibration provenance, never inherit fusion evaluation.
    artifact = {k:bundle[k] for k in ['model', 'probability_calibrator', 'model_family',
        'feature_names', 'feature_schema_version', 'calibration_version'] if k in bundle}
    artifact.update({'artifact_type':'rf_components_pending_policy',
        'production_ready':False, 'fusion_method':'ml_only',
        'risk_formula':'FinalScore = 100 * Calibrate(RandomForest(features))',
        'rule_weight':0.0, 'ml_weight':1.0,
        'source_model_sha256':source_hash, 'source_model_version':bundle.get('model_version'),
        'source_trained_at':bundle.get('trained_at'),
        'prepared_at':datetime.now(timezone.utc).isoformat(),
        'policy':None, 'metrics':None, 'retrained':False})
    joblib.dump(artifact, destination/'rf_components.pkl', compress=3)
    summary={k:v for k,v in artifact.items() if k not in {'model','probability_calibrator'}}
    summary['artifact_sha256']=hashlib.sha256((destination/'rf_components.pkl').read_bytes()).hexdigest()
    summary['remaining']=['Retrain with corrected PSL features and reviewed examples.',
        'Select RF-only thresholds on separate validation data.',
        'Evaluate real labelled holdout; compare false positives and phishing recall.',
        'Run regression/provenance/promotion checks before deployment.']
    (destination/'status.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    assert hashlib.sha256(source.read_bytes()).hexdigest()==source_hash
    return summary


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT/'backend/model.pkl')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(prepare(args.source,args.output),ensure_ascii=True,indent=2))
