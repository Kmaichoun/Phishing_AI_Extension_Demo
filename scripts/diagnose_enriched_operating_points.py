"""Validation-only feasibility of monotonic calibration; never opens tests."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
import app
import joblib
import numpy as np
from train_host_context_candidate import read
from model_registry import atomic_json


def main():
    base=app.load_model_bundle()
    rows=[r for r in read(ROOT/'backend/data/simple_host_context_20261008/dataset.csv') if r['split']=='validation']
    original=read(ROOT/'backend/data/simple_recovered_query_structural_rf_20261005/dataset.csv')
    urls={r['url'] for r in original if r['split']=='validation'}
    x=np.load(ROOT/'backend/data/feature_cache_domain_enriched_20261008/validation.npy',mmap_mode='r')
    y=np.array([int(r['label']) for r in rows])
    old=base['model'].predict_proba(x[:,:32])[:,1]
    p=base['probability_calibrator'].predict_proba(old.reshape(-1,1))[:,1]
    donor=joblib.load(ROOT/'backend/data/simple_enriched_forest_20261008/new-trees.pkl')
    raw=np.array([t.predict_proba(x)[:,1] for t in donor.estimators_])
    historic=np.array([r['url'] in urls for r in rows])
    strata={'all':np.ones(len(rows),dtype=bool),'historical':historic,'augmentation':~historic}
    results={}
    for count in (24,48,96):
        values=(96*old+raw[:count].sum(axis=0))/(96+count)
        results[count]={}
        for key,t in [('warning',.6),('blocking',.8)]:
            bounds={}
            for name,mask in strata.items():
                positive=np.sort(values[mask&(y==1)])[::-1]
                negative=np.sort(values[mask&(y==0)])[::-1]
                tp=int(((p>=t)&mask&(y==1)).sum())
                fp=int(((p>=t)&mask&(y==0)).sum())-(1 if key=='warning' else 0)
                lower=float(negative[fp]) if 0<=fp<len(negative) else 0.
                upper=float(positive[tp-1]) if tp else 1.
                bounds[name]={'lower_exclusive':lower,'upper_inclusive':upper,'feasible':lower<upper}
            lower=max(b['lower_exclusive'] for b in bounds.values())
            upper=min(b['upper_inclusive'] for b in bounds.values())
            results[count][key]={'strata':bounds,'lower_exclusive':lower,'upper_inclusive':upper,'feasible':lower<upper}
    atomic_json(ROOT/'backend/data/simple_enriched_forest_20261008/operating-point-diagnostic.json',{
        'results':results,'test_scores_used':False,'threshold_or_model_changed':False,
        'scope':'Feasibility diagnostic only; bounds are NOT installed or used to manufacture a calibration curve.'})
    print(json.dumps(results),flush=True)


if __name__=='__main__':main()
