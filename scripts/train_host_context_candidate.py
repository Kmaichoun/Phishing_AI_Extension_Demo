"""RF-only retraining with publisher augmentation and frozen unseen-source test.

Never changes the active model. Preserves 60/80. All test evaluation happens
after development selection is frozen. Missing historical exposure stays unknown.
"""
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
import app
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from feature_extractor import HOST_CONTEXT_SCHEMA_VERSION, QUERY_ROBUST_SCHEMA_VERSION, feature_names
from train_recovered_rf import feature_matrix, scores, evaluate, subgroup_metrics
from model_registry import atomic_json, sha256
from train_subdomain_fp_candidate import probes, improves

OLD = ROOT / 'backend/data/simple_recovered_query_structural_rf_20261005/dataset.csv'
NEW = ROOT / 'backend/data/host-context-20261008'
OUT = ROOT / 'backend/data/simple_host_context_20261008'


def read(path):
    with path.open(encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def reliability(y, p):
    bins, ece = [], 0.0
    for lo in np.arange(0, 1, .1):
        mask = (p >= lo) & (p < lo + .1 if lo < .9 else p <= 1)
        if mask.any():
            predicted, actual = float(p[mask].mean()), float(y[mask].mean())
            ece += mask.mean() * abs(predicted - actual)
            bins.append({'lower': round(float(lo), 1), 'rows': int(mask.sum()),
                         'mean_prediction': predicted, 'phishing_fraction': actual})
    return {'expected_calibration_error_10_bins': float(ece), 'bins': bins,
            'limitation': 'Calibration depends on sampled class prevalence; not a per-URL safety guarantee.'}


def summarize(bundle, rows, matrix=None):
    y = np.array([int(r['label']) for r in rows])
    p = scores(bundle, rows, matrix)
    metrics = evaluate(y, p, .6, .8)
    metrics['calibration'] = reliability(y, p)
    groups = {}
    for name, mask in [('subdomain', np.array([urlsplit(r['url']).hostname.count('.') > r['group'].count('.') for r in rows])),
                       ('query', np.array([bool(urlsplit(r['url']).query) for r in rows])),
                       ('new_source', np.array([r['source'].startswith('deepurlbench') for r in rows]))]:
        if mask.any():
            groups[name] = subgroup_metrics(y[mask], p[mask], .6)
    metrics['subgroups'] = groups
    return metrics


def main():
    OUT.mkdir(exist_ok=False)
    baseline = app.load_model_bundle(); baseline_hash = sha256(app.MODEL_PATH)
    manifest = json.loads((NEW / 'manifest.json').read_text(encoding='utf-8'))
    assert sha256(NEW / 'dataset.csv') == manifest['csv_sha256']
    prior = read(OLD); incoming = read(NEW / 'dataset.csv')
    reference_manifest = json.loads((NEW / 'official-references.manifest.json').read_text(encoding='utf-8'))
    assert sha256(NEW / 'official-references.csv') == reference_manifest['csv_sha256']
    incoming += read(NEW / 'official-references.csv')
    old_splits = {r['group']: r['split'] for r in prior}
    dev = [r for r in prior if r['split'] != 'holdout']
    old_test = [r for r in prior if r['split'] == 'holdout']
    fresh_test = [r for r in incoming if r['split'] == 'holdout']
    seen = {r['url'] for r in prior}
    added = Counter()
    for row in incoming:
        if row['split'] == 'holdout' or row['url'] in seen or old_splits.get(row['group']) == 'holdout':
            continue
        # Keep references on an existing registered-domain partition. Exclude
        # reference rows whose domains belong to publisher test partitions.
        if row['source'].startswith('official_reference') and row['group'] not in old_splits:
            continue
        row['split'] = old_splits.get(row['group'], row['split'])
        dev.append(row); seen.add(row['url']); added[row['split']] += 1
    partitions = {s: [r for r in dev if r['split'] == s] for s in ('train', 'calibration', 'validation')}
    group_sets = {s: {r['group'] for r in rows} for s, rows in partitions.items()}
    group_sets.update({'old_test': {r['group'] for r in old_test}, 'fresh_test': {r['group'] for r in fresh_test}})
    keys = list(group_sets)
    assert all(not group_sets[a] & group_sets[b] for i, a in enumerate(keys) for b in keys[i+1:])
    print(json.dumps({'augmentation': dict(added), 'split_counts': {s: len(r) for s, r in partitions.items()},
                      'fresh_test_rows': len(fresh_test), 'all_registered_domain_overlaps': 0}), flush=True)
    with (OUT / 'dataset.csv').open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(dev[0]), extrasaction='ignore'); writer.writeheader(); writer.writerows(dev)
    # Persist test separately. Neither labels nor scores are used for selection.
    vx_old = feature_matrix(partitions['validation'], QUERY_ROBUST_SCHEMA_VERSION)
    old_validation = summarize(baseline, partitions['validation'], vx_old)
    results, bundles = {}, {}
    for name, schema in [('augmented_v5', QUERY_ROBUST_SCHEMA_VERSION), ('host_context_v6', HOST_CONTEXT_SCHEMA_VERSION)]:
        print('Extracting/training ' + name, flush=True)
        matrices = {s: feature_matrix(rows, schema) for s, rows in partitions.items()}
        labels = {s: np.array([int(r['label']) for r in rows]) for s, rows in partitions.items()}
        weights = np.array([1.5 if r['label'] == '0' and
            (urlsplit(r['url']).query or (urlsplit(r['url']).hostname or '').count('.') > r['group'].count('.')) else 1.0
            for r in partitions['train']])
        forest = RandomForestClassifier(n_estimators=128, max_depth=28, min_samples_leaf=3,
            class_weight='balanced_subsample', random_state=20261008, n_jobs=4)
        forest.fit(matrices['train'], labels['train'], sample_weight=weights)
        raw = forest.predict_proba(matrices['calibration'])[:, list(forest.classes_).index(1)]
        calibrator = LogisticRegression(C=1e6, max_iter=1000).fit(raw.reshape(-1, 1), labels['calibration'])
        assert calibrator.coef_[0, 0] > 0
        bundle = {**baseline, 'model': forest, 'probability_calibrator': calibrator,
            'feature_schema_version': schema, 'feature_names': feature_names(schema),
            'model_version': 'url-risk-rf-' + name + '-20261008',
            'trained_at': datetime.now(timezone.utc).isoformat(), 'metrics': {}, 'production_ready': False,
            'dataset_row_count': len(dev), 'calibration_version': 'platt-disjoint-domains-20261008',
            'evaluation_design': {'fresh_source_test': True, 'forward_temporal_test': False,
                'prior_exposure_audit_complete': False},
            'training_provenance': {'new_data_manifest': str(NEW / 'manifest.json'), 'license': 'CC BY-NC 4.0'}}
        new_validation = summarize(bundle, partitions['validation'], matrices['validation'])
        regression = probes(bundle)
        eligible = improves(new_validation, old_validation) and all(r['decision'] == 'allow' for r in regression)
        importance = sorted(zip(feature_names(schema), forest.feature_importances_), key=lambda t: -t[1])
        results[name] = {'validation': new_validation, 'probes': regression, 'eligible': eligible,
                         'feature_importance': [{ 'feature': k, 'importance': float(v)} for k, v in importance]}
        bundle['metrics']['validation'] = new_validation
        joblib.dump(bundle, OUT / (name + '.pkl'), compress=3); bundles[name] = bundle
        print(json.dumps({name: {'warning': new_validation['warning'], 'blocking': new_validation['blocking'],
                               'probes': regression, 'eligible': eligible}}), flush=True)
        del matrices
    eligible = [name for name in results if results[name]['eligible']]
    # When no candidate passes, one research-only candidate is frozen for a
    # diagnostic test. It cannot become eligible based on test results.
    selected = min(eligible or list(results), key=lambda n: results[n]['validation']['warning']['false_positive_rate'])
    atomic_json(OUT / 'selection.json', {'baseline_sha256': baseline_hash, 'old_dataset_sha256': sha256(OLD),
        'new_dataset_sha256': manifest['csv_sha256'], 'selected': selected,
        'validation_passed': bool(eligible), 'holdout_used_for_selection': False,
        'baseline_validation': old_validation, 'candidates': results,
        'rule': 'Lower warning FPR; no warning/block recall loss; no block FPR increase; all benign probes allow.'})
    candidate = bundles[selected]
    print('Selection frozen; evaluating fresh-source test once.', flush=True)
    evaluation = {}
    for name, rows in [('new_source_domain_disjoint', fresh_test), ('historical_reused', old_test)]:
        if set(r['label'] for r in rows) != {'0', '1'}:
            raise ValueError('Both labels required for evaluation')
        old_metrics = summarize(baseline, rows)
        new_metrics = summarize(candidate, rows)
        evaluation[name] = {'rows': len(rows), 'domains': len({r['group'] for r in rows}),
            'label_counts': dict(Counter(r['label'] for r in rows)), 'baseline': old_metrics,
            'candidate': new_metrics, 'better': improves(new_metrics, old_metrics)}
        print(json.dumps({name: {'baseline': old_metrics['warning'], 'candidate': new_metrics['warning'],
                                'better': evaluation[name]['better']}}), flush=True)
    statistical_pass = bool(eligible) and all(r['better'] for r in evaluation.values())
    candidate['metrics'].update({'new_source_test': evaluation['new_source_domain_disjoint']['candidate'],
                                'reused_benchmark': evaluation['historical_reused']['candidate']})
    candidate['statistical_gate_passed'] = statistical_pass
    candidate['prior_exposure_audit_complete'] = False
    joblib.dump(candidate, OUT / 'candidate.pkl', compress=3)
    atomic_json(OUT / 'evaluation.json', {'selected': selected, 'evaluations': evaluation,
        'statistical_gate_passed': statistical_pass, 'promotion_ready': False, 'production_ready': False,
        'prior_exposure_audit_complete': False, 'forward_temporal_test': False,
        'missing_original_training_file': 'backend/data/training_urls.csv',
        'candidate_sha256': sha256(OUT / 'candidate.pkl'), 'baseline_sha256': baseline_hash,
        'test_read_after_selection': True, 'refit_on_test': False,
        'limitations': manifest['limitations']})
    assert sha256(app.MODEL_PATH) == baseline_hash
    print('Finished; operating model unchanged.', flush=True)


if __name__ == '__main__':
    main()
