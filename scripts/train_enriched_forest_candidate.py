"""Error-focused new RF trees plus exact-preserved operating trees.

Calibration and validation domains are disjoint from ALL training rows. No
confirmation data or URL-specific score changes. Models remain experimental.
"""
import copy
import json
import sys
from pathlib import Path
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
import app
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from feature_extractor import DOMAIN_ENRICHED_SCHEMA_VERSION as SCHEMA, feature_names
from forest_feature_adapter import extend_forest
from probability_calibration import IsotonicProbabilityCalibrator, BetaProbabilityCalibrator
from train_recovered_rf import feature_matrix, scores, evaluate
from train_host_context_candidate import read, reliability
from train_subdomain_fp_candidate import probes, improves
from model_registry import atomic_json,sha256

OUT=ROOT/'backend/data/simple_enriched_forest_20261008'
SOURCE=ROOT/'backend/data/simple_host_context_20261008/dataset.csv'


def metrics(y,p):
    value=evaluate(y,p,.6,.8);value['calibration']=reliability(y,p);return value


def main():
    OUT.mkdir(exist_ok=False)
    base=app.load_model_bundle();base_hash=sha256(app.MODEL_PATH)
    rows=read(SOURCE)
    parts={s:[r for r in rows if r['split']==s] for s in ('train','calibration','validation')}
    domains={s:{r['group'] for r in part} for s,part in parts.items()}
    assert all(not domains[a]&domains[b] for a,b in [('train','calibration'),('train','validation'),('calibration','validation')])
    original=read(ROOT/'backend/data/simple_recovered_query_structural_rf_20261005/dataset.csv')
    old_urls={r['url'] for r in original if r['split'] in ('calibration','validation')}
    del rows,original
    names=feature_names(SCHEMA);old_count=len(base['feature_names'])
    assert names[:old_count]==base['feature_names']
    adapted=extend_forest(base['model'],base['feature_names'],names)
    design={'created_at':datetime.now(timezone.utc).isoformat(),'baseline_sha256':base_hash,
        'development_sha256':sha256(SOURCE),'feature_code_sha256':sha256(ROOT/'backend/feature_extractor.py'),
        'schema':SCHEMA,'new_tree_config':{'trees':96,'depth':28,'leaf':5,'max_features':.33},
        'train_error_weight':2.,'added_tree_counts':[24,48,96],'calibration_sets':['combined','historical'],
        'calibration_methods':['platt','isotonic','beta'],'heldout_scores_used_for_selection':False,
        'selection':'All validation strata reduce warning FPR with no warning/block recall loss or block FPR increase; benign probes allow.',
        'prior_exposure_audit_complete':False,'license':'CC BY-NC 4.0'}
    atomic_json(OUT/'design.json',design)
    x,y,old_raw={}, {}, {}
    cache=ROOT/'backend/data/feature_cache_domain_enriched_20261008'
    cache.mkdir(exist_ok=True)
    cache_key={'dataset_sha256':sha256(SOURCE),'feature_code_sha256':sha256(ROOT/'backend/feature_extractor.py'),'schema':SCHEMA}
    if (cache/'manifest.json').exists():
        assert json.loads((cache/'manifest.json').read_text(encoding='utf-8'))==cache_key
    else:atomic_json(cache/'manifest.json',cache_key)
    for split,part in parts.items():
        print('Extracting enriched '+split,flush=True)
        matrix_path=cache/(split+'.npy')
        if not matrix_path.exists():
            np.save(matrix_path,feature_matrix(part,SCHEMA))
        x[split]=np.load(matrix_path,mmap_mode='r');y[split]=np.array([int(r['label']) for r in part])
        assert x[split].shape==(len(part),len(names))
        old_raw[split]=base['model'].predict_proba(x[split][:,:old_count])[:,1]
        if split=='calibration':
            np.testing.assert_allclose(adapted.predict_proba(x[split])[:,1],old_raw[split],atol=1e-12,rtol=0)
    bp_train=base['probability_calibrator'].predict_proba(old_raw['train'].reshape(-1,1))[:,1]
    errors=((y['train']==1)&(bp_train<.6))|((y['train']==0)&(bp_train>=.6))
    print('Training error-focused forest: '+str(int(errors.sum()))+' weighted training errors',flush=True)
    donor=RandomForestClassifier(n_estimators=96,max_depth=28,min_samples_leaf=5,max_features=.33,
        class_weight='balanced_subsample',random_state=20261008,n_jobs=4)
    donor.fit(x['train'],y['train'],sample_weight=np.where(errors,2.,1.))
    joblib.dump(donor,OUT/'new-trees.pkl',compress=3)
    del x['train'],bp_train
    masks={s:np.array([r['url'] in old_urls for r in parts[s]]) for s in ('calibration','validation')}
    new_raw={s:np.array([t.predict_proba(x[s])[:,1] for t in donor.estimators_]) for s in masks}
    bp=base['probability_calibrator'].predict_proba(old_raw['validation'].reshape(-1,1))[:,1]
    strata={'all':np.ones(len(bp),dtype=bool),'historical':masks['validation'],'augmentation':~masks['validation']}
    bm={s:metrics(y['validation'][mask],bp[mask]) for s,mask in strata.items()}
    results,bundles,eligible={}, {}, []
    for count in (24,48,96):
        raw={s:(old_raw[s]*len(adapted.estimators_)+new_raw[s][:count].sum(axis=0))/(len(adapted.estimators_)+count) for s in masks}
        for cal_set in ('combined','historical'):
            cmask=np.ones(len(y['calibration']),dtype=bool) if cal_set=='combined' else masks['calibration']
            for method in ('platt','isotonic','beta'):
                name=f'enriched_{count}_{cal_set}_{method}'
                calibrator={'platt':lambda:LogisticRegression(C=1e6,max_iter=1000),
                    'isotonic':IsotonicProbabilityCalibrator,'beta':BetaProbabilityCalibrator}[method]()
                calibrator.fit(raw['calibration'][cmask].reshape(-1,1),y['calibration'][cmask])
                if method=='platt':assert calibrator.coef_[0,0]>0
                p=calibrator.predict_proba(raw['validation'].reshape(-1,1))[:,1]
                m={s:metrics(y['validation'][mask],p[mask]) for s,mask in strata.items()}
                forest=copy.copy(adapted);forest.estimators_=list(adapted.estimators_)+list(donor.estimators_[:count]);forest.n_estimators=len(forest.estimators_)
                # Check artifact inference equals cached selection probabilities.
                np.testing.assert_allclose(forest.predict_proba(x['validation'][:1000])[:,1],raw['validation'][:1000],atol=1e-12,rtol=0)
                bundle={**base,'model':forest,'probability_calibrator':calibrator,'feature_schema_version':SCHEMA,'feature_names':names,
                    'model_version':'url-risk-rf-'+name+'-20261008','trained_at':datetime.now(timezone.utc).isoformat(),
                    'calibration_version':method+'-domain-disjoint-enriched-20261008-'+cal_set,
                    'calibration':'heldout_'+method+'_random_forest','probability_method':'heldout_'+method+'_random_forest',
                    'production_ready':False,'statistical_gate_passed':False,'dataset_row_count':sum(len(part) for part in parts.values()),
                    'metrics':{'validation':m['all']},'evaluation_design':{'prior_exposure_audit_complete':False,'forward_temporal_test':False},
                    'training_provenance':{'design':design,'old_trees_preserved_exactly':True,'added_trees':count,'calibration_set':cal_set,'license':'CC BY-NC 4.0'}}
                checks=probes(bundle)
                passed=all(improves(m[s],bm[s]) for s in strata) and all(r['decision']=='allow' for r in checks)
                results[name]={'metrics':m,'probes':checks,'eligible':passed};bundles[name]=bundle
                if passed:eligible.append(name)
                print(json.dumps({name:{'eligible':passed,'facebook':checks[0]['final_score'],
                    'warning':m['all']['warning'],'historical_warning':m['historical']['warning'],'historical_blocking':m['historical']['blocking']}}),flush=True)
    selected=min(eligible,key=lambda n:results[n]['metrics']['all']['warning']['false_positive_rate']) if eligible else None
    atomic_json(OUT/'selection.json',{'selected':selected,'baseline_validation':bm,'candidates':results,'test_used_for_selection':False,'promotion_ready':False})
    if selected:joblib.dump(bundles[selected],OUT/'candidate.pkl',compress=3)
    assert sha256(app.MODEL_PATH)==base_hash
    print('Selection frozen: '+str(selected),flush=True)


if __name__=='__main__':main()
