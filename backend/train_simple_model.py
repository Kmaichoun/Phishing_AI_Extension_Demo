"""Reproducible URL-only experiment. Never visits URLs contained in datasets.

Downloads only the attributed UCI archive, preserves the deployed model, and
writes a candidate. Training, calibration, selection and test domains are disjoint.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import shutil
import urllib.request
import zipfile
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import joblib
import numpy as np
import tldextract
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression

from build_dataset import normalized_url, calculate_rule_scores
from feature_extractor import FEATURE_NAMES, FEATURE_SCHEMA_VERSION, feature_vector
from fuzzy_scoring import fuzzy_score
from risk_policy import apply_consensus_guardrail
from train_model import classification_metrics, probability_metrics
from model_registry import atomic_json

BASE = Path(__file__).resolve().parent
UCI_URL = 'https://archive.ics.uci.edu/static/public/967/phiusiil+phishing+url+dataset.zip'
UCI_PAGE = 'https://archive.ics.uci.edu/dataset/967/phiusiil+phishing+url+dataset'
MENDELEY_URL = 'https://data.mendeley.com/public-files/datasets/c2gw7fy2j4/files/575316f4-ee1d-453e-a04f-7b950915b61b/file_downloaded'
MENDELEY_HASH = '21093e2902e5441c86a6daf95e86e7c332046e477fdf109a579d7bd81e586d6c'
FORMULAS = {'ml_only': 'FinalScore = MLScore',
            'weighted_40_60': 'FinalScore = 0.40 * RuleScore + 0.60 * MLScore'}
EXTRACT = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None)


def read_reviewed_rows(path):
    """New collection input, not the redacted history/feedback export."""
    with path.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        required = {'url', 'label', 'source', 'observed_at', 'label_evidence', 'reviewed_by'}
        if not required <= set(reader.fieldnames or []):
            raise ValueError('Reviewed collection needs: ' + ', '.join(sorted(required)))
        for row in reader:
            if row['label'] not in {'0', '1'} or any(not row[k].strip() for k in required):
                raise ValueError('Missing reviewed label/provenance')
            observed = datetime.fromisoformat(row['observed_at'].replace('Z', '+00:00'))
            if observed.tzinfo is None or observed > datetime.now(timezone.utc):
                raise ValueError('observed_at needs a timezone and cannot be in the future')
            if urlsplit(row['url']).scheme not in {'https', 'http'}:
                raise ValueError('Original HTTP(S) URL required')
            yield row


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_published_rows(manifest_path):
    """Publisher labels are evidence, not a claim of personal manual review.

    Preserve missing/day-precision dates honestly. The publisher's test split
    must not accidentally enter training; collect only its train partition.
    """
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    path = (manifest_path.parent / manifest['csv']).resolve()
    if path.parent != manifest_path.parent.resolve() or digest(path) != manifest['csv_sha256']:
        raise ValueError('Published CSV path or checksum mismatch')
    sources = manifest['sources']
    for source in sources.values():
        if not all(source.get(key) for key in ('url','license','attribution','label_evidence','time_semantics')):
            raise ValueError('Publisher attribution, license and label/date evidence required')
    with path.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        required = {'url','label','source','observed_at','time_precision','publisher_split'}
        if not required <= set(reader.fieldnames or []):
            raise ValueError('Published URL columns missing')
        for row in reader:
            if row['label'] not in {'0','1'} or row['source'] not in sources:
                raise ValueError('Unknown published source or label')
            if row['publisher_split'] not in {'train','external'}:
                raise ValueError('Publisher test data cannot enter development')
            if row['time_precision'] == 'day':
                if not row['observed_at'] or date.fromisoformat(row['observed_at']) > datetime.now(timezone.utc).date():
                    raise ValueError('Invalid publisher observation date')
            elif row['time_precision'] != 'unknown' or row['observed_at']:
                raise ValueError('Do not invent observation dates')
            yield row


def group(url):
    host = (urlsplit(url).hostname or '').lower().encode('idna').decode('ascii')
    result = EXTRACT(host)
    # Group entire shared hosting provider too: conservative leakage prevention.
    return result.top_domain_under_public_suffix or host


def split_for(domain, legacy_domains):
    if domain in legacy_domains:
        return 'train'
    bucket = int(hashlib.sha256(('simple-v1|' + domain).encode()).hexdigest()[:8], 16) % 10
    return 'train' if bucket < 6 else 'calibration' if bucket == 6 else 'validation' if bucket == 7 else 'holdout'


def threshold(y, score, ceiling, minimum=0.0):
    # Explicit 0.1 score-point grid. Threshold remains exactly reproducible at runtime.
    negatives = np.sort(score[y == 0])
    n = len(negatives)
    if not n:
        raise ValueError('Threshold selection requires negative samples')
    z = 1.6448536269514722
    for value in np.arange(max(1, int(np.ceil(minimum * 1000))), 1001) / 1000:
        fp = n - np.searchsorted(negatives, value, side='left')
        p = fp / n
        upper = (p + z*z/(2*n) + z*np.sqrt(p*(1-p)/n + z*z/(4*n*n))) / (1+z*z/n)
        if upper <= ceiling:
            metrics = classification_metrics(y, score, float(value))
            metrics['meets_fpr_constraint'] = True
            return float(value), metrics
    raise ValueError(f'No threshold meets FPR upper bound {ceiling}; do not deploy')


def legacy_scores(bundle, x, rules):
    p = bundle['model'].predict_proba(x)[:, list(bundle['model'].classes_).index(1)]
    calibrator = bundle.get('probability_calibrator')
    if calibrator is not None:
        p = calibrator.predict_proba(p.reshape(-1, 1))[:, list(calibrator.classes_).index(1)]
    if bundle.get('fusion_method') == 'ml_only':
        return p
    if bundle.get('fusion_method') == 'weighted_40_60':
        return .4 * rules / 100 + .6 * p
    if bundle.get('fusion_model') is None:
        return (0.4 * rules / 100 + 0.6 * p)
    fuzzy = np.array([fuzzy_score(v) / 100 for v in rules])
    fusion = bundle['fusion_model'].predict_proba(np.column_stack([fuzzy, p]))[:, 1]
    return np.array([apply_consensus_guardrail(f, m, s)[0] for f, m, s in zip(fuzzy, p, fusion)])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--uci-limit', type=int, default=100000)
    parser.add_argument('--trees', type=int, default=180)
    parser.add_argument('--formula', choices=['ml_only', 'compare'], default='ml_only',
                        help='Default: calibrated RF only; compare explicitly evaluates the legacy 40/60 blend too.')
    parser.add_argument('--mendeley', action='store_true')
    parser.add_argument('--balance-shapes', action='store_true')
    parser.add_argument('--prior-experiment', type=Path)
    parser.add_argument('--additional-data', type=Path,
                        help='New reviewed URL collection with labels, evidence and observation timestamps.')
    parser.add_argument('--published-data', type=Path,
                        help='Checksum-pinned publisher manifest from collect_research_urls.py.')
    parser.add_argument('--external-holdout', action='store_true',
                        help='Reserve all Mendeley domains as an external-source holdout.')
    parser.add_argument('--external-source', help='Reserve a never-seen source, e.g. reviewed_partner_2026_10')
    parser.add_argument('--output', type=Path, required=True, help='A new, unused experiment directory')
    args = parser.parse_args()
    legacy_path = BASE / 'data' / 'training_urls.csv'
    if not legacy_path.is_file():
        raise FileNotFoundError('Restore backend/data/training_urls.csv from the original training run. '
                                'Its domains are required to prevent evaluation leakage; do not regenerate it as a substitute.')
    for previous in (BASE / 'data').glob('simple_*'):
        if (previous / 'evaluation.json').is_file() and not (previous / 'dataset.csv').is_file():
            raise FileNotFoundError(f'Restore {previous / "dataset.csv"} to exclude previously seen domains from evaluation.')
    out = args.output.resolve()
    # Exclusive directory creation prevents concurrent runs overwriting each other.
    out.mkdir(parents=True, exist_ok=False)
    archive = BASE / 'data' / 'cache' / 'uci-967.zip'
    if not archive.exists():
        archive.parent.mkdir(parents=True, exist_ok=True)
        print('Downloading UCI dataset archive (not visiting dataset URLs)...', flush=True)
        request = urllib.request.Request(UCI_URL, headers={'User-Agent': 'PhishRadar-academic-research/2.0'})
        with urllib.request.urlopen(request, timeout=60) as response, archive.with_suffix('.tmp').open('wb') as dest:
            shutil.copyfileobj(response, dest)
        archive.with_suffix('.tmp').replace(archive)
    legacy_path = BASE / 'data' / 'training_urls.csv'
    with legacy_path.open(encoding='utf-8-sig', newline='') as handle:
        legacy = list(csv.DictReader(handle))
    legacy_domains = {group(row['url']) for row in legacy}
    # Every previously seen domain is development data now, even past holdouts.
    prior_inventory = {}
    for previous in sorted((BASE/'data').glob('simple_*')):
        if previous.resolve() == out or not (previous/'dataset.csv').is_file():
            continue
        prior_inventory[previous.name] = digest(previous/'dataset.csv')
        with (previous/'dataset.csv').open(encoding='utf-8', newline='') as handle:
            legacy_domains.update(group(row['url']) for row in csv.DictReader(handle))
    if args.prior_experiment:
        # Previously observed experiment domains cannot become a new test set.
        with (args.prior_experiment / 'dataset.csv').open(encoding='utf-8', newline='') as handle:
            legacy_domains.update(row['group'] for row in csv.DictReader(handle))
    # Keep genuine historical URLs; exclude fabricated paths and popularity-only labels.
    real_sources = {'phishtank', 'openphish'}
    records = {}
    conflicts = set()
    invalid = 0
    provenance = {}
    external_domains = set()

    def add(raw, label, source):
        nonlocal invalid
        url = normalized_url(raw)
        if not url:
            invalid += 1
            return
        try:
            domain = group(url)
            feature_vector(url)
        except (ValueError, UnicodeError):
            invalid += 1
            return
        key = url  # paths are case sensitive; do not case-fold them
        if key in records and records[key]['label'] != label:
            conflicts.add(key)
        elif key not in records:
            records[key] = {'url': url, 'label': label, 'source': source, 'group': domain}
        provenance.setdefault(key, set()).add(source)
        if source == 'mendeley_webpage_v3':
            external_domains.add(domain)

    for row in legacy:
        if row.get('source') in real_sources:
            add(row['url'], int(row['label']), 'legacy_' + row['source'])
    # Internal benign seeds and generated query/subdomain variants are excluded.
    # A trusted-looking domain is not sufficient evidence for a benign label.
    reviewed_metadata = []
    if args.additional_data:
        for row in read_reviewed_rows(args.additional_data):
            add(row['url'], int(row['label']), 'reviewed_' + row['source'])
            reviewed_metadata.append(row)
    published_manifest = None
    if args.published_data:
        published_manifest = json.loads(args.published_data.read_text(encoding='utf-8'))
        for row in read_published_rows(args.published_data):
            source = 'published_' + row['source']
            if (row['publisher_split'] == 'external') != (source == args.external_source):
                raise ValueError('Reserved external publisher rows must match --external-source')
            add(row['url'], int(row['label']), source)
    with zipfile.ZipFile(archive) as zipped:
        names = [n for n in zipped.namelist() if n.endswith('.csv')]
        if len(names) != 1:
            raise ValueError('Unexpected UCI archive layout')
        with zipped.open(names[0]) as handle:
            raw_rows = list(csv.DictReader(io.TextIOWrapper(handle, encoding='utf-8-sig')))
    # Deterministic representative sample, before examining scores or holdout results.
    raw_rows.sort(key=lambda row: hashlib.sha256(row['URL'].encode()).digest())
    for row in raw_rows[:args.uci_limit]:
        if row['label'] not in {'0', '1'}:
            raise ValueError('Unexpected UCI label')
        add(row['URL'], 1 - int(row['label']), 'uci_phiusiil')
    if args.mendeley:
        mendeley = archive.parent / 'mendeley-c2gw7fy2j4-v3.csv'
        if not mendeley.exists():
            print('Downloading attributed Mendeley CSV only...', flush=True)
            request = urllib.request.Request(MENDELEY_URL, headers={
                'User-Agent':'Mozilla/5.0 PhishRadarAcademic/2.0',
                'Accept':'text/csv,*/*',
            })
            with urllib.request.urlopen(request, timeout=60) as response, mendeley.open('wb') as dest:
                shutil.copyfileobj(response, dest)
        if digest(mendeley) != MENDELEY_HASH:
            raise ValueError('Mendeley checksum does not match publisher metadata')
        with mendeley.open(encoding='utf-8-sig', newline='') as handle:
            for row in csv.DictReader(handle):
                if row['status'] not in {'legitimate', 'phishing'}:
                    raise ValueError('Unexpected Mendeley label')
                add(row['url'], int(row['status'] == 'phishing'), 'mendeley_webpage_v3')
    for key in conflicts:
        records.pop(key, None)
    rows = sorted(records.values(), key=lambda row: row['url'])
    external_key = args.external_source or ('mendeley_webpage_v3' if args.external_holdout else None)
    if args.external_source and args.external_holdout:
        raise ValueError('Choose one external source option')
    if external_key:
        external_domains = {group(url) for url,sources in provenance.items() if external_key in sources and url in records}
    if external_key and (not external_domains or external_domains & legacy_domains):
        raise ValueError('External holdout source was already seen (or missing). Obtain a genuinely new source; do not recycle it as untouched.')
    for row in rows:
        row['is_external'] = int(bool(external_key and external_key in provenance[row['url']]))
        row['split'] = ('holdout' if external_key and row['group'] in external_domains
                        else split_for(row['group'], legacy_domains))
    for split in ('train', 'calibration', 'validation', 'holdout'):
        if {r['label'] for r in rows if r['split'] == split} != {0,1}:
            raise ValueError(f'{split} lacks fresh examples of both classes. Add reviewed new domains with --additional-data; previous holdouts cannot be reused as new tests.')
    print(f'Extracting URL-only features for {len(rows):,} rows...', flush=True)
    x = np.asarray([feature_vector(r['url']) for r in rows])
    y = np.asarray([r['label'] for r in rows])
    rules = np.asarray(calculate_rule_scores([r['url'] for r in rows]), dtype=float)
    masks = {s: np.array([r['split'] == s for r in rows]) for s in ('train','calibration','validation','holdout')}
    split_counts = {s: {'rows': int(m.sum()), 'labels': dict(Counter(str(v) for v in y[m])),
                        'domains': len({r['group'] for r in rows if r['split'] == s})} for s,m in masks.items()}
    for s,m in masks.items():
        if set(y[m]) != {0,1}:
            raise ValueError(f'{s} lacks fresh examples of both classes. Add reviewed new domains with --additional-data; previous holdouts cannot be reused as new tests.')
    with (out / 'dataset.csv').open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=['url','label','source','group','split','is_external','rule_score'])
        writer.writeheader()
        writer.writerows(dict(r, rule_score=float(v)) for r,v in zip(rows,rules))
    atomic_json(out/'provenance.json', {
        'prior_experiments': prior_inventory,
        'additional_data_sha256': digest(args.additional_data) if args.additional_data else None,
        'reviewed_rows': reviewed_metadata,
        'multi_source_urls': {hashlib.sha256(url.encode()).hexdigest(): sorted(sources)
                              for url,sources in provenance.items() if len(sources) > 1},
        'excluded_internal_benign_seeds': True,
    })
    if published_manifest:
        atomic_json(out/'publisher_sources.json', published_manifest)
    print(json.dumps(split_counts), flush=True)
    print('Training RF; calibration/validation/holdout excluded from fit...', flush=True)
    model = RandomForestClassifier(n_estimators=args.trees, max_depth=20, min_samples_leaf=3,
                                   class_weight='balanced_subsample', n_jobs=4, random_state=20260910)
    weights = None
    if args.balance_shapes:
        # Reweight observed URL shapes, never fabricate URLs or whitelist domains.
        train_rows = [r for r in rows if r['split'] == 'train']
        shape = lambda r: (r['label'], 'query' if urlsplit(r['url']).query else
                           'path' if urlsplit(r['url']).path not in {'', '/'} else 'root')
        counts = Counter(shape(r) for r in train_rows)
        weights = np.array([
            min(12.0, len(train_rows)/(len(counts)*counts[shape(r)]))
            * (4.0 if r['label'] == 0 and r['source'].startswith(('audited_','legacy_curated_','legacy_common_crawl_')) else 1.0)
            for r in train_rows
        ])
    model.fit(x[masks['train']], y[masks['train']], sample_weight=weights)
    raw = model.predict_proba(x)[:, 1]
    calibrator = LogisticRegression(C=1e6, solver='lbfgs', max_iter=1000)
    calibrator.fit(raw[masks['calibration']].reshape(-1,1), y[masks['calibration']])
    calibrated = calibrator.predict_proba(raw.reshape(-1,1))[:, 1]
    if calibrator.coef_[0,0] <= 0:
        raise ValueError('Calibration must be monotonic')
    scores = {'ml_only': calibrated}
    if args.formula == 'compare':
        scores['weighted_40_60'] = .4 * rules / 100 + .6 * calibrated
    validation = {}
    policies = {}
    v = masks['validation']
    for name, score in scores.items():
        warn, wm = threshold(y[v], score[v], .01)
        block, bm = threshold(y[v], score[v], .001, warn)
        policies[name] = (warn, block)
        validation[name] = {'warning': wm, 'blocking': bm}
    # Select once on validation; ties prefer the simpler model. Holdout is untouched.
    selected = max(scores, key=lambda n: (validation[n]['warning']['recall'], n == 'ml_only'))
    warn, block = policies[selected]
    h = masks['holdout']
    holdout = {name: {'warning': classification_metrics(y[h], score[h], policies[name][0]),
                       'blocking': classification_metrics(y[h], score[h], policies[name][1])} for name,score in scores.items()}
    old = joblib.load(BASE / 'model.pkl')
    old_schema = old.get('feature_schema_version', 'url-v3-www-canonical')
    old_x = np.asarray([feature_vector(r['url'], old_schema) for r in rows if r['split'] == 'holdout'])
    old_scores = legacy_scores(old, old_x, rules[h])
    old_holdout = {'warning': classification_metrics(y[h], old_scores, old['policy']['warning_threshold']/100),
                   'blocking': classification_metrics(y[h], old_scores, old['policy']['blocking_threshold']/100)}
    # Old training domains were forced into train; this is fresh-domain comparison.
    evaluation = {'train_rows': split_counts['train']['rows'], 'calibration_rows': split_counts['calibration']['rows'],
                  'validation_rows': split_counts['validation']['rows'], 'holdout_rows': split_counts['holdout']['rows'],
                  'development_rows': len(rows)-split_counts['holdout']['rows'],
                  'split_counts': split_counts, 'group_overlap': 0, 'refit_on_holdout': False}
    selected_metrics = holdout[selected]
    gate = (selected_metrics['warning']['false_positive_rate_upper_95'] <= .01
            and selected_metrics['blocking']['false_positive_rate_upper_95'] <= .001
            and all(selected_metrics[s]['recall'] >= old_holdout[s]['recall'] for s in ('warning','blocking')))
    report = {'created_at': datetime.now(timezone.utc).isoformat(), 'selected': selected,
              'selection_rule': 'Max warning recall on validation under Wilson FPR bounds; ties prefer ML-only',
              'risk_formula': FORMULAS[selected], 'dataset_rows': len(rows), 'uci_archive_rows': len(raw_rows),
              'sources': dict(Counter(r['source'] for r in rows)), 'invalid_rows': invalid, 'conflicting_urls_removed':len(conflicts),
              'uci_url': UCI_PAGE, 'license': 'UCI PhiUSIIL: CC BY 4.0; legacy feeds retain original source terms',
              'attribution': 'Arvind Prasad and Shalini Chandra (2024), PhiUSIIL, DOI:10.1016/j.cose.2023.103545',
              'archive_sha256': digest(archive), 'dataset_sha256': digest(out/'dataset.csv'),
              'mendeley_source': 'https://data.mendeley.com/datasets/c2gw7fy2j4/3' if args.mendeley else None,
              'mendeley_sha256': MENDELEY_HASH if args.mendeley else None,
              'shape_reweighting': args.balance_shapes,
              'publisher_sources_sha256': digest(out/'publisher_sources.json') if published_manifest else None,
              'publisher_label_limitations': 'Publisher labels are not independent project verification or a current-world safety guarantee.',
              'prior_experiment_domains_excluded_from_evaluation': str(args.prior_experiment) if args.prior_experiment else None,
              'external_holdout_source': 'Mendeley Web page phishing detection v3' if args.external_holdout else None,
              'external_source_key': external_key,
              'evaluation_design': evaluation, 'validation': validation, 'holdout': holdout,
              'previous_model_fresh_domain_holdout': old_holdout,
              'promotion_gate_passed': gate,
              'promotion_ready': False,
              'promotion_check': 'Requires regression and analyze_model_errors.py exposure/provenance checks',
              'previous_experiments': prior_inventory,
              'limitations': ['URL-only labels may be stale; downloaded today does not mean collected today.',
                             'Not a temporal split: publisher dates are preserved when available but are incomplete across sources.',
                             'Grouped mixed-source validation is not fully held-out external-source validation.',
                             'No guarantee on arbitrary websites; public-domain popularity is not a benign label.',
                             'Rules remain explanations, not independent measurements of risk.']}
    bundle = {'model': model, 'probability_calibrator': calibrator, 'fusion_model':None,
              'model_version':'url-risk-random-forest-2.0', 'policy_version':'simple-url-risk-2.0',
              'model_family':'random_forest', 'fusion_method': selected,
              'risk_formula':FORMULAS[selected], 'rule_weight':0.0 if selected == 'ml_only' else .4,
              'ml_weight':1.0 if selected == 'ml_only' else .6,
              'feature_names':FEATURE_NAMES, 'feature_schema_version':FEATURE_SCHEMA_VERSION,
              'calibration_version':'platt-disjoint-domains-1.0', 'probability_method':'heldout_platt_random_forest',
              'policy':{'warning_threshold':round(warn*100,4), 'blocking_threshold':round(block*100,4),
                        'warning_max_fpr':.01, 'blocking_max_fpr':.001},
              'cv_strategy':'Disjoint registered-domain Train / Calibration / Validation / Holdout; no test refit',
              'evaluation_design':evaluation, 'metrics':{'validation':validation[selected], 'independent_holdout':selected_metrics},
              'trained_at':report['created_at'], 'dataset_row_count':len(rows), 'dataset_sha256':report['dataset_sha256']}
    joblib.dump(bundle, out/'candidate.pkl', compress=3)
    (out/'evaluation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'selected':selected,'gate':gate,'new':selected_metrics,'old':old_holdout}, indent=2), flush=True)
    print('Candidate saved; production model has NOT been replaced.', flush=True)


if __name__ == '__main__':
    main()
