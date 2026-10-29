"""Error audit and conservative, learned RF-leaf refinement. No test scoring.

The baseline tree backbone is retained. Development training fits small trees
inside its leaves. Half of calibration domains guard against benign branches
containing phishing; the other half alone fits the probability calibrator.
Validation selects a fixed, predeclared search, with all source gates retained.
"""
import argparse
import copy
import csv
import hashlib
import json
import sys
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
import app
import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from feature_extractor import DOMAIN_ENRICHED_SCHEMA_VERSION as SCHEMA, REFERENCE_ORIGIN_SCHEMA_VERSION, feature_names, feature_vector, normalize_url
from reference_origin_features import reference_origin_match, registry
from forest_feature_adapter import extend_forest
from forest_leaf_refinement import learn_regions, refine_estimator
from probability_calibration import ValidationConstrainedSigmoidCalibrator
from model_registry import atomic_json, sha256
from train_enriched_forest_candidate import metrics
from train_quality_rf_candidate import no_regression
from train_subdomain_fp_candidate import PROBES, improves

SOURCE = ROOT / 'backend/data/simple_quality_rf_20261008'
OUT = ROOT / 'backend/data/simple_selective_refinement_rf_20261008'
CONFIGS = [{'name': f'depth{d}_support{n}', 'depth': d, 'support': n}
           for d, n in [(2, 8), (3, 8), (4, 8), (2, 16), (3, 16), (4, 32)]]
URL_PROBES = list(dict.fromkeys(PROBES + ['https://web.facebook.com/?locale=th_TH&_rdc=1&_rdr#',
                                        'https://gemini.google.com/?hl=th', 'https://gemini.google.com/']))


def probe_scores(bundle):
    x = np.asarray([feature_vector(u, SCHEMA) for u in URL_PROBES], dtype=np.float32)
    raw = bundle['model'].predict_proba(x)[:, 1]
    p = bundle['probability_calibrator'].predict_proba(raw.reshape(-1, 1))[:, 1]
    return [{'url': u, 'final_score': round(float(v * 100)), 'decision': 'block' if v >= .8 else 'warn' if v >= .6 else 'allow'}
            for u, v in zip(URL_PROBES, p)]


def strata_for(source, y):
    strata = {'all': np.ones(len(y), dtype=bool)}
    for name, prefix in [('historical', 'phreshphish'), ('historical_urlphish', 'urlphish'),
                         ('deepurlbench', 'deepurlbench'), ('uci', 'uci_')]:
        mask = np.char.startswith(source, prefix)
        if set(y[mask]) == {0, 1}: strata[name] = mask
    return strata


def audit(val_rows, y, baseline_raw, baseline_p, cal_raw, cal_y, cal_sources, x):
    donor = joblib.load(SOURCE / 'context-forest.pkl'); donor.verbose = 0
    raw = {}
    for s, old in [('calibration', cal_raw), ('validation', baseline_raw)]:
        raw[s] = (old * 96 + donor.predict_proba(x[s])[:, 1] * 64) / 160
    historical = np.char.startswith(cal_sources, 'phreshphish') | np.char.startswith(cal_sources, 'urlphish')
    calibrator = LogisticRegression(C=1e6, max_iter=1000).fit(raw['calibration'][historical].reshape(-1, 1), cal_y[historical])
    p = calibrator.predict_proba(raw['validation'].reshape(-1, 1))[:, 1]
    summary = {}
    with (OUT / 'paired-error-review.csv').open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['url', 'publisher_label', 'source', 'group', 'baseline_score', 'previous_candidate_score',
                    'warning_transition', 'blocking_transition', 'label_review_status'])
        for i, row in enumerate(val_rows):
            transitions = []
            for name, cutoff in [('warning', .6), ('blocking', .8)]:
                old, new = baseline_p[i] >= cutoff, p[i] >= cutoff
                transition = ('phishing_lost' if old and not new else 'phishing_gained') if y[i] else (
                    'false_positive_removed' if old and not new else 'false_positive_added')
                transitions.append(transition if old != new else '')
                if old != new:
                    summary.setdefault(row['source'], Counter())[name + '_' + transition] += 1
            if any(transitions):
                w.writerow([row['url'], int(y[i]), row['source'], row['group'], float(baseline_p[i] * 100),
                            float(p[i] * 100), *transitions, 'publisher label; not independently adjudicated'])
    atomic_json(OUT / 'error-audit.json', {'source_transitions': {k: dict(v) for k, v in summary.items()},
        'audited_candidate': 'context_pooled_64_platt_historical', 'labels_manually_changed': 0,
        'validation_is_reused_development': True, 'test_scores_read': False,
        'note': 'URLs are reviewed offline; no phishing destinations fetched. Aggregate misses can hide paired lost/gained.'})


def main():
    global SCHEMA, OUT, CONFIGS
    parser = argparse.ArgumentParser(); parser.add_argument('--resume', action='store_true')
    parser.add_argument('--reference-origin', action='store_true')
    args = parser.parse_args()
    if args.reference_origin:
        SCHEMA = REFERENCE_ORIGIN_SCHEMA_VERSION
        OUT = ROOT / 'backend/data/simple_reference_refinement_rf_20261008'
        CONFIGS = [{'name': f'depth{d}_support{n}', 'depth': d, 'support': n} for d, n in [(2,8), (4,8), (4,32)]]
    OUT.mkdir(exist_ok=args.resume)
    (OUT / 'checkpoints').mkdir(exist_ok=True)
    base = app.load_model_bundle(); base['model'].verbose = 0
    parent = json.loads((SOURCE / 'design.json').read_text(encoding='utf-8'))
    assert sha256(app.MODEL_PATH) == parent['baseline_sha256']
    assert sha256(SOURCE / 'dataset.csv') == parent['development_sha256']
    cache_manifest = json.loads((ROOT / 'backend/data/feature_cache_domain_enriched_20261008/manifest.json').read_text(encoding='utf-8'))
    current_feature_hash = sha256(ROOT / 'backend/feature_extractor.py')
    backup = ROOT / 'output/before-reference-origin-20261008/feature_extractor.py'
    assert cache_manifest['feature_code_sha256'] == current_feature_hash or (
        backup.is_file() and cache_manifest['feature_code_sha256'] == sha256(backup))
    design = {**parent, 'created_at': datetime.now(timezone.utc).isoformat(), 'method': 'experimental selective RF terminal-node refinement',
        'feature_code_sha256': sha256(ROOT / 'backend/feature_extractor.py'),
        'refinement_code_sha256': sha256(ROOT / 'backend/forest_leaf_refinement.py'),
        'configs': CONFIGS, 'probability_methods': ['platt', 'validation_constrained_sigmoid'],
        'calibration_split': 'registered-domain SHA256 parity: even=positive guard; odd=probability calibration',
        'region_fit': {'max_depth': 4, 'min_samples_leaf': 4, 'class_weight': 'balanced', 'minimum_old_leaf_probability': .35,
                       'minimum_train_observations': 16, 'minimum_training_false_positives': 2},
        'leaf_probability': 'Laplace (phishing_count+1)/(observations+2), only pure benign leaves; remaining descendants original probability',
        'test_used_for_selection': False, 'validation_used_for_selection': True,
        'selection': 'Lower aggregate warning FPR; no warning/block FP/FN increase per source; all probes allow; no URL/domain overrides.'}
    design['schema'] = SCHEMA
    design['cached_prefix_feature_code_sha256'] = cache_manifest['feature_code_sha256']
    if args.reference_origin:
        design['reference_origin_registry_sha256'] = registry()[1]
        design['reference_origin_meaning'] = 'Exact publisher-reference origin presence is a model feature, not a benign label or decision override.'
    if args.resume:
        saved = json.loads((OUT / 'design.json').read_text(encoding='utf-8'))
        for k in ('baseline_sha256', 'development_sha256', 'feature_code_sha256', 'refinement_code_sha256', 'configs'):
            assert saved[k] == design[k]
        assert not (OUT / 'confirmation-lock.json').exists()
    else: atomic_json(OUT / 'design.json', design)
    labels, sources, guards, val_rows = {s: [] for s in ('train', 'calibration', 'validation')}, {s: [] for s in ('train', 'calibration', 'validation')}, [], []
    origin_flags, prefix_check = {s: [] for s in labels}, {s: [] for s in labels}
    groups = {s: set() for s in labels}
    probe_groups = {}
    with (SOURCE / 'dataset.csv').open(encoding='utf-8', newline='') as f:
        for row in csv.DictReader(f):
            s = row['split']; labels[s].append(int(row['label'])); sources[s].append(row['source']); groups[s].add(row['group'])
            if len(prefix_check[s]) < 100: prefix_check[s].append(row['url'])
            if args.reference_origin: origin_flags[s].append(reference_origin_match(normalize_url(row['url'])))
            if s == 'validation': val_rows.append(row)
            if s == 'calibration':
                guards.append(int.from_bytes(hashlib.sha256(('refinement-guard-20261008|' + row['group']).encode()).digest()[:4], 'big') % 2 == 0)
            if row['group'] in ('facebook.com', 'google.com'):
                probe_groups.setdefault(row['group'], Counter())[s + '|label=' + row['label']] += 1
    assert all(not groups[a] & groups[b] for a, b in [('train','calibration'), ('train','validation'), ('calibration','validation')])
    y = {s: np.asarray(v, dtype=np.int8) for s, v in labels.items()}
    src = {s: np.asarray(v, dtype='U100') for s, v in sources.items()}
    del labels, sources, groups
    original_x = {s: np.load(SOURCE / (s + '.npy'), mmap_mode='r') for s in y}
    for s in y:
        check = np.asarray([feature_vector(u, 'url-v8-domain-enriched') for u in prefix_check[s]], dtype=np.float32)
        np.testing.assert_array_equal(check, original_x[s][:len(check)])
    x = original_x
    if args.reference_origin:
        x = {}
        prefix_width = len(feature_names('url-v8-domain-enriched'))
        assert feature_names(SCHEMA)[:prefix_width] == feature_names('url-v8-domain-enriched')
        for s in y:
            path = OUT / (s + '.npy')
            if not path.exists():
                new = np.lib.format.open_memmap(path, mode='w+', dtype=np.float32, shape=(len(y[s]),len(feature_names(SCHEMA))))
                new[:,:prefix_width] = original_x[s]; new[:,prefix_width] = np.asarray(origin_flags[s],dtype=np.float32); new.flush(); del new
            x[s] = np.load(path,mmap_mode='r')
            full_check = np.asarray([feature_vector(u, SCHEMA) for u in prefix_check[s]], dtype=np.float32)
            np.testing.assert_array_equal(full_check, x[s][:len(full_check)])
    del origin_flags, prefix_check
    assert all(x[s].shape == (len(y[s]), len(feature_names(SCHEMA))) for s in y)
    oldraw = {}
    for s in y:
        path = OUT / ('baseline-' + s + '.npy')
        if not path.exists(): np.save(path, base['model'].predict_proba(x[s][:, :32])[:, 1])
        oldraw[s] = np.load(path)
    bp = base['probability_calibrator'].predict_proba(oldraw['validation'].reshape(-1,1))[:,1]
    strata = strata_for(src['validation'], y['validation'])
    bm = {s: metrics(y['validation'][m], bp[m]) for s, m in strata.items()}
    if not (OUT / 'error-audit.json').exists():
        if args.reference_origin:
            for filename in ('error-audit.json','paired-error-review.csv'):
                shutil.copyfile(ROOT/'backend/data/simple_selective_refinement_rf_20261008'/filename,OUT/filename)
        else: audit(val_rows, y['validation'], oldraw['validation'], bp, oldraw['calibration'], y['calibration'], src['calibration'], original_x)
    del val_rows
    guard = np.asarray(guards, dtype=bool)
    guard_x, guard_y = x['calibration'][guard], y['calibration'][guard]
    atomic_json(OUT / 'partition-audit.json', {'counts': {s: len(v) for s, v in y.items()},
        'guard_rows': int(guard.sum()), 'probability_calibration_rows': int((~guard).sum()),
        'target_domain_counts': {k: dict(v) for k, v in probe_groups.items()},
        'registered_domain_disjoint': True, 'all_target_examples_are_development_probes': True})
    train_p = base['probability_calibrator'].predict_proba(oldraw['train'].reshape(-1,1))[:,1]
    hard = (y['train'] == 0) & (train_p >= .6)
    adapted = extend_forest(base['model'], base['feature_names'], feature_names(SCHEMA))
    for i, est in enumerate(adapted.estimators_):
        path = OUT / 'checkpoints' / f'tree-{i:03}.pkl'
        if path.exists(): continue
        regions = learn_regions(est, x['train'], y['train'], hard, guard_x, guard_y, 20261010 + i)
        joblib.dump(regions, path, compress=3)
        atomic_json(OUT / 'training-progress.json', {'trees_done': i+1, 'trees_total': len(adapted.estimators_),
                                                    'latest_learned_regions': len(regions), 'test_scores_read': False})
        print(json.dumps({'tree': i+1, 'of': len(adapted.estimators_), 'regions': len(regions)}), flush=True)
    from diagnose_quality_calibration import bounds, separated_intervals
    results, eligible = {}, []
    for config in CONFIGS:
        forest = copy.copy(adapted); forest.estimators_ = []; changes = 0
        for i, est in enumerate(adapted.estimators_):
            regions = joblib.load(OUT / 'checkpoints' / f'tree-{i:03}.pkl')
            refined, n = refine_estimator(est, regions, config['depth'], config['support'])
            forest.estimators_.append(refined); changes += n
        forest.verbose = 0
        joblib.dump(forest, OUT / (config['name'] + '-forest.pkl'), compress=3)
        raw = {s: forest.predict_proba(x[s])[:,1] for s in ('calibration','validation')}
        for s in raw:
            assert np.all(raw[s] <= oldraw[s] + 1e-12), 'Raw predictions must not increase under benign-only refinement'
        wl, wu, wlimits = bounds(raw['validation'], y['validation'], bp, strata, .6, True)
        bl, bu, blimits = bounds(raw['validation'], y['validation'], bp, strata, .8, False)
        intervals = separated_intervals(wl, wu, bl, bu)
        fitted = {'platt': LogisticRegression(C=1e6, max_iter=1000).fit(raw['calibration'][~guard].reshape(-1,1), y['calibration'][~guard])}
        if intervals:
            fitted['validation_constrained_sigmoid'] = ValidationConstrainedSigmoidCalibrator(*intervals).fit(
                raw['calibration'][~guard].reshape(-1,1), y['calibration'][~guard])
        atomic_json(OUT / (config['name'] + '-ranking.json'), {'warning_interval': [wl,wu], 'blocking_interval': [bl,bu],
            'warning_strata': wlimits, 'blocking_strata': blimits, 'monotonic_calibration_feasible': bool(intervals),
            'modified_terminal_nodes': changes})
        for method, calibrator in fitted.items():
            p = calibrator.predict_proba(raw['validation'].reshape(-1,1))[:,1]
            m = {s: metrics(y['validation'][mask],p[mask]) for s,mask in strata.items()}
            name = config['name'] + '_' + method
            bundle = {**base, 'model': forest, 'probability_calibrator': calibrator, 'feature_names': feature_names(SCHEMA),
                'feature_schema_version': SCHEMA, 'model_version': 'url-risk-rf-selective-refinement-' + name + '-20261008',
                'trained_at': datetime.now(timezone.utc).isoformat(), 'calibration': method + '_refined_rf',
                'probability_method': method + '_refined_rf', 'calibration_version': 'selective-refinement-' + method + '-20261008',
                'production_ready': False, 'statistical_gate_passed': False, 'metrics': {'development_selection': m['all']},
                'dataset_row_count': sum(len(v) for v in y.values()),
                'evaluation_design': {'prior_exposure_audit_complete': False, 'forward_temporal_test': False,
                                      'test_used_for_selection': False, 'validation_used_for_tuning': method != 'platt'},
                'training_provenance': {'design_sha256': sha256(OUT/'design.json'), 'method': design['method'],
                                        'config': config, 'license': 'Includes CC BY-NC 4.0 DeepURLBench'}}
            if args.reference_origin: bundle['reference_origin_registry_sha256'] = registry()[1]
            checks = probe_scores(bundle)
            passed = improves(m['all'],bm['all']) and all(no_regression(m[s],bm[s]) for s in strata) and all(r['decision']=='allow' for r in checks)
            results[name] = {'metrics':m, 'probes':checks, 'eligible':passed, 'modified_terminal_nodes': changes}
            joblib.dump(bundle, OUT / (name + '.pkl'), compress=3)
            if passed: eligible.append(name)
            atomic_json(OUT / 'development-progress.json', {'baseline_validation': bm, 'candidates': results})
            print(json.dumps({name: {'eligible':passed, 'probes':checks, 'warning':m['all']['warning']}}), flush=True)
    selected = min(eligible, key=lambda n: results[n]['metrics']['all']['warning']['false_positive_rate']) if eligible else None
    atomic_json(OUT / 'selection.json', {'selected':selected, 'baseline_validation':bm, 'candidates':results,
        'test_used_for_selection':False, 'promotion_ready':False})
    if selected: (OUT / 'candidate.pkl').write_bytes((OUT / (selected + '.pkl')).read_bytes())
    assert sha256(app.MODEL_PATH) == design['baseline_sha256']
    print('Selection frozen: ' + str(selected), flush=True)


if __name__ == '__main__': main()
