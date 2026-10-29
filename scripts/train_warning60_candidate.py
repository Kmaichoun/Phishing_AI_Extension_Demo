"""Fixed-threshold RF experiment. Select on validation before opening reused holdout."""
import csv
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from train_recovered_rf import feature_matrix, scores, evaluate
from model_registry import sha256, atomic_json

SOURCE = ROOT / 'backend/data/simple_recovered_query_structural_rf_20261005'
OUT = ROOT / 'backend/data/simple_warning60_20261007'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--unweighted', action='store_true')
    args = parser.parse_args()
    global OUT
    if args.unweighted:
        OUT = ROOT / 'backend/data/simple_warning60_unweighted_20261007'
    OUT.mkdir(exist_ok=True)
    baseline = joblib.load(ROOT / 'backend/model.pkl')
    model_hash = sha256(ROOT / 'backend/model.pkl')
    if model_hash != sha256(SOURCE / 'candidate.pkl'):
        raise ValueError('Unexpected baseline')
    with (SOURCE / 'dataset.csv').open(encoding='utf-8', newline='') as f:
        rows = [r for r in csv.DictReader(f) if r['split'] != 'holdout']
    groups = {s: {r['group'] for r in rows if r['split'] == s}
              for s in ('train', 'calibration', 'validation')}
    assert not (groups['train'] & groups['calibration'] or groups['train'] & groups['validation']
                or groups['calibration'] & groups['validation'])
    schema = baseline['feature_schema_version']
    print('Extracting development features; holdout excluded...', flush=True)
    x = feature_matrix(rows, schema)
    y = np.array([int(r['label']) for r in rows])
    masks = {s: np.array([r['split'] == s for r in rows]) for s in groups}
    baseline_p = scores(baseline, [], x[masks['validation']])
    old = evaluate(y[masks['validation']], baseline_p, .6, .9577)
    print(json.dumps({'baseline_validation_at_60': old}), flush=True)
    # More capacity and smaller leaves preserve uncommon legitimate URL shapes.
    # Fixed configuration, no validation or holdout rows are mined for training.
    forest = RandomForestClassifier(n_estimators=160, max_depth=None if args.unweighted else 32,
                                    min_samples_leaf=1 if args.unweighted else 2,
                                    class_weight=None if args.unweighted else 'balanced_subsample',
                                    random_state=20261007, n_jobs=4)
    print('Training 160 trees on training partition only...', flush=True)
    forest.fit(x[masks['train']], y[masks['train']])
    raw = forest.predict_proba(x[masks['calibration']])[:, list(forest.classes_).index(1)]
    calibrator = LogisticRegression(C=1e6, max_iter=1000).fit(raw.reshape(-1, 1), y[masks['calibration']])
    assert calibrator.coef_[0, 0] > 0
    candidate = {**baseline, 'model': forest, 'probability_calibrator': calibrator,
                 'model_version': 'url-risk-rf-warning60-20261007' + ('-unweighted' if args.unweighted else ''),
                 'policy_version': 'rf-fixed-warning60-20261007',
                 'calibration_version': 'platt-domain-disjoint-20261007',
                 'trained_at': datetime.now(timezone.utc).isoformat(),
                 'policy': {**baseline['policy'], 'warning_threshold': 60.0},
                 'production_ready': False}
    vp = scores(candidate, [], x[masks['validation']])
    new = evaluate(y[masks['validation']], vp, .6, .9577)
    selected = (new['warning']['false_positive_rate'] < old['warning']['false_positive_rate']
                and new['warning']['recall'] >= old['warning']['recall'])
    atomic_json(OUT / 'selection.json', {'baseline_sha256': model_hash, 'selected': selected,
        'rule': 'Lower validation FPR and no recall regression at fixed threshold 60.',
        'baseline': old, 'candidate': new, 'holdout_used_for_selection': False})
    joblib.dump(candidate, OUT / 'candidate.pkl', compress=3)
    print(json.dumps({'validation_candidate': new, 'selected': selected}), flush=True)
    if not selected:
        print('Candidate rejected on validation; operating model unchanged.', flush=True)
        return
    # Selection is frozen before re-opening the previously used benchmark.
    with (SOURCE / 'dataset.csv').open(encoding='utf-8', newline='') as f:
        holdout = [r for r in csv.DictReader(f) if r['split'] == 'holdout']
    assert not {r['group'] for r in holdout} & set.union(*groups.values())
    hx = feature_matrix(holdout, schema)
    hy = np.array([int(r['label']) for r in holdout])
    hp = scores(candidate, [], hx)
    oldp = scores(baseline, [], hx)
    hm = evaluate(hy, hp, .6, .9577)
    baseline_60 = evaluate(hy, oldp, .6, .9577)
    baseline_original = evaluate(hy, oldp, .8505, .9577)
    candidate['metrics'] = {'validation': new, 'reused_benchmark': hm}
    candidate['policy']['warning_max_fpr'] = None
    candidate['policy']['blocking_max_fpr'] = None
    joblib.dump(candidate, OUT / 'candidate.pkl', compress=3)
    evaluation = {'baseline_sha256': model_hash, 'candidate_sha256': sha256(OUT / 'candidate.pkl'),
        'candidate_holdout': hm, 'baseline_at_60': baseline_60, 'baseline_original': baseline_original,
        'validation': new, 'promotion_ready': False, 'production_ready': False,
        'test_reused_after_previous_experiments': True,
        'candidate_better_at_60': (hm['warning']['false_positive_rate'] < baseline_60['warning']['false_positive_rate']
                                 and hm['warning']['recall'] >= baseline_60['warning']['recall']),
        'limitation': 'Historical reused benchmark; not independent generalization evidence.'}
    atomic_json(OUT / 'evaluation.json', evaluation)
    print(json.dumps(evaluation), flush=True)


if __name__ == '__main__':
    main()
