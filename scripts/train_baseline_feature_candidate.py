"""Source-balanced RF with old raw prediction as an extra feature.

Existing tests are regression only. A new round-two publisher confirmation set
is reserved until selection. Raw baseline RF (not its calibrated scores) is
used in training, avoiding feedback from its calibration labels.
"""
import json
import sys
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
import app
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from feature_extractor import DOMAIN_ENRICHED_SCHEMA_VERSION as SCHEMA,feature_names
from baseline_feature_forest import BaselineFeatureForest
from probability_calibration import ValidationConstrainedSigmoidCalibrator
from train_host_context_candidate import read
from train_enriched_forest_candidate import metrics
from train_constrained_enriched_candidate import operating_bounds
from train_subdomain_fp_candidate import probes,improves
from model_registry import atomic_json,sha256

OUT=ROOT/'backend/data/simple_baseline_feature_20261008'
SOURCE=ROOT/'backend/data/simple_host_context_20261008/dataset.csv'
CACHE=ROOT/'backend/data/feature_cache_domain_enriched_20261008'


def main():
    OUT.mkdir(exist_ok=False)
    base=app.load_model_bundle();base_hash=sha256(app.MODEL_PATH)
    assert json.loads((CACHE/'manifest.json').read_text(encoding='utf-8'))=={
        'dataset_sha256':sha256(SOURCE),'feature_code_sha256':sha256(ROOT/'backend/feature_extractor.py'),'schema':SCHEMA}
    design={'created_at':datetime.now(timezone.utc).isoformat(),'baseline_sha256':base_hash,'development_sha256':sha256(SOURCE),
        'schema':SCHEMA,'model_family':'RF with baseline raw probability as an additional feature',
        'new_source_training_weight':4.,'training_error_weight':2.,'teacher_training_error_cutoff_raw':.5,
        'configs':['regularized','capacity'],'calibration_methods':['platt_combined','platt_historical','validation_constrained_sigmoid'],
        'validation_used_for_tuning':True,'validation_is_independent_evidence':False,'heldout_scores_used_for_selection':False,
        'confirmation_round':2,'selection':'Strict all-strata validation FPR/recall gates, benign probes allow; lowest warning FPR.',
        'prior_exposure_audit_complete':False,'license':'CC BY-NC 4.0'}
    atomic_json(OUT/'design.json',design)
    rows=read(SOURCE);parts={s:[r for r in rows if r['split']==s] for s in ('train','calibration','validation')}
    group_sets={s:{r['group'] for r in part} for s,part in parts.items()}
    assert all(not group_sets[a]&group_sets[b] for a,b in [('train','calibration'),('train','validation'),('calibration','validation')])
    original=read(ROOT/'backend/data/simple_recovered_query_structural_rf_20261005/dataset.csv')
    old_urls={r['url'] for r in original if r['split'] in ('calibration','validation')}
    del rows,original
    names=feature_names(SCHEMA)
    x,y,raw_old={}, {}, {}
    for s,part in parts.items():
        print('Preparing baseline-feature '+s,flush=True)
        url_x=np.load(CACHE/(s+'.npy'),mmap_mode='r')
        assert url_x.shape==(len(part),len(names))
        y[s]=np.array([int(r['label']) for r in part])
        raw_old[s]=base['model'].predict_proba(url_x[:,:32])[:,1]
        x[s]=np.column_stack((url_x,raw_old[s])).astype(np.float32,copy=False)
    train_errors=((y['train']==1)&(raw_old['train']<.5))|((y['train']==0)&(raw_old['train']>=.5))
    new_source=np.array([r['source'].startswith('deepurlbench') for r in parts['train']])
    weights=np.where(train_errors,2.,1.)*np.where(new_source,4.,1.)
    bp=base['probability_calibrator'].predict_proba(raw_old['validation'].reshape(-1,1))[:,1]
    historic_val=np.array([r['url'] in old_urls for r in parts['validation']])
    historic_cal=np.array([r['url'] in old_urls for r in parts['calibration']])
    strata={'all':np.ones(len(bp),dtype=bool),'historical':historic_val,'augmentation':~historic_val}
    bm={s:metrics(y['validation'][mask],bp[mask]) for s,mask in strata.items()}
    results,bundles,eligible={}, {}, []
    for config,trees,depth,leaf in [('regularized',96,20,10),('capacity',96,28,5)]:
        print('Training baseline-feature '+config,flush=True)
        forest=RandomForestClassifier(n_estimators=trees,max_depth=depth,min_samples_leaf=leaf,max_features=.33,
            class_weight='balanced_subsample',random_state=20261008,n_jobs=4)
        forest.fit(x['train'],y['train'],sample_weight=weights)
        joblib.dump(forest,OUT/(config+'-forest.pkl'),compress=3)
        raw_cal=forest.predict_proba(x['calibration'])[:,1]
        raw_val=forest.predict_proba(x['validation'])[:,1]
        methods={}
        for cal_set,mask in [('combined',np.ones(len(raw_cal),dtype=bool)),('historical',historic_cal)]:
            methods['platt_'+cal_set]=LogisticRegression(C=1e6,max_iter=1000).fit(raw_cal[mask].reshape(-1,1),y['calibration'][mask])
        wl,wu,_=operating_bounds(raw_val,y['validation'],bp,strata,'warning',.6)
        bl,bu,_=operating_bounds(raw_val,y['validation'],bp,strata,'blocking',.8)
        if wl<wu<bl<bu:
            methods['validation_constrained_sigmoid']=ValidationConstrainedSigmoidCalibrator((wl,wu),(bl,bu)).fit(raw_cal.reshape(-1,1),y['calibration'])
        for method,calibrator in methods.items():
            p=calibrator.predict_proba(raw_val.reshape(-1,1))[:,1]
            m={s:metrics(y['validation'][mask],p[mask]) for s,mask in strata.items()}
            model=BaselineFeatureForest(base['model'],forest,len(names))
            np.testing.assert_allclose(model.predict_proba(np.load(CACHE/'validation.npy',mmap_mode='r')[:1000])[:,1],raw_val[:1000],atol=1e-12,rtol=0)
            name=config+'_'+method
            bundle={**base,'model':model,'probability_calibrator':calibrator,'feature_schema_version':SCHEMA,'feature_names':names,
                'model_version':'url-risk-rf-baseline-feature-'+name+'-20261008','trained_at':datetime.now(timezone.utc).isoformat(),
                'calibration_version':method+'-baseline-feature-20261008','calibration':method+'_rf_baseline_feature',
                'probability_method':method+'_rf_baseline_feature','production_ready':False,'statistical_gate_passed':False,
                'dataset_row_count':sum(len(part) for part in parts.values()),'metrics':{'development_tuning':m['all']},
                'cv_strategy':'Registered-domain disjoint training/calibration; validation tuning; source confirmation',
                'evaluation_design':{'prior_exposure_audit_complete':False,'forward_temporal_test':False,'validation_used_for_tuning':True},
                'training_provenance':{'design':design,'config':config,'final_forest_extra_feature':'raw baseline RF probability',
                    'internal_feature_names':names+['baseline_rf_raw_probability'],'license':'CC BY-NC 4.0'}}
            checks=probes(bundle)
            passed=all(improves(m[s],bm[s]) for s in strata) and all(r['decision']=='allow' for r in checks)
            results[name]={'metrics':m,'probes':checks,'eligible':passed};bundles[name]=bundle
            if passed:eligible.append(name)
            print(json.dumps({name:{'eligible':passed,'facebook':checks[0]['final_score'],'warning':m['all']['warning']}}),flush=True)
    selected=min(eligible,key=lambda n:results[n]['metrics']['all']['warning']['false_positive_rate']) if eligible else None
    atomic_json(OUT/'selection.json',{'selected':selected,'baseline_validation':bm,'candidates':results,'test_used_for_selection':False,
        'validation_used_for_tuning':True,'promotion_ready':False})
    if selected:joblib.dump(bundles[selected],OUT/'candidate.pkl',compress=3)
    assert sha256(app.MODEL_PATH)==base_hash
    print('Selection frozen: '+str(selected),flush=True)


if __name__=='__main__':main()
