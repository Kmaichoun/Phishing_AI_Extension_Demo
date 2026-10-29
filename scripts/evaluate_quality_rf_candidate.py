"""One frozen-candidate confirmation plus regressions; no test-based refit."""
import json
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
import app
import joblib
import numpy as np
from train_host_context_candidate import read, reliability
from train_recovered_rf import feature_matrix, scores, subgroup_metrics, evaluate
from train_subdomain_fp_candidate import probes
from train_quality_rf_candidate import no_regression
from model_registry import atomic_json, sha256

OUT = ROOT / 'backend/data/simple_quality_rf_20261008'
QUALITY = ROOT / 'backend/data/quality-augmentation-20261008'


def main():
    global OUT
    parser=argparse.ArgumentParser()
    parser.add_argument('--experiment',type=Path,default=OUT)
    parser.add_argument('--targeted-repair',action='store_true',help='Only the predeclared reference-root hypothesis; preserves unrelated scores')
    args=parser.parse_args()
    OUT=args.experiment.resolve()
    assert OUT.parent==(ROOT/'backend/data').resolve()
    assert not (OUT / 'evaluation.json').exists(), 'Confirmation already read; do not reuse as untouched'
    selection = json.loads((OUT / 'selection.json').read_text(encoding='utf-8'))
    design = json.loads((OUT / 'design.json').read_text(encoding='utf-8'))
    if args.targeted_repair:
        assert design.get('unchanged_outside_context') and selection.get('targeted_repair')
        assert 'confirmation_gate' in design and 'gate_change_reason' in design
    assert selection['selected'] and not selection['test_used_for_selection']
    assert sha256(app.MODEL_PATH) == design['baseline_sha256']
    candidate = joblib.load(OUT / 'candidate.pkl'); baseline = app.load_model_bundle()
    manifest = json.loads((QUALITY / 'manifest.json').read_text(encoding='utf-8'))
    assert sha256(QUALITY / 'confirmation.csv') == manifest['confirmation_sha256'] == design['confirmation_sha256']
    round2 = ROOT / 'backend/data/incremental-confirmation-round2-20261008'
    m2 = json.loads((round2 / 'manifest.json').read_text(encoding='utf-8'))
    assert sha256(round2 / 'dataset.csv') == m2['csv_sha256']
    paths = {
        'fresh_uci_confirmation': QUALITY / 'confirmation.csv',
        'fresh_deepurlbench_confirmation_round2': round2 / 'dataset.csv',
        'historical_regression': ROOT / 'backend/data/simple_recovered_query_structural_rf_20261005/dataset.csv',
        'prior_deepurlbench_regression': ROOT / 'backend/data/host-context-20261008/dataset.csv',
        'prior_confirmation_regression': ROOT / 'backend/data/incremental-confirmation-20261008/dataset.csv',
        'recent_phishing_regression': ROOT / 'backend/data/host-context-20261008/temporal-phishing-test.csv',
    }
    result = {}
    # Save locked identity before any test scoring, even if evaluation fails midway.
    lock = {'candidate_sha256': sha256(OUT / 'candidate.pkl'), 'selection_sha256': sha256(OUT / 'selection.json'),
            'datasets': {name: sha256(path) for name,path in paths.items()}, 'test_used_for_selection':False,
            'targeted_repair':args.targeted_repair,'design_sha256':sha256(OUT/'design.json')}
    assert not (OUT / 'confirmation-lock.json').exists(), 'A confirmation attempt already exists'
    atomic_json(OUT / 'confirmation-lock.json', lock)
    for name, path in paths.items():
        print('Evaluating ' + name, flush=True)
        rows = read(path)
        if name in ('historical_regression','prior_deepurlbench_regression'):
            rows = [r for r in rows if r['split'] == 'holdout']
        x = feature_matrix(rows,candidate['feature_schema_version'])
        if candidate['feature_names'][:len(baseline['feature_names'])]==baseline['feature_names']:
            bx=x[:,:len(baseline['feature_names'])]
        else:bx=feature_matrix(rows,baseline['feature_schema_version'])
        y = np.array([int(r['label']) for r in rows])
        bp, cp = scores(baseline,[],bx), scores(candidate,[],x)
        m = {k: {**evaluate(y,p,.6,.8),'calibration':reliability(y,p)} if set(y)=={0,1} else {
                    side:subgroup_metrics(y,p,t) for side,t in [('warning',.6),('blocking',.8)]}
             for k,p in [('baseline',bp),('candidate',cp)]}
        passed = no_regression(m['candidate'],m['baseline'])
        if set(y)=={0,1} and not args.targeted_repair:
            passed = passed and m['candidate']['warning']['false_positive'] < m['baseline']['warning']['false_positive']
        outside_count=None
        if args.targeted_repair:
            index=candidate['feature_names'].index('publisher_reference_root_context')
            outside=x[:,index]==0
            np.testing.assert_allclose(cp[outside],bp[outside],atol=1e-12,rtol=0)
            assert np.all(cp<=bp+1e-12)
            outside_count=int(outside.sum())
        paired = {}
        for side,t in [('warning',.6),('blocking',.8)]:
            old, new = bp>=t, cp>=t
            paired[side] = {'phishing_lost':int(((y==1)&old&~new).sum()),
                            'phishing_gained':int(((y==1)&~old&new).sum()),
                            'false_positives_removed':int(((y==0)&old&~new).sum()),
                            'false_positives_added':int(((y==0)&~old&new).sum())}
        result[name] = {'rows':len(rows),'domains':len({r['group'] for r in rows}),
                        **m,'paired_transitions':paired,'measured_gate_passed':passed,
                        'outside_context_rows':outside_count}
        atomic_json(OUT / 'confirmation-progress.json',{'evaluations':result,'lock':lock})
        print(json.dumps({name:{'baseline_warning':m['baseline']['warning'],'candidate_warning':m['candidate']['warning'],'passed':passed}}),flush=True)
    checks = probes(candidate)
    passed = all(r['measured_gate_passed'] for r in result.values()) and all(r['decision']=='allow' for r in checks)
    atomic_json(OUT / 'evaluation.json',{'evaluations':result,'measured_gate_passed':passed,'probes':checks,**lock,
        'production_ready':False,'promotion_ready':False,'statistical_gate_passed':False,
        'baseline_sha256':design['baseline_sha256'],'prior_exposure_audit_complete':False,'forward_temporal_test':False,
        'confirmation_used_for_selection':False,'refit_on_test':False,
        'measured_gate_scope':'Targeted reference-root correction; no regressions and exact preservation outside context. Not a global independent FPR improvement claim.' if args.targeted_repair else 'General warning FPR reduction and no recall regression per evaluation dataset.',
        'limitations':manifest['limitations']+[
            'Gates compare finite-set counts, not a statistical guarantee of recall noninferiority.',
            'No net increase in misses is not preservation of detection of every individual old URL.']})
    assert sha256(app.MODEL_PATH)==design['baseline_sha256']
    print('Measured confirmation gates: ' + str(passed),flush=True)


if __name__ == '__main__': main()
