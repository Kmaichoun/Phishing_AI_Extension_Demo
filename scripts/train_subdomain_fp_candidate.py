"""Training-only hard-negative experiments, retaining calibrated RF and 60/80.

Historical validation/test are reused benchmarks, not independent evidence.
Never replaces the active model. Failed candidates remain research artifacts.
"""
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
import app
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from train_recovered_rf import feature_matrix, scores, evaluate
from model_registry import sha256, atomic_json

SOURCE = ROOT / 'backend/data/simple_recovered_query_structural_rf_20261005/dataset.csv'
OUT = ROOT / 'backend/data/simple_subdomain_fp_20261008'
PROBES = [
    'https://web.facebook.com/', 'https://www.facebook.com/',
    'https://m.facebook.com/',
    'https://sites.google.com/go.buu.ac.th/regservice-burapha-university/home',
    'https://www.google.com/search?q=phishing+research',
    'https://www.youtube.com/watch?v=AwKnraP_Wno',
    'https://www.ku.ac.th/th',
]


def probes(bundle):
    with patch.object(app, 'load_model_bundle', return_value=bundle):
        return [{'url': u, **{k: v for k, v in app.predict(app.PredictRequest(url=u, rule_score=0)).items()
                             if k in ('final_score', 'decision')}} for u in PROBES]


def improves(new, old):
    return (new['warning']['false_positive_rate'] < old['warning']['false_positive_rate']
            and new['warning']['recall'] >= old['warning']['recall']
            and new['blocking']['false_positive_rate'] <= old['blocking']['false_positive_rate']
            and new['blocking']['recall'] >= old['blocking']['recall'])


def main():
    OUT.mkdir(exist_ok=False)
    baseline = app.load_model_bundle()
    baseline_hash = sha256(app.MODEL_PATH)
    assert baseline['fusion_method'] == 'ml_only'
    assert baseline['policy']['warning_threshold'] == 60
    assert baseline['policy']['blocking_threshold'] == 80
    schema = baseline['feature_schema_version']
    with SOURCE.open(encoding='utf-8', newline='') as f:
        rows = [r for r in csv.DictReader(f) if r['split'] != 'holdout']
    groups = {s: {r['group'] for r in rows if r['split'] == s}
              for s in ('train', 'calibration', 'validation')}
    assert all(not (groups[a] & groups[b]) for a, b in
               [('train', 'calibration'), ('train', 'validation'), ('calibration', 'validation')])
    print('Extracting development features; holdout excluded.', flush=True)
    x = feature_matrix(rows, schema)
    y = np.array([int(r['label']) for r in rows])
    masks = {s: np.array([r['split'] == s for r in rows]) for s in groups}
    train_x, train_y = x[masks['train']], y[masks['train']]
    old = evaluate(y[masks['validation']], scores(baseline, [], x[masks['validation']]), .6, .8)
    train_p = scores(baseline, [], train_x)
    hard = (train_y == 0) & (train_p >= .6)
    print(json.dumps({'baseline_validation': old, 'training_rows': len(train_y),
                      'training_hard_negatives': int(hard.sum()), 'baseline_probes': probes(baseline)}), flush=True)
    selected = None
    results = {}
    # Fixed small search. No probe URLs or evaluation labels are added to fit.
    for name, depth, leaf, weight in [('capacity', 28, 2, 1.5), ('moderate', 24, 5, 2.0)]:
        print('Training ' + name, flush=True)
        weights = np.where(hard, weight, 1.0)
        forest = RandomForestClassifier(n_estimators=128, max_depth=depth,
            min_samples_leaf=leaf, class_weight='balanced_subsample', random_state=20261008, n_jobs=4)
        forest.fit(train_x, train_y, sample_weight=weights)
        raw = forest.predict_proba(x[masks['calibration']])[:, list(forest.classes_).index(1)]
        calibrator = LogisticRegression(C=1e6, max_iter=1000).fit(raw.reshape(-1, 1), y[masks['calibration']])
        assert calibrator.coef_[0, 0] > 0
        candidate = {**baseline, 'model': forest, 'probability_calibrator': calibrator,
            'model_version': 'url-risk-rf-subdomain-fp-20261008-' + name,
            'trained_at': datetime.now(timezone.utc).isoformat(),
            'calibration_version': 'platt-domain-disjoint-20261008',
            'production_ready': False, 'metrics': {},
            'evaluation_design': {'reused_benchmark': True, 'independent_test': False}}
        new = evaluate(y[masks['validation']], scores(candidate, [], x[masks['validation']]), .6, .8)
        smoke = probes(candidate)
        eligible = improves(new, old) and all(r['decision'] == 'allow' for r in smoke)
        results[name] = {'validation': new, 'probes': smoke, 'eligible': eligible,
                         'parameters': {'depth': depth, 'leaf': leaf, 'hard_negative_weight': weight}}
        joblib.dump(candidate, OUT / (name + '.pkl'), compress=3)
        print(json.dumps({name: results[name]}), flush=True)
        if eligible and (selected is None or new['warning']['false_positive_rate'] < results[selected]['validation']['warning']['false_positive_rate']):
            selected = name
    atomic_json(OUT / 'selection.json', {'baseline_sha256': baseline_hash, 'dataset_sha256': sha256(SOURCE),
        'selected': selected, 'results': results, 'baseline_validation': old,
        'holdout_used_for_selection': False,
        'rule': 'Lower warning FPR; no warning/block recall regression; no block FPR regression; benign probes allow.'})
    if selected is not None:
        with SOURCE.open(encoding='utf-8', newline='') as f:
            holdout = [r for r in csv.DictReader(f) if r['split'] == 'holdout']
        assert not {r['group'] for r in holdout} & set.union(*groups.values())
        hx = feature_matrix(holdout, schema)
        hy = np.array([int(r['label']) for r in holdout])
        candidate = joblib.load(OUT / (selected + '.pkl'))
        old_h = evaluate(hy, scores(baseline, [], hx), .6, .8)
        new_h = evaluate(hy, scores(candidate, [], hx), .6, .8)
        atomic_json(OUT / 'evaluation.json', {'baseline': old_h, 'candidate': new_h,
            'better_on_reused_benchmark': improves(new_h, old_h), 'production_ready': False,
            'promotion_ready': False, 'independent_test': False})
        print(json.dumps({'reused_benchmark': new_h, 'better': improves(new_h, old_h)}), flush=True)
    assert sha256(app.MODEL_PATH) == baseline_hash
    print('Finished. Active model unchanged.', flush=True)


if __name__ == '__main__':
    main()
