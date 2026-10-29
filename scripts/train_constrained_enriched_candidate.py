"""Explicit validation-tuned sigmoid MLE; only fresh test may confirm it.

Keeps RF-only formula and displayed 60/80 policy. No domain-specific exception.
Existing validation is tuning, not independent evidence. No test score is read.
"""
import copy
import json
import sys
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
import app
import joblib
import numpy as np
from feature_extractor import DOMAIN_ENRICHED_SCHEMA_VERSION as SCHEMA,feature_names
from forest_feature_adapter import extend_forest
from probability_calibration import ValidationConstrainedSigmoidCalibrator
from train_host_context_candidate import read
from train_enriched_forest_candidate import metrics
from train_subdomain_fp_candidate import probes,improves
from model_registry import atomic_json,sha256

OUT=ROOT/'backend/data/simple_constrained_enriched_20261008'
SOURCE=ROOT/'backend/data/simple_host_context_20261008/dataset.csv'
DONOR=ROOT/'backend/data/simple_enriched_forest_20261008/new-trees.pkl'
CACHE=ROOT/'backend/data/feature_cache_domain_enriched_20261008'


def operating_bounds(values,y,p,strata,key,t):
    bounds={}
    for name,mask in strata.items():
        positive=np.sort(values[mask&(y==1)])[::-1]
        negative=np.sort(values[mask&(y==0)])[::-1]
        tp=int(((p>=t)&mask&(y==1)).sum())
        allowed_fp=int(((p>=t)&mask&(y==0)).sum())-(1 if key=='warning' else 0)
        lower=float(negative[allowed_fp]) if 0<=allowed_fp<len(negative) else 0.
        upper=float(positive[tp-1]) if tp else 1.
        bounds[name]={'lower_exclusive':lower,'upper_inclusive':upper}
    return max(v['lower_exclusive'] for v in bounds.values()),min(v['upper_inclusive'] for v in bounds.values()),bounds


def main():
    OUT.mkdir(exist_ok=False)
    base=app.load_model_bundle();base_hash=sha256(app.MODEL_PATH)
    assert json.loads((CACHE/'manifest.json').read_text(encoding='utf-8'))=={
        'dataset_sha256':sha256(SOURCE),'feature_code_sha256':sha256(ROOT/'backend/feature_extractor.py'),'schema':SCHEMA}
    design={'created_at':datetime.now(timezone.utc).isoformat(),'baseline_sha256':base_hash,
        'donor_sha256':sha256(DONOR),'development_sha256':sha256(SOURCE),'schema':SCHEMA,
        'calibration_method':'Validation-constrained sigmoid MLE; experimental, not ordinary Platt scaling.',
        'validation_used_for_tuning':True,'validation_is_independent_evidence':False,
        'added_tree_counts':[24,48,96],'calibration_set':'combined',
        'heldout_scores_used_for_selection':False,'thresholds_changed':False,
        'selection':'Strict FPR/recall gates for all validation strata; benign probes allow; lowest all-strata warning FPR.',
        'prior_exposure_audit_complete':False,'license':'CC BY-NC 4.0'}
    atomic_json(OUT/'design.json',design)
    rows=read(SOURCE);parts={s:[r for r in rows if r['split']==s] for s in ('calibration','validation')}
    original=read(ROOT/'backend/data/simple_recovered_query_structural_rf_20261005/dataset.csv')
    old_urls={r['url'] for r in original if r['split']=='validation'}
    del rows,original
    names=feature_names(SCHEMA);adapted=extend_forest(base['model'],base['feature_names'],names);donor=joblib.load(DONOR)
    x,y,old_raw,new_raw={}, {}, {}, {}
    for s,part in parts.items():
        print('Scoring constrained development '+s,flush=True)
        x[s]=np.load(CACHE/(s+'.npy'),mmap_mode='r');y[s]=np.array([int(r['label']) for r in part])
        old_raw[s]=base['model'].predict_proba(x[s][:,:32])[:,1]
        new_raw[s]=np.array([t.predict_proba(x[s])[:,1] for t in donor.estimators_])
    p=base['probability_calibrator'].predict_proba(old_raw['validation'].reshape(-1,1))[:,1]
    historic=np.array([r['url'] in old_urls for r in parts['validation']])
    strata={'all':np.ones(len(p),dtype=bool),'historical':historic,'augmentation':~historic}
    bm={s:metrics(y['validation'][mask],p[mask]) for s,mask in strata.items()}
    results,bundles,eligible={}, {}, []
    for count in (24,48,96):
        raw={s:(old_raw[s]*96+new_raw[s][:count].sum(axis=0))/(96+count) for s in parts}
        wl,wu,warning=operating_bounds(raw['validation'],y['validation'],p,strata,'warning',.6)
        bl,bu,blocking=operating_bounds(raw['validation'],y['validation'],p,strata,'blocking',.8)
        if not wl<wu<bl<bu: continue
        calibrator=ValidationConstrainedSigmoidCalibrator((wl,wu),(bl,bu)).fit(raw['calibration'].reshape(-1,1),y['calibration'])
        cp=calibrator.predict_proba(raw['validation'].reshape(-1,1))[:,1]
        m={s:metrics(y['validation'][mask],cp[mask]) for s,mask in strata.items()}
        forest=copy.copy(adapted);forest.estimators_=list(adapted.estimators_)+list(donor.estimators_[:count]);forest.n_estimators=len(forest.estimators_)
        name=f'constrained_enriched_{count}'
        bundle={**base,'model':forest,'probability_calibrator':calibrator,'feature_schema_version':SCHEMA,'feature_names':names,
            'model_version':'url-risk-rf-'+name+'-20261008','trained_at':datetime.now(timezone.utc).isoformat(),
            'calibration_version':'validation-constrained-sigmoid-20261008',
            'calibration':'validation_constrained_sigmoid_rf','probability_method':'validation_constrained_sigmoid_rf',
            'production_ready':False,'statistical_gate_passed':False,'dataset_row_count':714534,
            'metrics':{'development_tuning':m['all']},'evaluation_design':{'prior_exposure_audit_complete':False,'forward_temporal_test':False,'validation_used_for_tuning':True},
            'training_provenance':{'design':design,'added_trees':count,'old_trees_preserved_exactly':True,'license':'CC BY-NC 4.0'}}
        checks=probes(bundle)
        passed=all(improves(m[s],bm[s]) for s in strata) and all(r['decision']=='allow' for r in checks)
        results[name]={'metrics':m,'probes':checks,'eligible':passed,'operating_constraints':{'warning':warning,'blocking':blocking},
            'calibration_coefficients':{'slope':float(calibrator.coef_[0,0]),'intercept':float(calibrator.intercept_[0])}}
        bundles[name]=bundle
        if passed:eligible.append(name)
        print(json.dumps({name:{'eligible':passed,'facebook':checks[0]['final_score'],'warning':m['all']['warning']} }),flush=True)
    selected=min(eligible,key=lambda n:results[n]['metrics']['all']['warning']['false_positive_rate']) if eligible else None
    atomic_json(OUT/'selection.json',{'selected':selected,'baseline_validation':bm,'candidates':results,
        'test_used_for_selection':False,'validation_used_for_tuning':True,'promotion_ready':False})
    if selected:joblib.dump(bundles[selected],OUT/'candidate.pkl',compress=3)
    assert sha256(app.MODEL_PATH)==base_hash
    print('Selection frozen: '+str(selected),flush=True)


if __name__=='__main__':main()
