"""RF-only experiment on recovered data; never replaces the operating model.

New-run domain isolation is checked. Missing historical exposure records remain
explicitly unknown; this experiment cannot bypass the production promotion gate.
Publisher test data are opened only after selection on development validation.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression

from domain_parts import domain_parts
from build_dataset import normalized_url
from feature_extractor import FEATURE_NAMES, FEATURE_SCHEMA_VERSION, LEGACY_FEATURE_SCHEMA_VERSION, QUERY_ROBUST_SCHEMA_VERSION, feature_names, feature_vector
from model_registry import atomic_json, sha256
from train_model import classification_metrics, probability_metrics

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent
FORMULA = 'Score = 100 × Calibrate(Random Forest)'
FEATURE_JOBS = 4


def feature_batch(urls, schema):
    return np.asarray([feature_vector(url, schema) for url in urls], dtype=np.float32)


def feature_matrix(rows, schema=FEATURE_SCHEMA_VERSION):
    urls = [r['url'] for r in rows]
    chunks = joblib.Parallel(n_jobs=FEATURE_JOBS, prefer='processes')(
        joblib.delayed(feature_batch)(urls[i:i+10000], schema) for i in range(0,len(urls),10000))
    return np.concatenate(chunks)


def partition(domain):
    bucket = int(hashlib.sha256(('rf-recovery-20261005|' + domain).encode()).hexdigest()[:8], 16) % 10
    return 'train' if bucket < 7 else 'calibration' if bucket == 7 else 'validation'


def read_rows(path, expected_hash, split):
    if sha256(path) != expected_hash:
        raise ValueError('Dataset checksum mismatch: ' + str(path))
    rows, seen = [], set()
    with path.open(encoding='utf-8', newline='') as handle:
        for row in csv.DictReader(handle):
            if row['label'] not in {'0', '1'} or row['publisher_split'] != split or row['url'] in seen:
                raise ValueError('Invalid label, partition, or repeated URL')
            domain = domain_parts(urlsplit(row['url']).hostname)[0]
            if domain != row['group']:
                raise ValueError('Domain group no longer matches the pinned PSL')
            row['label'] = int(row['label'])
            row['split'] = partition(domain) if split == 'train' else 'holdout'
            rows.append(row); seen.add(row['url'])
    return rows


def scores(bundle, rows, matrix=None):
    if bundle['fusion_method'] != 'ml_only':
        raise ValueError('This experiment compares RF-only policies')
    schema = bundle.get('feature_schema_version', LEGACY_FEATURE_SCHEMA_VERSION)
    x = matrix if matrix is not None else feature_matrix(rows, schema)
    raw = bundle['model'].predict_proba(x)[:, list(bundle['model'].classes_).index(1)]
    return bundle['probability_calibrator'].predict_proba(raw.reshape(-1, 1))[:, list(bundle['probability_calibrator'].classes_).index(1)]


def cutoff(y, p, ceiling, minimum=0.001):
    negatives = np.sort(p[y == 0])
    n, z = len(negatives), 1.6448536269514722
    if not n or set(y) != {0, 1}:
        raise ValueError('Both classes required for threshold selection')
    grid = np.arange(max(1, int(np.ceil(minimum * 10000))), 10001) / 10000
    fp = n - np.searchsorted(negatives, grid, side='left')
    rate = fp / n
    upper = (rate + z*z/(2*n) + z*np.sqrt(rate*(1-rate)/n + z*z/(4*n*n))) / (1+z*z/n)
    eligible = np.flatnonzero(upper <= ceiling)
    if not len(eligible):
        raise ValueError('Insufficient negative data for FPR ceiling')
    # Lowest threshold maximizes recall subject to the prespecified FP ceiling.
    value = float(grid[eligible[0]])
    return value, classification_metrics(y, p, value)


def evaluate(y, p, warning, blocking):
    return {'warning': classification_metrics(y, p, warning),
            'blocking': classification_metrics(y, p, blocking),
            'probability': probability_metrics(y, p)}


def subgroup_metrics(y, p, threshold):
    if set(y) == {0, 1}:
        return classification_metrics(y, p, threshold)
    predicted = p >= threshold
    fp = int(((y == 0) & predicted).sum()); tn = int(((y == 0) & ~predicted).sum())
    tp = int(((y == 1) & predicted).sum()); fn = int(((y == 1) & ~predicted).sum())
    return {'threshold':threshold,'false_positive':fp,'true_negative':tn,'true_positive':tp,'false_negative':fn,
            'false_positive_rate':fp/(fp+tn) if fp+tn else None,
            'recall':tp/(tp+fn) if tp+fn else None,'roc_auc':None,
            'limitation':'Only one class in this subgroup; absent-class metrics are not estimable'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--trees', type=int, default=160)
    parser.add_argument('--jobs', type=int, default=4)
    parser.add_argument('--data', type=Path, default=BASE/'data/recovered-20261004')
    parser.add_argument('--resume-selection', action='store_true',
                        help='Resume final evaluation from a frozen selection without training or threshold tuning')
    parser.add_argument('--additional-mendeley', type=Path,
                        help='Checksum-pinned historical Mendeley v3 CSV; development only')
    parser.add_argument('--query-weight', type=float, default=1.0)
    parser.add_argument('--only-hard-negative', action='store_true')
    parser.add_argument('--feature-schema', choices=[FEATURE_SCHEMA_VERSION, QUERY_ROBUST_SCHEMA_VERSION], default=FEATURE_SCHEMA_VERSION)
    args = parser.parse_args()
    global FEATURE_JOBS
    FEATURE_JOBS = args.jobs
    out = args.output.resolve(); out.mkdir(parents=True, exist_ok=args.resume_selection)
    data = args.data.resolve()
    manifest = json.loads((data/'recovery-manifest.json').read_text(encoding='utf-8'))
    audit = json.loads((ROOT/'output/dataset-recovery/audit.json').read_text(encoding='utf-8'))
    baseline_hash = sha256(BASE/'model.pkl')
    if not args.resume_selection:
        shutil.copyfile(BASE/'model.pkl', out/'baseline.pkl')
    elif sha256(out/'baseline.pkl') != baseline_hash:
        raise ValueError('Operating baseline changed; cannot resume the same experiment')
    baseline = joblib.load(out/'baseline.pkl')
    dev = read_rows(data/manifest['development_deduplicated']['csv'], manifest['development_deduplicated']['sha256'], 'train')
    augmentation = None
    if args.additional_mendeley:
        expected='21093e2902e5441c86a6daf95e86e7c332046e477fdf109a579d7bd81e586d6c'
        if sha256(args.additional_mendeley)!=expected:raise ValueError('Mendeley source checksum mismatch')
        test_info=audit['domain_disjoint_test_candidate']
        if sha256(data/test_info['csv'])!=test_info['sha256']:raise ValueError('Reserved partition changed')
        # Read only its group inventory for exclusion; no labels/scores inform fit.
        with (data/test_info['csv']).open(encoding='utf-8',newline='') as f:
            reserved_groups={r['group'] for r in csv.DictReader(f)}
        seen={r['url'] for r in dev}; counts=Counter()
        with args.additional_mendeley.open(encoding='utf-8-sig',newline='') as f:
            for raw in csv.DictReader(f):
                if raw['status'] not in {'legitimate','phishing'}:raise ValueError('Unknown Mendeley label')
                url=normalized_url(raw['url'])
                if not url:counts['invalid']+=1;continue
                try:domain=domain_parts(urlsplit(url).hostname)[0]
                except (ValueError,UnicodeError):counts['invalid']+=1;continue
                if url in seen:counts['already_in_development']+=1;continue
                if domain in reserved_groups:counts['reserved_domain_excluded']+=1;continue
                label=int(raw['status']=='phishing')
                dev.append({'url':url,'label':label,'group':domain,'source':'mendeley_webpage_v3',
                    'split':partition(domain),'observed_at':'2020-05','time_precision':'month',
                    'publisher_split':'train'})
                counts['added_label_'+str(label)]+=1;seen.add(url)
                if label==0 and urlsplit(url).query:counts['added_benign_query']+=1
        augmentation={'sha256':expected,'source':'https://data.mendeley.com/datasets/c2gw7fy2j4/3',
            'license':'CC BY 4.0','attribution':'Abdelhakim Hannousse and Salima Yahiouche (2021)',
            'publisher_collection_time':'May 2020, month precision; not a current safety verdict',
            'counts':dict(counts),'test_reused_after_first_experiment':True}
    groups = {s: {r['group'] for r in dev if r['split'] == s} for s in ('train','calibration','validation')}
    assert not (groups['train'] & groups['calibration'] or groups['train'] & groups['validation'] or groups['calibration'] & groups['validation'])
    split_counts = {s: {'rows':sum(r['split']==s for r in dev), 'domains':len(groups[s]),
                       'labels': dict(Counter(str(r['label']) for r in dev if r['split']==s))} for s in groups}
    print(json.dumps({'stage':'features', 'splits':split_counts}), flush=True)
    x = None if args.resume_selection else feature_matrix(dev, args.feature_schema)
    y = np.asarray([r['label'] for r in dev], dtype=np.int8)
    masks = {s: np.asarray([r['split']==s for r in dev]) for s in groups}
    for mask in masks.values():
        if set(y[mask]) != {0,1}: raise ValueError('Both classes required in each split')
    # Mine hard negatives only in training. No validation/test labels affect fit.
    training_rows = [r for r in dev if r['split']=='train']
    print('Scoring training negatives with baseline for training-only weights...', flush=True)
    old_train = np.zeros(len(training_rows)) if args.resume_selection else scores(baseline, training_rows)
    weights = np.ones(len(training_rows), dtype=np.float64)
    train_labels = y[masks['train']]
    hard = (train_labels == 0) & (old_train >= baseline['policy']['warning_threshold']/100)
    weights[hard] = 4.0
    query_negative=np.asarray([r['label']==0 and bool(urlsplit(r['url']).query) for r in training_rows])
    weights[query_negative]=np.maximum(weights[query_negative],args.query_weight)
    configs = [('regularized', 24, 5, None), ('hard_negative', 20, 10, weights)]
    if args.only_hard_negative:configs=configs[1:]
    selected, candidates = None, {}
    if args.resume_selection:
        frozen = json.loads((out/'selection.json').read_text(encoding='utf-8'))
        if frozen['baseline_sha256'] != baseline_hash or frozen['test_read_for_selection']:
            raise ValueError('Selection is not a frozen pre-test selection')
        selected, candidates = frozen['selected'], frozen['candidates']
        configs = []
    for name, depth, leaf, sample_weight in configs:
        print(json.dumps({'stage':'training','name':name,'trees':args.trees,'depth':depth,'leaf':leaf,'hard_negatives':int(hard.sum())}), flush=True)
        forest = RandomForestClassifier(n_estimators=args.trees, max_depth=depth, min_samples_leaf=leaf,
            class_weight='balanced_subsample', random_state=20261005, n_jobs=args.jobs)
        forest.fit(x[masks['train']], train_labels, sample_weight=sample_weight)
        raw_cal = forest.predict_proba(x[masks['calibration']])[:, list(forest.classes_).index(1)]
        calibrator = LogisticRegression(C=1e6, max_iter=1000)
        calibrator.fit(raw_cal.reshape(-1,1), y[masks['calibration']])
        if calibrator.coef_[0,0] <= 0: raise ValueError('Calibration must be monotonic')
        bundle = {'model':forest,'probability_calibrator':calibrator,'fusion_method':'ml_only',
                  'feature_schema_version':args.feature_schema}
        vp = scores(bundle, [], x[masks['validation']])
        warning, wm = cutoff(y[masks['validation']], vp, .01)
        blocking, bm = cutoff(y[masks['validation']], vp, .001, warning)
        candidates[name] = {'parameters':{'trees':args.trees,'max_depth':depth,'min_samples_leaf':leaf,
            'training_only_hard_negative_weight':4 if sample_weight is not None else 1,
            'training_only_benign_query_weight':args.query_weight if sample_weight is not None else 1},
            'warning_threshold':warning*100, 'blocking_threshold':blocking*100,
            'validation':{'warning':wm,'blocking':bm,'probability':probability_metrics(y[masks['validation']],vp)}}
        joblib.dump(bundle,out/(name+'.pkl'),compress=3)
        print(json.dumps({'name':name,'validation':candidates[name]}),flush=True)
        if selected is None or wm['recall'] > candidates[selected]['validation']['warning']['recall']:
            selected = name
    # Freeze selection before opening the reserved publisher test.
    atomic_json(out/'selection.json',{'selected':selected,'candidates':candidates,
        'rule':'Highest validation warning recall under 1% Wilson upper FPR; blocking under 0.1%; ties use regularized',
        'baseline_sha256':baseline_hash,'test_read_for_selection':False})
    candidate = joblib.load(out/(selected+'.pkl'))
    warning, blocking = (candidates[selected][k]/100 for k in ('warning_threshold','blocking_threshold'))
    print('Selection frozen. Opening domain-disjoint publisher test for final evaluation...',flush=True)
    test_info = audit['domain_disjoint_test_candidate']
    holdout = read_rows(data/test_info['csv'],test_info['sha256'],'test')
    test_groups = {r['group'] for r in holdout}
    if test_groups & set.union(*groups.values()): raise ValueError('Holdout domain leakage')
    hx = feature_matrix(holdout, candidate['feature_schema_version'])
    hy = np.asarray([r['label'] for r in holdout],dtype=np.int8)
    hp = scores(candidate, [], hx)
    oldp = scores(baseline, holdout)
    new_metrics = evaluate(hy,hp,warning,blocking)
    old_metrics = evaluate(hy,oldp,baseline['policy']['warning_threshold']/100,baseline['policy']['blocking_threshold']/100)
    split_counts['holdout']={'rows':len(holdout),'domains':len(test_groups),'labels':dict(Counter(str(v) for v in hy))}
    education = np.asarray([r['group'].endswith(('.ac.th','.edu','.ac.uk')) or '.edu.' in r['group'] for r in holdout])
    subgroups = {}
    for label, mask in [('education_domain_pattern',education),('has_query',np.asarray([bool(urlsplit(r['url']).query) for r in holdout]))]:
        if mask.any():
            subgroups[label]={'rows':int(mask.sum()),'candidate':subgroup_metrics(hy[mask],hp[mask],warning),
                             'baseline':subgroup_metrics(hy[mask],oldp[mask],baseline['policy']['warning_threshold']/100)}
    statistical_gate = (new_metrics['warning']['false_positive_rate_upper_95'] <= .01
        and new_metrics['blocking']['false_positive_rate_upper_95'] <= .001
        and new_metrics['warning']['false_positive_rate'] < old_metrics['warning']['false_positive_rate']
        and new_metrics['warning']['recall'] >= old_metrics['warning']['recall'])
    now = datetime.now(timezone.utc).isoformat()
    evaluation = {'created_at':now,'selected':selected,'risk_formula':FORMULA,
        'dataset_rows':len(dev)+len(holdout),'sources':dict(Counter(r['source'] for r in dev+holdout)),
        'split_counts':split_counts,'group_overlap':0,'refit_on_holdout':False,
        'baseline_sha256':baseline_hash,'candidates':candidates,'candidate_holdout':new_metrics,
        'baseline_same_holdout':old_metrics,'subgroups':subgroups,'statistical_gate_passed':statistical_gate,
        'promotion_ready':False,'prior_exposure_audit_complete':False,
        'missing_original_files':manifest['missing_original_files'],
        'augmentation':augmentation,
        'feature_schema_version':candidate['feature_schema_version'],
        'test_reused_after_previous_experiments':True,
        'limitations':['Domain-disjoint within this new run; historical baseline exposure remains unknown.',
            'Publisher labels are historical, not a current security verdict.',
            'PhreshPhish benign query preprocessing can bias URL-only results.',
            'Mixed-source training and same-publisher test do not establish generalization to every source.',
            'Wilson intervals treat URL rows as Bernoulli trials; within-domain correlation is not modeled.'],
        'input_hashes':{'development':manifest['development_deduplicated']['sha256'],'holdout':test_info['sha256'],
                       'feature_extractor':sha256(BASE/'feature_extractor.py'),'psl':sha256(BASE/'public_suffix_list.dat')}}
    candidate.update({'model_version':'url-risk-random-forest-recovered-20261005' + ('-query-structural' if args.feature_schema == QUERY_ROBUST_SCHEMA_VERSION else ''),
        'policy_version':'rf-only-domain-disjoint-20261005','model_family':'random_forest',
        'risk_formula':FORMULA,'rule_weight':0.0,'ml_weight':1.0,'feature_names':feature_names(candidate['feature_schema_version']),
        'probability_method':'heldout_platt_random_forest','calibration_version':'platt-disjoint-domains-20261005',
        'policy':{'warning_threshold':round(warning*100,4),'blocking_threshold':round(blocking*100,4),
                  'warning_max_fpr':.01,'blocking_max_fpr':.001},
        'cv_strategy':'Registered-domain disjoint Train / Calibration / Validation / Publisher Holdout',
        'trained_at':now,'dataset_row_count':len(dev)+len(holdout),
        'metrics':{'validation':candidates[selected]['validation'],'reused_benchmark':new_metrics},
        'evaluation_design':{'split_counts':split_counts,'holdout_rows':len(holdout),'development_rows':len(dev), 'holdout_reused':True},
        'production_ready':False,'prior_exposure_audit_complete':False})
    joblib.dump(candidate,out/'candidate.pkl',compress=3)
    with (out/'dataset.csv').open('w',encoding='utf-8',newline='') as f:
        fields=['url','label','source','group','split','observed_at','time_precision','publisher_split']
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(dev+holdout)
    with (out/'holdout-scores.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.writer(f);w.writerow(['url','label','group','candidate_score','baseline_score'])
        w.writerows((r['url'],r['label'],r['group'],float(p*100),float(o*100)) for r,p,o in zip(holdout,hp,oldp))
    evaluation['candidate_sha256']=sha256(out/'candidate.pkl')
    atomic_json(out/'evaluation.json',evaluation)
    if sha256(BASE/'model.pkl') != baseline_hash: raise ValueError('Operating model changed during experiment')
    print(json.dumps({'selected':selected,'candidate':new_metrics,'baseline':old_metrics,'statistical_gate_passed':statistical_gate,'production_replaced':False}),flush=True)


if __name__=='__main__':main()
