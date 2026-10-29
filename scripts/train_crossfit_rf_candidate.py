"""Group-cross-fitted two-stage RF, independent calibration, frozen selection.

No pretrained baseline weights are used in the candidate. The old model is only
the comparator. The meta training probability feature comes from a forest that
has not seen ANY URL from the row's registered domain. Formula remains calibrated
final RF; no RuleScore/FuzzyScore/LLM blending or domain-specific exceptions.
"""
import hashlib
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

OUT=ROOT/'backend/data/simple_crossfit_rf_20261008'
SOURCE=ROOT/'backend/data/simple_host_context_20261008/dataset.csv'
CACHE=ROOT/'backend/data/feature_cache_domain_enriched_20261008'


def first_forest(trees,seed):
    return RandomForestClassifier(n_estimators=trees,max_depth=24,min_samples_leaf=10,
        max_features='sqrt',class_weight='balanced_subsample',random_state=seed,n_jobs=4)


def main():
    OUT.mkdir(exist_ok=False)
    base=app.load_model_bundle();base_hash=sha256(app.MODEL_PATH)
    assert json.loads((CACHE/'manifest.json').read_text(encoding='utf-8'))=={
        'dataset_sha256':sha256(SOURCE),'feature_code_sha256':sha256(ROOT/'backend/feature_extractor.py'),'schema':SCHEMA}
    design={'created_at':datetime.now(timezone.utc).isoformat(),'baseline_sha256':base_hash,'development_sha256':sha256(SOURCE),
        'schema':SCHEMA,'model_family':'Group-cross-fitted two-stage Random Forest',
        'new_source_weight':4.,'first_stage_fold_trees':32,'first_stage_final_trees':64,
        'folds':3,'fold_unit':'registered domain','fold_assignment':'SHA256 crossfit-rf-20261008 prefix',
        'second_stage_configs':['regularized','capacity'],'calibration_methods':['platt_combined','platt_historical','validation_constrained_sigmoid'],
        'validation_used_for_tuning':True,'validation_is_independent_evidence':False,'heldout_scores_used_for_selection':False,
        'candidate_uses_pretrained_baseline_weights':False,'candidate_training_exposure_complete':True,
        'baseline_prior_exposure_audit_complete':False,'confirmation_round':2,
        'selection':'Strict all-strata validation FPR/recall gates, benign probes allow; lowest warning FPR.',
        'license':'CC BY-NC 4.0','method_reference':'https://doi.org/10.1016/S0893-6080(05)80023-1'}
    atomic_json(OUT/'design.json',design)
    rows=read(SOURCE);parts={s:[r for r in rows if r['split']==s] for s in ('train','calibration','validation')}
    group_sets={s:{r['group'] for r in part} for s,part in parts.items()}
    assert all(not group_sets[a]&group_sets[b] for a,b in [('train','calibration'),('train','validation'),('calibration','validation')])
    original=read(ROOT/'backend/data/simple_recovered_query_structural_rf_20261005/dataset.csv')
    old_urls={r['url'] for r in original if r['split'] in ('calibration','validation')}
    del rows,original
    names=feature_names(SCHEMA)
    url_x={s:np.load(CACHE/(s+'.npy'),mmap_mode='r') for s in parts}
    y={s:np.array([int(r['label']) for r in part]) for s,part in parts.items()}
    for s,part in parts.items():assert url_x[s].shape==(len(part),len(names))
    source_weight=np.array([4. if r['source'].startswith('deepurlbench') else 1. for r in parts['train']])
    folds=np.array([int.from_bytes(hashlib.sha256(('crossfit-rf-20261008|'+r['group']).encode()).digest()[:4],'big')%3 for r in parts['train']])
    oof=np.full(len(y['train']),np.nan)
    fold_record=[]
    for fold in range(3):
        fit=folds!=fold;held=~fit
        fitted_groups={r['group'] for r,keep in zip(parts['train'],fit) if keep}
        held_groups={r['group'] for r,keep in zip(parts['train'],held) if keep}
        assert not fitted_groups&held_groups
        print('Training first-stage domain fold '+str(fold),flush=True)
        forest=first_forest(32,20261008+fold)
        forest.fit(url_x['train'][fit,:32],y['train'][fit],sample_weight=source_weight[fit])
        oof[held]=forest.predict_proba(url_x['train'][held,:32])[:,1]
        joblib.dump(forest,OUT/f'fold-{fold}-forest.pkl',compress=3)
        fold_record.append({'fold':fold,'fit_rows':int(fit.sum()),'held_rows':int(held.sum()),'domain_overlap':0})
    assert np.isfinite(oof).all()
    np.save(OUT/'train-oof-probability.npy',oof)
    atomic_json(OUT/'folds.json',{'folds':fold_record,'oof_probability_sha256':sha256(OUT/'train-oof-probability.npy')})
    print('Training full first-stage forest',flush=True)
    teacher=first_forest(64,20261008)
    teacher.fit(url_x['train'][:,:32],y['train'],sample_weight=source_weight)
    joblib.dump(teacher,OUT/'first-stage-forest.pkl',compress=3)
    x={'train':np.column_stack((url_x['train'],oof)).astype(np.float32,copy=False)}
    for s in ('calibration','validation'):
        raw=teacher.predict_proba(url_x[s][:,:32])[:,1]
        x[s]=np.column_stack((url_x[s],raw)).astype(np.float32,copy=False)
    baseline_raw=base['model'].predict_proba(url_x['validation'][:,:32])[:,1]
    bp=base['probability_calibrator'].predict_proba(baseline_raw.reshape(-1,1))[:,1]
    historic_val=np.array([r['url'] in old_urls for r in parts['validation']])
    historic_cal=np.array([r['url'] in old_urls for r in parts['calibration']])
    strata={'all':np.ones(len(bp),dtype=bool),'historical':historic_val,'augmentation':~historic_val}
    bm={s:metrics(y['validation'][mask],bp[mask]) for s,mask in strata.items()}
    errors=((y['train']==1)&(oof<.5))|((y['train']==0)&(oof>=.5))
    weights=source_weight*np.where(errors,2.,1.)
    results,bundles,eligible={}, {}, []
    for config,trees,depth,leaf in [('regularized',64,20,10),('capacity',96,28,5)]:
        print('Training crossfit meta forest '+config,flush=True)
        forest=RandomForestClassifier(n_estimators=trees,max_depth=depth,min_samples_leaf=leaf,max_features=.33,
            class_weight='balanced_subsample',random_state=20261008,n_jobs=4)
        forest.fit(x['train'],y['train'],sample_weight=weights)
        joblib.dump(forest,OUT/(config+'-meta-forest.pkl'),compress=3)
        raw_cal=forest.predict_proba(x['calibration'])[:,1];raw_val=forest.predict_proba(x['validation'])[:,1]
        methods={}
        for cal_set,mask in [('combined',np.ones(len(raw_cal),dtype=bool)),('historical',historic_cal)]:
            methods['platt_'+cal_set]=LogisticRegression(C=1e6,max_iter=1000).fit(raw_cal[mask].reshape(-1,1),y['calibration'][mask])
        wl,wu,_=operating_bounds(raw_val,y['validation'],bp,strata,'warning',.6)
        bl,bu,_=operating_bounds(raw_val,y['validation'],bp,strata,'blocking',.8)
        if wl<wu<bl<bu:methods['validation_constrained_sigmoid']=ValidationConstrainedSigmoidCalibrator((wl,wu),(bl,bu)).fit(raw_cal.reshape(-1,1),y['calibration'])
        for method,calibrator in methods.items():
            p=calibrator.predict_proba(raw_val.reshape(-1,1))[:,1]
            m={s:metrics(y['validation'][mask],p[mask]) for s,mask in strata.items()}
            model=BaselineFeatureForest(teacher,forest,len(names))
            np.testing.assert_allclose(model.predict_proba(url_x['validation'][:1000])[:,1],raw_val[:1000],atol=1e-12,rtol=0)
            name=config+'_'+method
            bundle={**base,'model':model,'probability_calibrator':calibrator,'feature_schema_version':SCHEMA,'feature_names':names,
                'model_version':'url-risk-rf-crossfit-'+name+'-20261008','trained_at':datetime.now(timezone.utc).isoformat(),
                'calibration_version':method+'-crossfit-rf-20261008','calibration':method+'_crossfit_rf','probability_method':method+'_crossfit_rf',
                'production_ready':False,'statistical_gate_passed':False,'dataset_row_count':sum(len(part) for part in parts.values()),
                'metrics':{'development_tuning':m['all']},'cv_strategy':'Registered-domain cross-fitting within train; separate calibration; validation tuning; fresh source confirmation',
                'evaluation_design':{'prior_exposure_audit_complete':False,'candidate_training_exposure_complete':True,'forward_temporal_test':False,'validation_used_for_tuning':True},
                'training_provenance':{'design':design,'config':config,'internal_feature_names':names+['domain_oof_rf_probability'],'license':'CC BY-NC 4.0'}}
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
