"""Validation-only ranking feasibility; optional explicit constrained calibration.

No confirmation score is read. This is experimental validation tuning, not
ordinary heldout Platt scaling or an independent improvement claim.
"""
import copy
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
import app
import joblib
import numpy as np
from feature_extractor import DOMAIN_ENRICHED_SCHEMA_VERSION as SCHEMA,feature_names
from forest_feature_adapter import extend_forest
from probability_calibration import ValidationConstrainedSigmoidCalibrator
from train_enriched_forest_candidate import metrics
from train_subdomain_fp_candidate import probes,improves
from train_quality_rf_candidate import no_regression
from model_registry import atomic_json,sha256

SOURCE=ROOT/'backend/data/simple_quality_rf_20261008'
OUT=ROOT/'backend/data/simple_quality_constrained_rf_20261008'


def bounds(raw,y,bp,strata,threshold,strict_aggregate):
    limits={}
    for name,mask in strata.items():
        negative=np.sort(raw[mask&(y==0)])[::-1]
        positive=np.sort(raw[mask&(y==1)])[::-1]
        allowed=int(((bp>=threshold)&mask&(y==0)).sum())-(1 if name=='all' and strict_aggregate else 0)
        wanted=int(((bp>=threshold)&mask&(y==1)).sum())
        lo=1. if allowed<0 else float(negative[allowed]) if allowed<len(negative) else 0.
        hi=float(positive[wanted-1]) if wanted else 1.
        limits[name]={'lower_exclusive':lo,'upper_inclusive':hi}
    return max(v['lower_exclusive'] for v in limits.values()),min(v['upper_inclusive'] for v in limits.values()),limits


def separated_intervals(wl,wu,bl,bu):
    if not (wl<wu and bl<bu and wl<bu):return None
    if wu>=bl:
        pivot=(max(wl,bl)+min(wu,bu))/2
        wu=min(wu,pivot-1e-9);bl=max(bl,pivot+1e-9)
    return ((wl,wu),(bl,bu)) if wl<wu<bl<bu else None


def main():
    OUT.mkdir(exist_ok=False)
    selection=json.loads((SOURCE/'selection.json').read_text(encoding='utf-8'))
    assert selection['selected'] is None, 'An eligible standard-calibrated candidate already exists'
    design=json.loads((SOURCE/'design.json').read_text(encoding='utf-8'))
    assert not (SOURCE/'confirmation-lock.json').exists(), 'Test read; do not tune on confirmation outcomes'
    base=app.load_model_bundle(); assert sha256(app.MODEL_PATH)==design['baseline_sha256']
    atomic_json(OUT/'design.json',{**design,'created_at':datetime.now(timezone.utc).isoformat(),
        'parent_design_sha256':sha256(SOURCE/'design.json'),
        'calibration_method':'Validation-constrained sigmoid MLE; not ordinary heldout Platt scaling',
        'validation_used_for_tuning':True,'validation_is_independent_evidence':False,
        'test_used_for_selection':False,'configs':['context','full_features'],
        'forest_variants':['new_64','pooled_32','pooled_64']})
    parts={'calibration':[],'validation':[]}
    with (SOURCE/'dataset.csv').open(encoding='utf-8',newline='') as f:
        for r in csv.DictReader(f):
            if r['split'] in parts:parts[r['split']].append(r)
    x={s:np.load(SOURCE/(s+'.npy'),mmap_mode='r') for s in parts}
    y={s:np.array([int(r['label']) for r in rows]) for s,rows in parts.items()}
    oldraw={s:base['model'].predict_proba(x[s][:,:32])[:,1] for s in parts}
    bp=base['probability_calibrator'].predict_proba(oldraw['validation'].reshape(-1,1))[:,1]
    strata={'all':np.ones(len(bp),dtype=bool)}
    for name,prefix in [('historical','phreshphish'),('historical_urlphish','urlphish'),('deepurlbench','deepurlbench'),('uci','uci_')]:
        mask=np.array([r['source'].startswith(prefix) for r in parts['validation']])
        if set(y['validation'][mask])=={0,1}:strata[name]=mask
    bm={s:metrics(y['validation'][mask],bp[mask]) for s,mask in strata.items()}
    adapted=extend_forest(base['model'],base['feature_names'],feature_names(SCHEMA))
    results,eligible,diagnostic={},[],{}
    for config in ('context','full_features'):
        donor=joblib.load(SOURCE/(config+'-forest.pkl'));donor.verbose=0
        print('Diagnosing quality ranking '+config,flush=True)
        trees={s:np.array([t.predict_proba(x[s])[:,1] for t in donor.estimators_]) for s in parts}
        for variant in ('new_64','pooled_32','pooled_64'):
            if variant=='new_64':
                forest=donor;raw={s:trees[s].mean(axis=0) for s in parts}
            else:
                n=int(variant.split('_')[1]);forest=copy.copy(adapted)
                forest.estimators_=list(adapted.estimators_)+list(donor.estimators_[:n]);forest.n_estimators=len(forest.estimators_)
                raw={s:(oldraw[s]*len(adapted.estimators_)+trees[s][:n].sum(axis=0))/forest.n_estimators for s in parts}
            wl,wu,wlimits=bounds(raw['validation'],y['validation'],bp,strata,.6,True)
            bl,bu,blimits=bounds(raw['validation'],y['validation'],bp,strata,.8,False)
            name=config+'_'+variant
            intervals=separated_intervals(wl,wu,bl,bu)
            feasible=intervals is not None
            diagnostic[name]={'warning_interval':[wl,wu],'blocking_interval':[bl,bu],
                'warning_strata':wlimits,'blocking_strata':blimits,'monotonic_calibration_feasible':feasible,
                'fitting_intervals':intervals}
            if not feasible:continue
            cal=ValidationConstrainedSigmoidCalibrator(*intervals).fit(raw['calibration'].reshape(-1,1),y['calibration'])
            cp=cal.predict_proba(raw['validation'].reshape(-1,1))[:,1]
            m={s:metrics(y['validation'][mask],cp[mask]) for s,mask in strata.items()}
            bundle={**base,'model':forest,'probability_calibrator':cal,'feature_schema_version':SCHEMA,'feature_names':feature_names(SCHEMA),
                'model_version':'url-risk-rf-quality-constrained-'+name+'-20261008','trained_at':datetime.now(timezone.utc).isoformat(),
                'calibration':'validation_constrained_sigmoid_rf','probability_method':'validation_constrained_sigmoid_rf',
                'calibration_version':'quality-validation-constrained-20261008','production_ready':False,'statistical_gate_passed':False,
                'dataset_row_count':925602,'metrics':{'development_tuning':m['all']},
                'evaluation_design':{'prior_exposure_audit_complete':False,'forward_temporal_test':False,'validation_used_for_tuning':True},
                'training_provenance':{'source_design_sha256':sha256(SOURCE/'design.json'),'variant':name,'license':'Includes CC BY-NC 4.0 DeepURLBench'}}
            np.testing.assert_allclose(forest.predict_proba(x['validation'][:300])[:,1],raw['validation'][:300],atol=1e-12,rtol=0)
            checks=probes(bundle)
            passed=improves(m['all'],bm['all']) and all(no_regression(m[s],bm[s]) for s in strata) and all(r['decision']=='allow' for r in checks)
            results[name]={'metrics':m,'probes':checks,'eligible':passed}
            if passed:eligible.append(name);joblib.dump(bundle,OUT/(name+'.pkl'),compress=3)
            print(json.dumps({name:{'eligible':passed,'facebook':checks[0]['final_score']}}),flush=True)
    selected=min(eligible,key=lambda n:results[n]['metrics']['all']['warning']['false_positive_rate']) if eligible else None
    atomic_json(OUT/'ranking-diagnostic.json',diagnostic)
    atomic_json(OUT/'selection.json',{'selected':selected,'baseline_validation':bm,'candidates':results,
        'test_used_for_selection':False,'validation_used_for_tuning':True,'promotion_ready':False})
    if selected:(OUT/'candidate.pkl').write_bytes((OUT/(selected+'.pkl')).read_bytes())
    assert sha256(app.MODEL_PATH)==design['baseline_sha256']
    print('Selection frozen: '+str(selected),flush=True)


if __name__=='__main__':main()
