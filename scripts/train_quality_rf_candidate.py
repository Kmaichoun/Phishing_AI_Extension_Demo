"""New-source, exact-conflict-cleaned RF development; tests stay unopened."""
import copy
import csv
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
import app
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from feature_extractor import DOMAIN_ENRICHED_SCHEMA_VERSION as SCHEMA, feature_names
from forest_feature_adapter import extend_forest
from probability_calibration import BetaProbabilityCalibrator
from train_recovered_rf import feature_matrix, scores
from train_host_context_candidate import read
from train_enriched_forest_candidate import metrics
from train_subdomain_fp_candidate import probes, improves
from collect_quality_url_data import canonical
from model_registry import atomic_json, sha256

INCOMING = ROOT / 'backend/data/quality-augmentation-20261008'
REFERENCES = ROOT / 'backend/data/quality-official-references-20261008'
OUT = ROOT / 'backend/data/simple_quality_rf_20261008'
CACHE = ROOT / 'backend/data/feature_cache_domain_enriched_20261008'
OLD = ROOT / 'backend/data/simple_host_context_20261008/dataset.csv'


def no_regression(new, old):
    return all(new[k]['false_positive'] <= old[k]['false_positive']
               and new[k]['false_negative'] <= old[k]['false_negative'] for k in ('warning','blocking'))


def prepare():
    manifest = json.loads((INCOMING / 'manifest.json').read_text(encoding='utf-8'))
    assert sha256(INCOMING / 'dataset.csv') == manifest['dataset_sha256']
    refs_manifest = json.loads((REFERENCES / 'manifest.json').read_text(encoding='utf-8'))
    assert sha256(REFERENCES / 'references.csv') == refs_manifest['csv_sha256']
    rows = read(INCOMING / 'dataset.csv')
    partitions = {r['group']: r['split'] for r in rows}
    blocked = {r['group'] for r in read(INCOMING / 'confirmation.csv')}
    test_paths = ['simple_recovered_query_structural_rf_20261005/dataset.csv',
                  'host-context-20261008/dataset.csv', 'host-context-20261008/temporal-phishing-test.csv',
                  'incremental-confirmation-20261008/dataset.csv', 'incremental-confirmation-round2-20261008/dataset.csv']
    for path in test_paths:
        blocked.update(r['group'] for r in read(ROOT / 'backend/data' / path)
                       if path not in ('simple_recovered_query_structural_rf_20261005/dataset.csv','host-context-20261008/dataset.csv')
                       or r.get('split') == 'holdout')
    assert not blocked & set(partitions)
    identity = {}
    for r in rows: identity.setdefault(canonical(r['url']), set()).add(r['label'])
    extra, conflicts, exclusions = [], set(), Counter()
    for r in read(REFERENCES / 'references.csv'):
        key = canonical(r['url'])
        if key in identity and identity[key] != {r['label']}:
            conflicts.add(key); continue
        if key in identity:
            exclusions['duplicate'] += 1; continue
        if r['group'] in blocked:
            exclusions['evaluation_domain'] += 1; continue
        bucket = int.from_bytes(hashlib.sha256(('quality-reference-20261008|' + r['group']).encode()).digest()[:4], 'big') % 10
        r['split'] = partitions.get(r['group'], 'train' if bucket < 7 else 'calibration' if bucket == 7 else 'validation')
        partitions[r['group']] = r['split']
        extra.append(r); identity[key] = {r['label']}
    rows = [r for r in rows if canonical(r['url']) not in conflicts] + extra
    for key in conflicts: extra = [r for r in extra if canonical(r['url']) != key]
    rows = [r for r in rows if canonical(r['url']) not in conflicts]
    with (OUT / 'dataset.csv').open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['url','label','source','group','split','observed_at','time_precision','label_evidence'], extrasaction='ignore')
        w.writeheader(); w.writerows(rows)
    atomic_json(OUT / 'reference-audit.json', {'included': len(extra), 'conflicting_exact_urls': sorted(conflicts),
        'excluded': dict(exclusions), 'reference_sha256': refs_manifest['csv_sha256'],
        'action': 'Conflicting exact URL labels quarantined; no whole-domain label corrections'})
    parts = {s: [r for r in rows if r['split'] == s] for s in ('train','calibration','validation')}
    groups = {s: {r['group'] for r in part} for s, part in parts.items()}
    assert all(not groups[a] & groups[b] for i,a in enumerate(groups) for b in list(groups)[i+1:])
    assert not set().union(*groups.values()) & blocked
    return parts, manifest


def matrices(parts):
    expected = {'dataset_sha256': sha256(OLD), 'feature_code_sha256': sha256(ROOT / 'backend/feature_extractor.py'), 'schema': SCHEMA}
    assert json.loads((CACHE / 'manifest.json').read_text(encoding='utf-8')) == expected
    original = read(OLD)
    old_parts = {s: [r for r in original if r['split'] == s] for s in parts}
    x = {}
    for s, part in parts.items():
        lookup = {(r['url'], r['label']): i for i,r in enumerate(old_parts[s])}
        cached = np.load(CACHE / (s + '.npy'), mmap_mode='r')
        mat = np.empty((len(part), len(feature_names(SCHEMA))), dtype=np.float32)
        added, indices = [], []
        for i, r in enumerate(part):
            index = lookup.get((r['url'],r['label']))
            if index is not None: mat[i] = cached[index]
            else: added.append(r); indices.append(i)
        print(json.dumps({'feature_split':s,'cached':len(part)-len(added),'new':len(added)}), flush=True)
        if added: mat[indices] = feature_matrix(added, SCHEMA)
        np.save(OUT / (s + '.npy'), mat)
        x[s] = mat
    return x


def main():
    OUT.mkdir(exist_ok=False)
    base = app.load_model_bundle(); baseline_hash = sha256(app.MODEL_PATH)
    parts, manifest = prepare()
    design = {'created_at':datetime.now(timezone.utc).isoformat(), 'baseline_sha256':baseline_hash,
        'development_sha256':sha256(OUT/'dataset.csv'), 'schema':SCHEMA, 'thresholds':{'warning':60,'blocking':80},
        'new_source_manifest_sha256':sha256(INCOMING/'manifest.json'), 'confirmation_sha256':manifest['confirmation_sha256'],
        'configs':[{'name':'context','trees':64,'depth':24,'leaf':6,'max_features':.5,'max_samples':.6},
                   {'name':'full_features','trees':64,'depth':24,'leaf':6,'max_features':1.,'max_samples':.6}],
        'calibration_methods':['platt_combined','platt_historical','beta_combined'],
        'forest_variants':['new_64','pooled_32','pooled_64'],
        'train_weight_policy':'UCI x2, official references x4; baseline training errors x2; all classes',
        'validation_used_for_selection':True, 'test_used_for_selection':False,
        'prior_exposure_audit_complete':False, 'forward_temporal_test':False,
        'source_licenses':{'UCI PhiUSIIL':'CC BY 4.0','DeepURLBench':'CC BY-NC 4.0'},
        'selection':'Aggregate warning FPR strictly lower; every both-class source stratum has no warning/block false-positive or miss increase; benign probes allow.'}
    atomic_json(OUT/'design.json', design)
    print(json.dumps({'split_counts':{s:len(p) for s,p in parts.items()}}), flush=True)
    x = matrices(parts); y = {s:np.array([int(r['label']) for r in p]) for s,p in parts.items()}
    baseline_raw = {s:base['model'].predict_proba(x[s][:,:32])[:,1] for s in parts}
    bp = {s:base['probability_calibrator'].predict_proba(baseline_raw[s].reshape(-1,1))[:,1] for s in parts}
    strata = {'all':np.ones(len(parts['validation']), dtype=bool)}
    for name, prefix in [('historical','phreshphish'),('historical_urlphish','urlphish'),('deepurlbench','deepurlbench'),('uci','uci_')]:
        mask = np.array([r['source'].startswith(prefix) for r in parts['validation']])
        if set(y['validation'][mask]) == {0,1}: strata[name] = mask
    bm = {s:metrics(y['validation'][mask], bp['validation'][mask]) for s,mask in strata.items()}
    source_weights = np.array([2. if r['source'].startswith('uci_') else 4. if r['source'].startswith('official_') else 1. for r in parts['train']])
    errors = ((y['train']==1)&(bp['train']<.6)) | ((y['train']==0)&(bp['train']>=.6))
    weights = source_weights * np.where(errors,2.,1.)
    adapted = extend_forest(base['model'],base['feature_names'],feature_names(SCHEMA))
    historical_cal = np.array([r['source'].startswith(('phreshphish','urlphish')) for r in parts['calibration']])
    results, eligible = {}, []
    for config in design['configs']:
        print('Training quality RF ' + config['name'], flush=True)
        donor = RandomForestClassifier(n_estimators=config['trees'],max_depth=config['depth'],
            min_samples_leaf=config['leaf'],max_features=config['max_features'],max_samples=config['max_samples'],
            class_weight='balanced_subsample',random_state=20261009,n_jobs=4,verbose=1)
        donor.fit(x['train'],y['train'],sample_weight=weights)
        joblib.dump(donor,OUT/(config['name']+'-forest.pkl'),compress=3)
        tree_raw = {s:np.array([t.predict_proba(x[s])[:,1] for t in donor.estimators_]) for s in ('calibration','validation')}
        for variant in design['forest_variants']:
            if variant == 'new_64':
                forest = donor
                raw = {s:tree_raw[s].mean(axis=0) for s in tree_raw}
            else:
                count = int(variant.split('_')[1])
                forest = copy.copy(adapted); forest.estimators_ = list(adapted.estimators_) + list(donor.estimators_[:count])
                forest.n_estimators = len(forest.estimators_)
                raw = {s:(baseline_raw[s]*len(adapted.estimators_)+tree_raw[s][:count].sum(axis=0))/forest.n_estimators for s in tree_raw}
            for method in design['calibration_methods']:
                mask = historical_cal if method == 'platt_historical' else np.ones(len(y['calibration']),dtype=bool)
                calibrator = BetaProbabilityCalibrator() if method == 'beta_combined' else LogisticRegression(C=1e6,max_iter=1000)
                calibrator.fit(raw['calibration'][mask].reshape(-1,1),y['calibration'][mask])
                p = calibrator.predict_proba(raw['validation'].reshape(-1,1))[:,1]
                m = {s:metrics(y['validation'][v],p[v]) for s,v in strata.items()}
                name = config['name']+'_'+variant+'_'+method
                bundle = {**base,'model':forest,'probability_calibrator':calibrator,'feature_names':feature_names(SCHEMA),
                    'feature_schema_version':SCHEMA,'model_version':'url-risk-rf-quality-'+name+'-20261008',
                    'trained_at':datetime.now(timezone.utc).isoformat(),'calibration_version':'quality-'+method+'-20261008',
                    'calibration':method+'_random_forest','probability_method':method+'_random_forest',
                    'production_ready':False,'statistical_gate_passed':False,
                    'dataset_row_count':sum(len(p) for p in parts.values()),'metrics':{'development_selection':m['all']},
                    'evaluation_design':{'prior_exposure_audit_complete':False,'forward_temporal_test':False,'test_used_for_selection':False},
                    'training_provenance':{'design':design,'variant':variant,'calibration_set':method,
                        'uses_old_trees':variant!='new_64','license':'Includes CC BY-NC 4.0 DeepURLBench'}}
                np.testing.assert_allclose(forest.predict_proba(x['validation'][:300])[:,1],raw['validation'][:300],atol=1e-12,rtol=0)
                checks = probes(bundle)
                passed = improves(m['all'],bm['all']) and all(no_regression(m[s],bm[s]) for s in strata) and all(r['decision']=='allow' for r in checks)
                results[name] = {'metrics':m,'probes':checks,'eligible':passed}
                if passed:
                    eligible.append(name); joblib.dump(bundle,OUT/(name+'.pkl'),compress=3)
                atomic_json(OUT/'development-progress.json',{'baseline_validation':bm,'candidates':results})
                print(json.dumps({name:{'eligible':passed,'facebook':checks[0]['final_score'],'warning':m['all']['warning']}}),flush=True)
    selected = min(eligible,key=lambda n:results[n]['metrics']['all']['warning']['false_positive_rate']) if eligible else None
    atomic_json(OUT/'selection.json',{'selected':selected,'baseline_validation':bm,'candidates':results,
        'test_used_for_selection':False,'promotion_ready':False})
    if selected:
        (OUT/'candidate.pkl').write_bytes((OUT/(selected+'.pkl')).read_bytes())
    assert sha256(app.MODEL_PATH)==baseline_hash
    print('Selection frozen: '+str(selected),flush=True)


if __name__ == '__main__': main()
