"""Fresh RF fit with domain character features; select solely on development."""
import json
import sys
from pathlib import Path
from datetime import datetime, timezone
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
import app
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from feature_extractor import DOMAIN_LEXICAL_SCHEMA_VERSION, feature_names
from train_recovered_rf import feature_matrix, scores, evaluate
from train_host_context_candidate import read, reliability
from train_subdomain_fp_candidate import probes, improves
from model_registry import atomic_json, sha256

OUT = ROOT / 'backend/data/simple_domain_lexical_20261008'
SOURCE = ROOT / 'backend/data/simple_host_context_20261008/dataset.csv'


def metrics(y, p):
    m = evaluate(y, p, .6, .8); m['calibration'] = reliability(y, p)
    return m


def main():
    OUT.mkdir(exist_ok=False)
    base = app.load_model_bundle(); base_hash = sha256(app.MODEL_PATH)
    rows = read(SOURCE)
    parts = {s: [r for r in rows if r['split'] == s] for s in ('train', 'calibration', 'validation')}
    domains = {s: {r['group'] for r in part} for s, part in parts.items()}
    assert all(not domains[a] & domains[b] for a, b in [('train','calibration'),('train','validation'),('calibration','validation')])
    original = read(ROOT / 'backend/data/simple_recovered_query_structural_rf_20261005/dataset.csv')
    old_urls = {r['url'] for r in original if r['split'] in ('calibration', 'validation')}
    del original, rows
    atomic_json(OUT / 'design.json', {'created_at': datetime.now(timezone.utc).isoformat(),
        'baseline_sha256': base_hash, 'development_sha256': sha256(SOURCE),
        'schema': DOMAIN_LEXICAL_SCHEMA_VERSION, 'configs': ['baseline_capacity', 'lexical_capacity'],
        'calibration': ['combined', 'historical'], 'heldout_scores_used_for_selection': False,
        'selection': 'All validation strata lower warning FPR with no warning/block recall loss or block FPR increase; benign probes allow.',
        'prior_exposure_audit_complete': False, 'license': 'CC BY-NC 4.0'})
    x, y = {}, {}
    for split, part in parts.items():
        print('Extracting V7 ' + split, flush=True)
        x[split] = feature_matrix(part, DOMAIN_LEXICAL_SCHEMA_VERSION)
        y[split] = np.array([int(r['label']) for r in part])
    historic_cal = np.array([r['url'] in old_urls for r in parts['calibration']])
    historic_val = np.array([r['url'] in old_urls for r in parts['validation']])
    print('Scoring baseline validation', flush=True)
    bp = scores(base, parts['validation'])
    strata = {'all': np.ones(len(bp), dtype=bool), 'historical': historic_val, 'augmentation': ~historic_val}
    bm = {s: metrics(y['validation'][mask], bp[mask]) for s, mask in strata.items()}
    results, bundles, eligible = {}, {}, []
    for config, trees, depth, leaf in [('baseline_capacity',96,20,10), ('lexical_capacity',128,28,3)]:
        print('Training V7 ' + config, flush=True)
        forest = RandomForestClassifier(n_estimators=trees, max_depth=depth, min_samples_leaf=leaf,
            class_weight='balanced_subsample', random_state=20261008, n_jobs=4)
        forest.fit(x['train'], y['train'])
        raw_cal = forest.predict_proba(x['calibration'])[:, 1]
        raw_val = forest.predict_proba(x['validation'])[:, 1]
        for cal_set in ('combined', 'historical'):
            name = config + '_' + cal_set
            mask = np.ones(len(raw_cal), dtype=bool) if cal_set == 'combined' else historic_cal
            calibrator = LogisticRegression(C=1e6,max_iter=1000).fit(raw_cal[mask].reshape(-1,1),y['calibration'][mask])
            assert calibrator.coef_[0,0] > 0
            p = calibrator.predict_proba(raw_val.reshape(-1,1))[:,1]
            m = {s: metrics(y['validation'][mask],p[mask]) for s,mask in strata.items()}
            bundle = {**base, 'model':forest,'probability_calibrator':calibrator,
                'feature_schema_version':DOMAIN_LEXICAL_SCHEMA_VERSION,'feature_names':feature_names(DOMAIN_LEXICAL_SCHEMA_VERSION),
                'model_version':'url-risk-rf-domain-lexical-20261008-' + name,
                'trained_at':datetime.now(timezone.utc).isoformat(),'production_ready':False,'statistical_gate_passed':False,
                'probability_method':'heldout_platt_random_forest','calibration':'heldout_platt_random_forest',
                'calibration_version':'platt-domain-lexical-20261008-' + cal_set,
                'dataset_row_count':sum(len(part) for part in parts.values()),'metrics':{'validation':m['all']},
                'evaluation_design':{'prior_exposure_audit_complete':False,'forward_temporal_test':False},
                'training_provenance':{'feature_code_sha256':sha256(ROOT/'backend/feature_extractor.py'),
                    'dataset_sha256':sha256(SOURCE),'calibration_set':cal_set,'license':'CC BY-NC 4.0'}}
            checks = probes(bundle)
            passed = all(improves(m[s],bm[s]) for s in strata) and all(r['decision']=='allow' for r in checks)
            results[name]={'metrics':m,'probes':checks,'eligible':passed}; bundles[name]=bundle
            if passed: eligible.append(name)
            print(json.dumps({name:{'eligible':passed,'facebook':checks[0]['final_score'],'warning':m['all']['warning'],
                'historical_warning':m['historical']['warning'],'historical_blocking':m['historical']['blocking']}}),flush=True)
    selected = min(eligible,key=lambda n:results[n]['metrics']['all']['warning']['false_positive_rate']) if eligible else None
    atomic_json(OUT/'selection.json',{'selected':selected,'baseline_validation':bm,'candidates':results,
        'test_used_for_selection':False,'promotion_ready':False})
    if selected: joblib.dump(bundles[selected],OUT/'candidate.pkl',compress=3)
    assert sha256(app.MODEL_PATH)==base_hash
    print('Selection frozen: ' + str(selected),flush=True)


if __name__=='__main__': main()
