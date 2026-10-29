"""Targeted learned entry-URL repair, preserving all scores outside its context.

This is a narrower hypothesis than the failed full-refit experiments. It does
not claim a global FPR improvement on unrelated unseen domains. The original
Platt mapping is transported for exact score continuity, not falsely described
as a new calibration fit. Fresh calibration metrics must be evaluated again.
"""
import copy
import argparse
import csv
import hashlib
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
from feature_extractor import (REFERENCE_ROOT_SCHEMA_VERSION as SCHEMA,feature_names,feature_vector,reference_root_context,reference_root_sensitive_query)
from reference_origin_features import registry
from forest_feature_adapter import extend_forest
from forest_leaf_refinement import learn_regions,refine_estimator
from model_registry import atomic_json,sha256
from train_enriched_forest_candidate import metrics
from train_quality_rf_candidate import no_regression
from train_selective_refinement_candidate import strata_for,URL_PROBES

SOURCE=ROOT/'backend/data/simple_quality_rf_20261008'
PARENT=ROOT/'backend/data/simple_reference_refinement_rf_20261008'
OUT=ROOT/'backend/data/simple_reference_root_repair_20261008'


def main():
    global OUT
    parser=argparse.ArgumentParser()
    parser.add_argument('--single-observation-repair',action='store_true',help='Explicit sparse reference case repair; not a general learned safety classifier')
    args=parser.parse_args()
    if args.single_observation_repair:OUT=ROOT/'backend/data/simple_reference_root_sparse_repair_20261008'
    supports=(1,2,4) if args.single_observation_repair else (4,8,16)
    OUT.mkdir(exist_ok=False)
    base=app.load_model_bundle();base['model'].verbose=0
    parent=json.loads((PARENT/'design.json').read_text(encoding='utf-8'))
    assert sha256(app.MODEL_PATH)==parent['baseline_sha256']
    assert sha256(SOURCE/'dataset.csv')==parent['development_sha256']
    assert registry()[1]==parent['reference_origin_registry_sha256']
    names=feature_names(SCHEMA);context_column=names.index('publisher_reference_root_context')
    design={**parent,'created_at':datetime.now(timezone.utc).isoformat(),'schema':SCHEMA,
        'feature_code_sha256':sha256(ROOT/'backend/feature_extractor.py'),
        'refinement_code_sha256':sha256(ROOT/'backend/forest_leaf_refinement.py'),
        'hypothesis':'Targeted correction of named and reference-entry false positives; not a global generalization claim.',
        'method':'One-feature supervised leaf refinement on reference root context, guarded by phishing observations.',
        'configs':[{'support':n} for n in supports],
        'sparse_case_repair':args.single_observation_repair,
        'sparse_case_limitation':'As few as one observed reference URL supports a learned branch; not evidence of broad Internet accuracy or calibrated phishing probability.',
        'calibration_method':'Transported original Platt mapping; no new calibration fit; reassess reliability on confirmation.',
        'unchanged_outside_context':True,'test_used_for_selection':False,
        'selection':'No validation warning/block FP/FN increase per source; at least one reported benign case fixed and all probes allow; choose fewer changed leaves.',
        'confirmation_gate':'No warning/block FP/FN increase on each fresh and regression dataset; all named benign probes allow. FPR need not strictly fall on unrelated domains whose predictions are preserved.',
        'gate_change_reason':'Different, narrowly scoped hypothesis declared before reading any confirmation score. Earlier general-FPR experiments remain failed.'}
    atomic_json(OUT/'design.json',design)
    labels={s:[] for s in ('train','calibration','validation')};sources={s:[] for s in labels};guards=[]
    sensitive_query={s:[] for s in labels};check_urls={s:[] for s in labels}
    with (SOURCE/'dataset.csv').open(encoding='utf-8',newline='') as f:
        for row in csv.DictReader(f):
            s=row['split'];labels[s].append(int(row['label']));sources[s].append(row['source'])
            sensitive_query[s].append(reference_root_sensitive_query(row['url']))
            if len(check_urls[s])<100:check_urls[s].append(row['url'])
            if s=='calibration':guards.append(int.from_bytes(hashlib.sha256(('refinement-guard-20261008|'+row['group']).encode()).digest()[:4],'big')%2==0)
    y={s:np.asarray(v,dtype=np.int8) for s,v in labels.items()};src=np.asarray(sources['validation'],dtype='U100')
    del labels,sources
    x={}
    for s in y:
        prefix=np.load(PARENT/(s+'.npy'),mmap_mode='r')
        assert prefix.shape==(len(y[s]),len(names)-1)
        matrix=np.lib.format.open_memmap(OUT/(s+'.npy'),mode='w+',dtype=np.float32,shape=(len(y[s]),len(names)))
        matrix[:,:-1]=prefix
        # Identical vectorized projection of the explicit v10 feature function.
        mask=(prefix[:,names.index('publisher_reference_origin_match')]==1)&(prefix[:,names.index('path_depth')]==0)&(prefix[:,names.index('path_length')]<=1)
        for name in ('has_nested_url','has_encoded_url','has_at_symbol','has_backslash','redirect_parameter_count',
                     'credential_parameter_count','enhanced_redirect_parameter_count','enhanced_credential_parameter_count'):
            mask&=prefix[:,names.index(name)]==0
        mask&=~np.asarray(sensitive_query[s],dtype=bool)
        matrix[:,-1]=mask.astype(np.float32);matrix.flush();del matrix
        x[s]=np.load(OUT/(s+'.npy'),mmap_mode='r')
        full=np.asarray([feature_vector(u,SCHEMA) for u in check_urls[s]],dtype=np.float32)
        np.testing.assert_array_equal(full,x[s][:len(full)])
    oldraw={s:np.load(PARENT/('baseline-'+s+'.npy')) for s in y}
    bp=base['probability_calibrator'].predict_proba(oldraw['validation'].reshape(-1,1))[:,1]
    strata=strata_for(src,y['validation'])
    # Also audit all actual publisher sources, including one-class references.
    for source in np.unique(src):
        mask=src==source
        if set(y['validation'][mask])=={0,1}:strata['source:'+source]=mask
    bm={s:metrics(y['validation'][m],bp[m]) for s,m in strata.items()}
    guard=np.asarray(guards,dtype=bool);gx=x['calibration'][guard];gy=y['calibration'][guard]
    tp=base['probability_calibrator'].predict_proba(oldraw['train'].reshape(-1,1))[:,1]
    hard=(y['train']==0)&(tp>=.6)
    adapted=extend_forest(base['model'],base['feature_names'],names)
    all_regions=[]
    for i,est in enumerate(adapted.estimators_):
        regions=learn_regions(est,x['train'],y['train'],hard,gx,gy,20261011+i,depth=1,min_leaf=1 if args.single_observation_repair else 4,columns=[context_column])
        all_regions.append(regions)
        print(json.dumps({'tree':i+1,'regions':len(regions)}),flush=True)
    results,eligible={},[]
    px=np.asarray([feature_vector(u,SCHEMA) for u in URL_PROBES],dtype=np.float32)
    for support in supports:
        forest=copy.copy(adapted);forest.estimators_=[];changed=0
        for est,regions in zip(adapted.estimators_,all_regions):
            new,n=refine_estimator(est,regions,1,support,required_feature=context_column)
            forest.estimators_.append(new);changed+=n
        forest.verbose=0
        raw=forest.predict_proba(x['validation'])[:,1]
        outside=x['validation'][:,context_column]==0
        np.testing.assert_allclose(raw[outside],oldraw['validation'][outside],atol=1e-12,rtol=0)
        assert np.all(raw<=oldraw['validation']+1e-12)
        p=base['probability_calibrator'].predict_proba(raw.reshape(-1,1))[:,1]
        m={s:metrics(y['validation'][mask],p[mask]) for s,mask in strata.items()}
        probe_raw=forest.predict_proba(px)[:,1]
        pp=base['probability_calibrator'].predict_proba(probe_raw.reshape(-1,1))[:,1]
        checks=[{'url':u,'final_score':round(float(v*100)),'risk_score_value':float(v*100),
                 'decision':'block' if v>=.8 else 'warn' if v>=.6 else 'allow'} for u,v in zip(URL_PROBES,pp)]
        name='support'+str(support)
        passed=changed>0 and all(no_regression(m[s],bm[s]) for s in strata) and all(v['decision']=='allow' for v in checks)
        bundle={**base,'model':forest,'feature_names':names,'feature_schema_version':SCHEMA,
            'model_version':'url-risk-rf-reference-root-repair-'+name+'-20261008',
            'trained_at':datetime.now(timezone.utc).isoformat(),'calibration':'transported_original_platt_rf',
            'probability_method':'transported_original_platt_rf','calibration_version':'original-map-transported-root-repair-20261008',
            'reference_origin_registry_sha256':registry()[1],'production_ready':False,'statistical_gate_passed':False,
            'metrics':{'development_regression':m['all']},'dataset_row_count':sum(len(v) for v in y.values()),
            'evaluation_design':{'targeted_repair':True,'test_used_for_selection':False,'prior_exposure_audit_complete':False,
                                 'forward_temporal_test':False,'calibrator_refit':False},
            'training_provenance':{'design_sha256':sha256(OUT/'design.json'),'method':design['method'],'support':support,
                                   'license':'Includes CC BY-NC 4.0 DeepURLBench'}}
        joblib.dump(bundle,OUT/(name+'.pkl'),compress=3)
        results[name]={'metrics':m,'probes':checks,'eligible':passed,'changed_terminal_nodes':changed,
                       'outside_context_predictions_preserved':True}
        if passed:eligible.append(name)
        atomic_json(OUT/'development-progress.json',{'baseline_validation':bm,'candidates':results})
        print(json.dumps({name:{'eligible':passed,'probes':checks,'warning':m['all']['warning']}}),flush=True)
    selected=min(eligible,key=lambda n:results[n]['changed_terminal_nodes']) if eligible else None
    atomic_json(OUT/'selection.json',{'selected':selected,'baseline_validation':bm,'candidates':results,
                                    'test_used_for_selection':False,'promotion_ready':False,'targeted_repair':True})
    if selected:(OUT/'candidate.pkl').write_bytes((OUT/(selected+'.pkl')).read_bytes())
    assert sha256(app.MODEL_PATH)==design['baseline_sha256']
    print('Selection frozen: '+str(selected),flush=True)


if __name__=='__main__':main()
