"""Prespecified pooling of existing RF trees, independently recalibrated.

No URL exceptions or threshold changes. This is a heterogeneous tree forest:
96 older trees plus a prefix of 16/32/64/128 trees fit on augmented training.
Selection uses validation only; previously read tests are regression diagnostics.
"""
import copy
import argparse
import json
import sys
from pathlib import Path
from datetime import datetime, timezone
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
import app
import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from probability_calibration import IsotonicProbabilityCalibrator, BetaProbabilityCalibrator
from train_host_context_candidate import read, reliability
from train_recovered_rf import feature_matrix, evaluate
from train_subdomain_fp_candidate import probes, improves
from model_registry import sha256, atomic_json

OUT = ROOT / 'backend/data/simple_incremental_rf_20261008'
SOURCE = ROOT / 'backend/data/simple_host_context_20261008'


def pooled_forest(old, new, count):
    forest = copy.copy(old)
    assert old.n_features_in_ == new.n_features_in_
    assert np.array_equal(old.classes_, new.classes_)
    forest.estimators_ = list(old.estimators_) + list(new.estimators_[:count])
    forest.n_estimators = len(forest.estimators_)
    return forest


def metric(y, p):
    value = evaluate(y, p, .6, .8)
    value['calibration'] = reliability(y, p)
    return value


def main():
    parser = argparse.ArgumentParser()
    method_group = parser.add_mutually_exclusive_group()
    method_group.add_argument('--isotonic', action='store_true')
    method_group.add_argument('--beta', action='store_true')
    args = parser.parse_args()
    method = 'beta' if args.beta else 'isotonic' if args.isotonic else 'platt'
    out = ROOT / ('backend/data/simple_incremental_' + method + '_20261008') if method != 'platt' else OUT
    out.mkdir(exist_ok=False)
    baseline = app.load_model_bundle()
    donor = joblib.load(SOURCE / 'augmented_v5.pkl')
    assert len(baseline['model'].estimators_) == 96
    assert baseline['feature_names'] == donor['feature_names']
    baseline_hash = sha256(app.MODEL_PATH)
    rows = read(SOURCE / 'dataset.csv')
    parts = {s: [r for r in rows if r['split'] == s] for s in ('calibration', 'validation')}
    original = read(ROOT / 'backend/data/simple_recovered_query_structural_rf_20261005/dataset.csv')
    old_urls = {r['url'] for r in original if r['split'] in parts}
    del rows, original
    atomic_json(out / 'design.json', {'created_at': datetime.now(timezone.utc).isoformat(),
        'calibration_method': method,
        'counts': [16, 32, 64, 128], 'calibration_sets': ['combined', 'historical'],
        'selection': 'All validation strata must reduce warning FPR without warning/block recall loss or block FPR increase; benign probes allow.',
        'heldout_scores_used_for_selection': False, 'baseline_sha256': baseline_hash,
        'donor_sha256': sha256(SOURCE / 'augmented_v5.pkl'),
        'development_sha256': sha256(SOURCE / 'dataset.csv'),
        'forest_type': 'Pooled previously trained trees; heterogeneous training populations and hyperparameters, not a new uniform RF fit.'})
    matrices, labels, raw_old, raw_new, masks = {}, {}, {}, {}, {}
    for split, part in parts.items():
        print('Extracting ' + split, flush=True)
        matrices[split] = feature_matrix(part, baseline['feature_schema_version'])
        labels[split] = np.array([int(r['label']) for r in part])
        masks[split] = np.array([r['url'] in old_urls for r in part])
        raw_old[split] = baseline['model'].predict_proba(matrices[split])[:, 1]
        # Cache each new tree once. All models use the same feature schema/order.
        raw_new[split] = np.array([t.predict_proba(matrices[split])[:, 1] for t in donor['model'].estimators_])
    base_p = baseline['probability_calibrator'].predict_proba(raw_old['validation'].reshape(-1, 1))[:, 1]
    strata = {'all': np.ones(len(base_p), dtype=bool), 'historical': masks['validation'], 'augmentation': ~masks['validation']}
    base_metrics = {s: metric(labels['validation'][mask], base_p[mask]) for s, mask in strata.items()}
    results, eligible, bundles = {}, [], {}
    for count in (16, 32, 64, 128):
        raw = {s: (raw_old[s] * 96 + raw_new[s][:count].sum(axis=0)) / (96 + count) for s in parts}
        for cal_set in ('combined', 'historical'):
            name = f'pooled_{count}_{cal_set}' + ('_' + method if method != 'platt' else '')
            cmask = np.ones(len(labels['calibration']), dtype=bool) if cal_set == 'combined' else masks['calibration']
            calibrator = (BetaProbabilityCalibrator() if args.beta else IsotonicProbabilityCalibrator() if args.isotonic else LogisticRegression(C=1e6, max_iter=1000)).fit(raw['calibration'][cmask].reshape(-1, 1), labels['calibration'][cmask])
            if method == 'platt': assert calibrator.coef_[0, 0] > 0
            p = calibrator.predict_proba(raw['validation'].reshape(-1, 1))[:, 1]
            metrics = {s: metric(labels['validation'][mask], p[mask]) for s, mask in strata.items()}
            bundle = {**baseline, 'model': pooled_forest(baseline['model'], donor['model'], count),
                'probability_calibrator': calibrator, 'model_version': 'url-risk-pooled-rf-20261008-' + name,
                'trained_at': datetime.now(timezone.utc).isoformat(), 'production_ready': False,
                'statistical_gate_passed': False, 'metrics': {'validation': metrics['all']},
                'calibration_version': method + '-disjoint-pooled-20261008-' + cal_set,
                'calibration': 'heldout_' + method + '_random_forest',
                'probability_method': 'heldout_' + method + '_random_forest',
                'dataset_row_count': donor['dataset_row_count'],
                'evaluation_design': {'prior_exposure_audit_complete': False, 'forward_temporal_test': False},
                'training_provenance': {'old_trees': 96, 'added_trees': count, 'calibration_set': cal_set,
                    'donor': 'augmented_v5.pkl', 'license': 'CC BY-NC 4.0'}}
            regression = probes(bundle)
            passed = all(improves(metrics[s], base_metrics[s]) for s in strata) and all(r['decision'] == 'allow' for r in regression)
            results[name] = {'metrics': metrics, 'probes': regression, 'eligible': passed}
            bundles[name] = bundle
            if passed: eligible.append(name)
            print(json.dumps({name: {'eligible': passed, 'facebook': regression[0]['final_score'],
                'warning': metrics['all']['warning'], 'historical_warning': metrics['historical']['warning']}}), flush=True)
    selected = min(eligible, key=lambda n: results[n]['metrics']['all']['warning']['false_positive_rate']) if eligible else None
    atomic_json(out / 'selection.json', {'selected': selected, 'baseline_validation': base_metrics,
        'candidates': results, 'test_used_for_selection': False, 'promotion_ready': False})
    if selected:
        joblib.dump(bundles[selected], out / 'candidate.pkl', compress=3)
    assert sha256(app.MODEL_PATH) == baseline_hash
    print('Selection frozen: ' + str(selected), flush=True)


if __name__ == '__main__':
    main()
