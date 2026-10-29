"""Activate the requested threshold without replacing RF/calibration; keep a backup."""
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
import joblib
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from feature_extractor import feature_vector

MODEL = ROOT / 'backend/model.pkl'
AUTH = ROOT / 'backend/model-demo-authorization.json'
OUT = ROOT / 'output/warning60-20261007'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    report = json.loads((OUT / 'threshold-evaluation.json').read_text(encoding='utf-8'))
    before = MODEL.read_bytes()
    if digest(before) != report['model_sha256']:
        raise ValueError('Operating model changed since evaluation; refusing overwrite')
    auth_before = AUTH.read_bytes()
    auth = json.loads(auth_before)
    if auth['model_sha256'] != digest(before) or auth['mode'] != 'user_requested_web_test':
        raise ValueError('Expected the authorized experimental demo model')
    baseline = joblib.load(MODEL)
    if baseline['fusion_method'] != 'ml_only' or baseline.get('production_ready') is not False:
        raise ValueError('Unexpected deployment mode')
    # Policy edit only: forest, features, calibrator, and probabilities stay intact.
    updated = {**baseline, 'policy_version': 'rf-warning60-block80-user-policy-20261007',
               'policy': {**baseline['policy'], 'warning_threshold': 60.0, 'blocking_threshold': 80.0,
                          'warning_max_fpr': None, 'blocking_max_fpr': None},
               'metrics_at_original_policy': baseline.get('metrics_at_original_policy', baseline['metrics']),
               'original_policy': baseline.get('original_policy', baseline['policy']),
               'operating_policy_note': 'User-requested warning 60 and block 80; historical FPR rises versus original thresholds.',
               'metrics': {**baseline['metrics']}}
    selection = json.loads((ROOT / 'backend/data/simple_warning60_20261007/selection.json').read_text(encoding='utf-8'))
    updated['metrics']['validation'] = {k:v for k,v in selection['baseline'].items() if k != 'blocking'}
    updated['metrics']['reused_benchmark'] = {
        **baseline['metrics']['reused_benchmark'],
        'warning': {**report['requested_policy'], 'threshold': .6},
        'blocking': {**report['requested_blocking_policy'], 'threshold': .8}}
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup = ROOT / 'backend/model_backups' / ('before-warning60-' + stamp)
    backup.mkdir(parents=True, exist_ok=False)
    (backup / MODEL.name).write_bytes(before)
    (backup / AUTH.name).write_bytes(auth_before)
    candidate = MODEL.with_suffix('.policy.tmp')
    joblib.dump(updated, candidate, compress=3)
    reloaded = joblib.load(candidate)
    probe = feature_vector('https://sdk-prod-cdn-aws.kurogame-service.com/pro/account-center/mc/bind-email', baseline['feature_schema_version'])
    # Compare semantic tree state, not pickle hashes: structured NumPy node
    # records can contain padding bytes that change across serialization.
    forest_before, forest_after = baseline['model'], reloaded['model']
    assert forest_before.get_params() == forest_after.get_params()
    np.testing.assert_array_equal(forest_before.classes_, forest_after.classes_)
    assert len(forest_before.estimators_) == len(forest_after.estimators_)
    for old_tree, new_tree in zip(forest_before.estimators_, forest_after.estimators_):
        old_state, new_state = old_tree.tree_.__getstate__(), new_tree.tree_.__getstate__()
        assert old_state.keys() == new_state.keys()
        for key, value in old_state.items():
            if isinstance(value, np.ndarray):
                np.testing.assert_array_equal(value, new_state[key])
            else:
                assert value == new_state[key]
    for attr in ('coef_', 'intercept_', 'classes_', 'n_iter_'):
        np.testing.assert_array_equal(getattr(baseline['probability_calibrator'], attr),
                                      getattr(reloaded['probability_calibrator'], attr))
    # Parallel tree summation can differ in the last floating-point bit.
    np.testing.assert_allclose(baseline['model'].predict_proba([probe]),
                               reloaded['model'].predict_proba([probe]), rtol=0, atol=1e-12)
    active_hash = digest(candidate.read_bytes())
    authorization = {**auth, 'model_sha256': active_hash, 'source': str(candidate),
        'authorized_at': datetime.now(timezone.utc).isoformat(),
        'reason': 'User requested warning 60 and block 80. RF unchanged; rejected accuracy candidates not deployed.',
        'previous_model_sha256': digest(before), 'backup': str(backup / 'model.pkl'),
        'production_ready': False, 'promotion_ready': False}
    if MODEL.read_bytes() != before or AUTH.read_bytes() != auth_before:
        raise ValueError('Concurrent model or authorization change')
    authorization['source'] = str(MODEL)
    auth_tmp = AUTH.with_suffix('.policy.tmp')
    auth_tmp.write_text(json.dumps(authorization, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(auth_tmp, AUTH)
    try:
        os.replace(candidate, MODEL)
    except OSError:
        AUTH.write_bytes(auth_before)
        raise
    (OUT / 'active-policy.json').write_text(json.dumps({**authorization,
        'policy': updated['policy'], 'original_policy': baseline['policy'],
        'model_retrained': False, 'threshold_evaluation': report}, indent=2), encoding='utf-8')
    print(json.dumps({'warning_threshold':60, 'blocking_threshold':updated['policy']['blocking_threshold'],
                      'active_sha256':active_hash, 'backup':str(backup)}, indent=2))


if __name__ == '__main__':
    main()
