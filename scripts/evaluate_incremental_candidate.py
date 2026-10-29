"""One post-selection test; never adjusts a chosen candidate to test labels."""
import argparse
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
import app
import joblib
import numpy as np
from train_host_context_candidate import read, reliability
from train_recovered_rf import feature_matrix, scores, subgroup_metrics, evaluate
from train_subdomain_fp_candidate import probes, improves
from model_registry import atomic_json, sha256


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('experiment', type=Path)
    parser.add_argument('--round', type=int, choices=[1,2], default=1)
    args = parser.parse_args(); out = args.experiment.resolve()
    assert out.parent == (ROOT / 'backend/data').resolve()
    design = json.loads((out / 'design.json').read_text(encoding='utf-8'))
    selection = json.loads((out / 'selection.json').read_text(encoding='utf-8'))
    assert selection['selected'], 'No validation-eligible candidate; do not inspect confirmation scores.'
    assert selection['test_used_for_selection'] is False
    assert sha256(app.MODEL_PATH) == design['baseline_sha256']
    candidate = joblib.load(out / 'candidate.pkl'); baseline = app.load_model_bundle()
    # Fix inherited display metadata, preserving learned tree/calibration state.
    candidate['probability_method'] = candidate['calibration']
    candidate['dataset_row_count'] = joblib.load(ROOT / 'backend/data/simple_host_context_20261008/augmented_v5.pkl')['dataset_row_count']
    joblib.dump(candidate, out / 'candidate.pkl', compress=3)
    confirmation = ROOT / ('backend/data/incremental-confirmation-round2-20261008' if args.round==2 else 'backend/data/incremental-confirmation-20261008')
    manifest = json.loads((confirmation / 'manifest.json').read_text(encoding='utf-8'))
    assert sha256(confirmation / 'dataset.csv') == manifest['csv_sha256']
    datasets = {
        'fresh_confirmation': read(confirmation / 'dataset.csv'),
        'historical_regression': [r for r in read(ROOT / 'backend/data/simple_recovered_query_structural_rf_20261005/dataset.csv') if r['split'] == 'holdout'],
        'prior_new_source_regression': [r for r in read(ROOT / 'backend/data/host-context-20261008/dataset.csv') if r['split'] == 'holdout'],
        'recent_phishing_regression': read(ROOT / 'backend/data/host-context-20261008/temporal-phishing-test.csv'),
    }
    if args.round==2:
        datasets['prior_confirmation_regression'] = read(ROOT / 'backend/data/incremental-confirmation-20261008/dataset.csv')
    result = {}
    for name, rows in datasets.items():
        print('Evaluating ' + name, flush=True)
        x = feature_matrix(rows, candidate['feature_schema_version'])
        old_x = x if baseline['feature_schema_version'] == candidate['feature_schema_version'] else feature_matrix(rows, baseline['feature_schema_version'])
        y = np.array([int(r['label']) for r in rows])
        old_p, new_p = scores(baseline, [], old_x), scores(candidate, [], x)
        metrics = {}
        for m, bundle, p in [('baseline', baseline, old_p), ('candidate', candidate, new_p)]:
            metrics[m] = {**evaluate(y, p, .6, .8), 'calibration': reliability(y, p)} if set(y) == {0, 1} else {
                k: subgroup_metrics(y, p, t) for k, t in [('warning', .6), ('blocking', .8)]}
        passed = improves(metrics['candidate'], metrics['baseline']) if set(y) == {0, 1} else all(
            metrics['candidate'][k]['true_positive'] >= metrics['baseline'][k]['true_positive'] for k in ('warning', 'blocking'))
        transitions = {}
        for k, t in [('warning', .6), ('blocking', .8)]:
            old, new = old_p >= t, new_p >= t
            transitions[k] = {'phishing_lost': int(((y == 1) & old & ~new).sum()),
                'phishing_gained': int(((y == 1) & ~old & new).sum()),
                'false_positives_removed': int(((y == 0) & old & ~new).sum()),
                'false_positives_added': int(((y == 0) & ~old & new).sum())}
        result[name] = {'rows': len(rows), 'domains': len({r['group'] for r in rows}),
            **metrics, 'paired_transitions': transitions, 'measured_gate_passed': passed}
        print(json.dumps({name: {m: metrics[m]['warning'] for m in ('baseline', 'candidate')} | {'passed': passed}}), flush=True)
    passed = all(r['measured_gate_passed'] for r in result.values())
    atomic_json(out / 'evaluation.json', {'evaluations': result, 'measured_gate_passed': passed,
        'statistical_gate_passed': False, 'promotion_ready': False, 'production_ready': False,
        'candidate_sha256': sha256(out / 'candidate.pkl'), 'baseline_sha256': design['baseline_sha256'],
        'selection_sha256': sha256(out / 'selection.json'), 'fresh_confirmation_sha256': manifest['csv_sha256'],
        'confirmation_used_for_selection': False, 'refit_on_test': False,
        'prior_exposure_audit_complete': False, 'forward_temporal_test': False,
        'probes': probes(candidate), 'limitations': manifest['limitations'],
        'scope': 'No net increase in misses/false positives on these finite sets; no guarantee for every future URL.'})
    assert sha256(app.MODEL_PATH) == design['baseline_sha256']


if __name__ == '__main__': main()
