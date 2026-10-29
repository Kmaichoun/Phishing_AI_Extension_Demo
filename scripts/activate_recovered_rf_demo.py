"""Install an evaluated, user-requested RF artifact for experimental Web testing."""
import hashlib
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from feature_extractor import feature_vector

SOURCE = ROOT / 'backend/data/simple_recovered_rf_20261005/candidate.pkl'
EXPECTED = 'ebf70940903f3dda11cb39edc312dc17ced381ad0fd2f677b44f1a9f63e9bb85'
MODEL = ROOT / 'backend/model.pkl'
AUTH = ROOT / 'backend/model-demo-authorization.json'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--experiment', type=Path, help='User-requested follow-up experiment for Web demo')
    args = parser.parse_args()
    source, expected = SOURCE, EXPECTED
    evaluation = None
    if args.experiment:
        experiment = args.experiment.resolve()
        if experiment.parent != (ROOT / 'backend/data').resolve() or not experiment.name.startswith('simple_'):
            raise ValueError('Experiment must be a direct simple_* child of backend/data')
        evaluation = json.loads((experiment / 'evaluation.json').read_text(encoding='utf-8'))
        source, expected = experiment / 'candidate.pkl', evaluation['candidate_sha256']
    candidate = source.read_bytes()
    if digest(candidate) != expected:
        raise ValueError('Evaluated candidate changed; refusing activation')
    bundle = joblib.load(source)
    if bundle.get('production_ready') is not False or bundle.get('fusion_method') != 'ml_only':
        raise ValueError('Expected the unchanged research RF-only candidate')
    targeted_repair = bundle.get('evaluation_design', {}).get('targeted_repair') is True
    if targeted_repair:
        if not evaluation or evaluation.get('measured_gate_passed') is not True or evaluation.get('targeted_repair') is not True:
            raise ValueError('Reference-root repair requires its frozen confirmation to pass')
        if digest(MODEL.read_bytes()) != evaluation.get('baseline_sha256'):
            raise ValueError('Operating baseline changed after confirmation')
        for result in evaluation['evaluations'].values():
            if result.get('measured_gate_passed') is not True:
                raise ValueError('An individual confirmation cohort failed')
            for transition in result['paired_transitions'].values():
                if transition['phishing_lost'] or transition['false_positives_added']:
                    raise ValueError('Repair must preserve every previously detected phishing URL')
        from reference_origin_features import registry
        if bundle.get('reference_origin_registry_sha256') != registry()[1]:
            raise ValueError('Reference-origin evidence changed after training')
    raw = bundle['model'].predict_proba([feature_vector('https://www.ku.ac.th/th', bundle['feature_schema_version'])])[0]
    probability = bundle['probability_calibrator'].predict_proba([[raw[list(bundle['model'].classes_).index(1)]]])[0]
    score = float(probability[list(bundle['probability_calibrator'].classes_).index(1)] * 100)
    if not 0 <= score < 40:
        raise ValueError('KU smoke check failed')
    previous = MODEL.read_bytes()
    if digest(previous) == expected:
        raise ValueError('Already installed; retain the existing backup and authorization')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup = ROOT / 'backend/model_backups' / ('before-rf-demo-' + stamp)
    backup.mkdir(parents=True, exist_ok=False)
    (backup / 'model.pkl').write_bytes(previous)
    if AUTH.exists():
        (backup / AUTH.name).write_bytes(AUTH.read_bytes())
    authorization = {'mode': 'user_requested_web_test', 'model_sha256': expected,
        'source': str(source), 'authorized_at': datetime.now(timezone.utc).isoformat(),
        'reason': ('User requested targeted RF false-positive repair; frozen no-regression checks passed; production gates remain unmet'
                   if targeted_repair else 'User requested RF false-positive improvements for Web testing; failed production gates retained'),
        'production_ready': False, 'promotion_ready': False,
        'previous_model_sha256': digest(previous), 'backup': str(backup / 'model.pkl')}
    # Authorize this exact artifact before the atomic switch. Other drafts remain rejected.
    AUTH.with_suffix('.tmp').write_text(json.dumps(authorization, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(AUTH.with_suffix('.tmp'), AUTH)
    temporary = MODEL.with_suffix('.demo.tmp')
    temporary.write_bytes(candidate)
    if MODEL.read_bytes() != previous:
        raise ValueError('Operating model changed concurrently')
    os.replace(temporary, MODEL)
    report_dir = ROOT / 'output' / args.experiment.name if targeted_repair else ROOT / ('output/retrained-rf-query-20261005' if args.experiment else 'output/retrained-rf-20261005')
    report_dir.mkdir(parents=True, exist_ok=True)
    output = report_dir / 'demo-active.json'
    output.write_text(json.dumps({**authorization, 'model_version': bundle['model_version'],
        'risk_formula': bundle['risk_formula'], 'policy': bundle['policy'], 'ku_score': score},
        ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'active_sha256': expected, 'backup': str(backup / 'model.pkl'),
        'ku_score': score, 'production_ready': False}, indent=2))


if __name__ == '__main__':
    main()
