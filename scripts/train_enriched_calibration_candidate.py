"""Calibration-only development search on frozen enriched trees.

Weights depend on raw scores/domain multiplicity, never phishing labels or test
outcomes. This is empirical calibration-model selection, not a probability or
production guarantee. Original strict per-stratum validation gates preserved.
"""
import copy
import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
import app
import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from probability_calibration import BrierSigmoidCalibrator
from feature_extractor import DOMAIN_ENRICHED_SCHEMA_VERSION as SCHEMA,feature_names
from forest_feature_adapter import extend_forest
from train_host_context_candidate import read
from train_enriched_forest_candidate import metrics
from train_subdomain_fp_candidate import probes,improves
from model_registry import atomic_json,sha256

OUT=ROOT/'backend/data/simple_enriched_calibration_20261008'
SOURCE=ROOT/'backend/data/simple_host_context_20261008/dataset.csv'
DONOR=ROOT/'backend/data/simple_enriched_forest_20261008/new-trees.pkl'
CACHE=ROOT/'backend/data/feature_cache_domain_enriched_20261008'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--brier',action='store_true');args=parser.parse_args()
    out=ROOT/'backend/data/simple_enriched_brier_20261008' if args.brier else OUT
    method='brier_sigmoid' if args.brier else 'weighted_platt'
    out.mkdir(exist_ok=False)
    base=app.load_model_bundle();base_hash=sha256(app.MODEL_PATH)
    assert json.loads((CACHE/'manifest.json').read_text(encoding='utf-8'))=={
        'dataset_sha256':sha256(SOURCE),'feature_code_sha256':sha256(ROOT/'backend/feature_extractor.py'),'schema':SCHEMA}
    weights_names=['uniform','domain_balanced','high_score_4','high_score_16','low_score_4','domain_high_score_4']
    design={'created_at':datetime.now(timezone.utc).isoformat(),'baseline_sha256':base_hash,
        'donor_sha256':sha256(DONOR),'development_sha256':sha256(SOURCE),'schema':SCHEMA,'calibration_method':method,
        'added_tree_counts':[24,48,96],'calibration_sets':['combined','historical'],'weight_functions':weights_names,
        'weight_definition':'Domain: inverse rows per registered domain; high k: 1+k*p^2; low k: 1+k*(1-p)^2. Normalize mean to one.',
        'weight_uses_labels':False,'heldout_scores_used_for_selection':False,
        'selection':'All validation strata lower warning FPR without warning/block recall loss or block FPR increase; benign probes allow.',
        'prior_exposure_audit_complete':False,'license':'CC BY-NC 4.0'}
    atomic_json(out/'design.json',design)
    rows=read(SOURCE);parts={s:[r for r in rows if r['split']==s] for s in ('calibration','validation')}
    original=read(ROOT/'backend/data/simple_recovered_query_structural_rf_20261005/dataset.csv')
    old_urls={r['url'] for r in original if r['split'] in parts}
    del rows,original
    names=feature_names(SCHEMA);adapted=extend_forest(base['model'],base['feature_names'],names)
    donor=joblib.load(DONOR)
    x,y,old_raw,new_raw,masks={}, {}, {}, {}, {}
    for s,part in parts.items():
        print('Scoring calibration development '+s,flush=True)
        x[s]=np.load(CACHE/(s+'.npy'),mmap_mode='r')
        assert x[s].shape==(len(part),len(names))
        y[s]=np.array([int(r['label']) for r in part])
        old_raw[s]=base['model'].predict_proba(x[s][:,:len(base['feature_names'])])[:,1]
        new_raw[s]=np.array([t.predict_proba(x[s])[:,1] for t in donor.estimators_])
        masks[s]=np.array([r['url'] in old_urls for r in part])
    bp=base['probability_calibrator'].predict_proba(old_raw['validation'].reshape(-1,1))[:,1]
    strata={'all':np.ones(len(bp),dtype=bool),'historical':masks['validation'],'augmentation':~masks['validation']}
    bm={s:metrics(y['validation'][mask],bp[mask]) for s,mask in strata.items()}
    results,bundles,eligible={}, {}, []
    for count in (24,48,96):
        raw={s:(old_raw[s]*len(adapted.estimators_)+new_raw[s][:count].sum(axis=0))/(len(adapted.estimators_)+count) for s in parts}
        for cal_set in ('combined','historical'):
            cmask=np.ones(len(y['calibration']),dtype=bool) if cal_set=='combined' else masks['calibration']
            group_counts=Counter(r['group'] for r,keep in zip(parts['calibration'],cmask) if keep)
            domain_weight=np.array([1/group_counts[r['group']] for r,keep in zip(parts['calibration'],cmask) if keep])
            cr=raw['calibration'][cmask]
            weight_options={'uniform':np.ones(len(cr)),'domain_balanced':domain_weight,'high_score_4':1+4*cr**2,
                'high_score_16':1+16*cr**2,'low_score_4':1+4*(1-cr)**2,'domain_high_score_4':domain_weight*(1+4*cr**2)}
            for weight_name,weight in weight_options.items():
                name=f'enriched_{count}_{cal_set}_{weight_name}' + ('_brier' if args.brier else '')
                weight=weight/weight.mean()
                calibrator=(BrierSigmoidCalibrator() if args.brier else LogisticRegression(C=1e6,max_iter=1000)).fit(cr.reshape(-1,1),y['calibration'][cmask],sample_weight=weight)
                assert calibrator.coef_[0,0]>0
                p=calibrator.predict_proba(raw['validation'].reshape(-1,1))[:,1]
                m={s:metrics(y['validation'][mask],p[mask]) for s,mask in strata.items()}
                forest=copy.copy(adapted);forest.estimators_=list(adapted.estimators_)+list(donor.estimators_[:count]);forest.n_estimators=len(forest.estimators_)
                bundle={**base,'model':forest,'probability_calibrator':calibrator,'feature_schema_version':SCHEMA,'feature_names':names,
                    'model_version':'url-risk-rf-'+name+'-20261008','trained_at':datetime.now(timezone.utc).isoformat(),
                    'calibration_version':method+'-domain-disjoint-20261008-'+weight_name+'-'+cal_set,
                    'calibration':'heldout_'+method+'_random_forest','probability_method':'heldout_'+method+'_random_forest',
                    'production_ready':False,'statistical_gate_passed':False,'dataset_row_count':714534,
                    'metrics':{'validation':m['all']},'evaluation_design':{'prior_exposure_audit_complete':False,'forward_temporal_test':False},
                    'training_provenance':{'design':design,'added_trees':count,'calibration_set':cal_set,
                        'calibration_weight':weight_name,'old_trees_preserved_exactly':True,'license':'CC BY-NC 4.0'}}
                checks=probes(bundle)
                passed=all(improves(m[s],bm[s]) for s in strata) and all(r['decision']=='allow' for r in checks)
                results[name]={'metrics':m,'probes':checks,'eligible':passed,'calibration_coefficients':{
                    'slope':float(calibrator.coef_[0,0]),'intercept':float(calibrator.intercept_[0])}}
                bundles[name]=bundle
                if passed:eligible.append(name)
                print(json.dumps({name:{'eligible':passed,'facebook':checks[0]['final_score'],
                    'warning':m['all']['warning'],'historical_warning':m['historical']['warning'],'historical_blocking':m['historical']['blocking']}}),flush=True)
    selected=min(eligible,key=lambda n:results[n]['metrics']['all']['warning']['false_positive_rate']) if eligible else None
    atomic_json(out/'selection.json',{'selected':selected,'baseline_validation':bm,'candidates':results,'test_used_for_selection':False,'promotion_ready':False})
    if selected:joblib.dump(bundles[selected],out/'candidate.pkl',compress=3)
    assert sha256(app.MODEL_PATH)==base_hash
    print('Selection frozen: '+str(selected),flush=True)


if __name__=='__main__':main()
