"""Post-selection diagnostic of the previously trained V5 ablation.

These datasets have already been inspected for V6 and are regression sets now,
not untouched evidence for choosing another model. Never activates a model.
"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
import app
import joblib
import numpy as np
from train_host_context_candidate import read, summarize
from train_recovered_rf import feature_matrix, scores, subgroup_metrics
from train_subdomain_fp_candidate import probes, improves
from model_registry import atomic_json, sha256


def main():
    out = ROOT / 'backend/data/simple_host_context_20261008'
    baseline = app.load_model_bundle()
    active_hash = sha256(app.MODEL_PATH)
    candidate = joblib.load(out / 'augmented_v5.pkl')
    tests = {
        'historical_reused': [r for r in read(ROOT / 'backend/data/simple_recovered_query_structural_rf_20261005/dataset.csv') if r['split'] == 'holdout'],
        'new_source_previously_read': [r for r in read(ROOT / 'backend/data/host-context-20261008/dataset.csv') if r['split'] == 'holdout'],
        'recent_phishing_previously_read': read(ROOT / 'backend/data/host-context-20261008/temporal-phishing-test.csv'),
    }
    results = {}
    for name, rows in tests.items():
        print('Evaluating ' + name, flush=True)
        x = feature_matrix(rows, candidate['feature_schema_version'])
        if name.startswith('recent'):
            y = np.ones(len(rows), dtype=np.int8)
            results[name] = {m: {k: subgroup_metrics(y, scores(b, [], x), t)
                for k, t in [('warning', .6), ('blocking', .8)]}
                for m, b in [('baseline', baseline), ('candidate', candidate)]}
        else:
            results[name] = {'baseline': summarize(baseline, rows, x), 'candidate': summarize(candidate, rows, x)}
            results[name]['better'] = improves(results[name]['candidate'], results[name]['baseline'])
        print({name: {m: results[name][m]['warning'] for m in ('baseline', 'candidate')}}, flush=True)
    atomic_json(out / 'augmented-v5-diagnostic.json', {
        'results': results, 'probes': probes(candidate), 'candidate_sha256': sha256(out / 'augmented_v5.pkl'),
        'baseline_sha256': active_hash, 'test_used_for_selection': False,
        'independent_confirmation': False, 'promotion_ready': False,
        'limitation': 'Previously inspected datasets; diagnostic only. No tuning or activation in this script.'})
    assert sha256(app.MODEL_PATH) == active_hash


if __name__ == '__main__':
    main()
