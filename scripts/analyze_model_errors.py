"""Offline error slices + provenance/exposure audit. Never opens dataset websites."""
from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
import joblib
import numpy as np
from feature_extractor import FEATURE_NAMES, FEATURE_SCHEMA_VERSION, feature_vector
from model_registry import ARTIFACTS, DATA, SCORE_CODE, REGRESSION_CODE, atomic_json, counts_metrics, experiment_path, gate_checks, read_json, sha256
from train_simple_model import group, legacy_scores


def shape(url):
    parsed = urlsplit(url)
    return 'query' if parsed.query else 'path' if parsed.path not in ('', '/') else 'root'


def score_bundle(bundle, x, rules):
    if bundle.get('fusion_method') not in {'ml_only', 'weighted_40_60'}:
        return legacy_scores(bundle, x, rules) * 100
    model = bundle['model']
    p = model.predict_proba(x)[:, list(model.classes_).index(1)]
    calibrator = bundle.get('probability_calibrator')
    if calibrator is not None:
        p = calibrator.predict_proba(p.reshape(-1, 1))[:, list(calibrator.classes_).index(1)]
    return p*100 if bundle['fusion_method'] == 'ml_only' else .4*rules + .6*p*100


def analyze(name):
    path = experiment_path(name)
    evaluation = read_json(path/'evaluation.json')
    artifacts = {filename: sha256(path/filename) for filename in ARTIFACTS}
    if evaluation.get('publisher_sources_sha256'):
        artifacts['publisher_sources.json'] = sha256(path/'publisher_sources.json')
        if artifacts['publisher_sources.json'] != evaluation['publisher_sources_sha256']:
            raise ValueError('Publisher manifest checksum mismatch')
    if artifacts['dataset.csv'] != evaluation['dataset_sha256']:
        raise ValueError('Dataset checksum does not match evaluation')
    with (path/'dataset.csv').open(encoding='utf-8', newline='') as stream:
        rows = list(csv.DictReader(stream))
    split_groups = defaultdict(set)
    split_labels = defaultdict(set)
    for row in rows:
        actual_group = group(row['url'])
        if actual_group != row['group'] or row['label'] not in ('0', '1'):
            raise ValueError('Invalid label or stored domain group')
        split_groups[row['split']].add(actual_group)
        split_labels[row['split']].add(row['label'])
    splits = ['train', 'calibration', 'validation', 'holdout']
    overlap = set().union(*(split_groups[a] & split_groups[b] for i,a in enumerate(splits) for b in splits[i+1:]))
    seen, exposure = set(), {}
    production = ROOT/'backend'/'model.pkl'
    baseline_hash = sha256(production)
    baseline = joblib.load(production)
    legacy_path = next((p for p in [DATA/'training_urls.csv', *sorted(DATA.glob('simple_*/dataset.csv'))]
                        if p.is_file() and sha256(p) == baseline.get('dataset_sha256')), None)
    if legacy_path is None:
        raise ValueError('Cannot locate the exact production training dataset for exposure checks')
    with legacy_path.open(encoding='utf-8-sig', newline='') as stream:
        legacy = {group(r['url']) for r in csv.DictReader(stream)}
    exposure['production_training_domains'] = len(legacy & split_groups['holdout'])
    seen.update(legacy)
    inventory = {}
    for previous in sorted(DATA.glob('simple_*')):
        if not (previous/'dataset.csv').is_file():
            continue
        inventory[previous.name] = sha256(previous/'dataset.csv')
        if previous == path:
            continue
        prior_report = read_json(previous/'evaluation.json')
        if prior_report['created_at'] >= evaluation['created_at']:
            continue
        with (previous/'dataset.csv').open(encoding='utf-8', newline='') as stream:
            domains = {group(r['url']) for r in csv.DictReader(stream)}
        exposure[previous.name] = len(domains & split_groups['holdout'])
        seen.update(domains)
    holdout = [r for r in rows if r['split'] == 'holdout']
    if not holdout:
        raise ValueError('Missing holdout')
    # Only developer-created, local, trusted model artifacts may be loaded here.
    bundle = joblib.load(path/'candidate.pkl')
    if bundle.get('dataset_sha256') != artifacts['dataset.csv']:
        raise ValueError('Candidate was trained on a different dataset')
    if bundle.get('feature_schema_version') != FEATURE_SCHEMA_VERSION or bundle.get('feature_names') != FEATURE_NAMES:
        raise ValueError('Candidate feature contract is incompatible')
    if not 0 < bundle['policy']['warning_threshold'] <= bundle['policy']['blocking_threshold'] <= 100:
        raise ValueError('Invalid candidate thresholds')
    if baseline.get('dataset_sha256') != sha256(legacy_path):
        raise ValueError('Legacy training file no longer matches production; cannot certify unseen domains')
    print(f'{name}: scoring {len(holdout):,} holdout rows...', flush=True)
    x = np.asarray([feature_vector(r['url']) for r in holdout])
    rules = np.asarray([float(r['rule_score']) for r in holdout])
    labels = [int(r['label']) for r in holdout]
    scores = score_bundle(bundle, x, rules)
    old_scores = score_bundle(baseline, x, rules)
    external_indexes = [i for i,r in enumerate(holdout) if r.get('is_external') == '1']
    external_is_valid = bool(evaluation.get('external_source_key') and external_indexes
                             and {labels[i] for i in external_indexes} == {0,1}
                             and not any(r.get('is_external') == '1' and r['split'] != 'holdout' for r in rows)
                             and not seen & split_groups['holdout'])
    regression = read_json(path/'regression.json')
    result = {'schema_version': 1, 'created_at': datetime.now(timezone.utc).isoformat(),
              'artifacts': artifacts, 'experiment_inventory': inventory, 'baseline_sha256': baseline_hash,
              'legacy_dataset_sha256': sha256(legacy_path),
              'baseline_dataset': legacy_path.relative_to(DATA).as_posix(),
              'score_code': {p: sha256(ROOT/p) for p in SCORE_CODE},
              'model_version': bundle['model_version'], 'policy_version': bundle['policy_version'],
              'thresholds': bundle['policy'], 'holdout_rows': len(holdout),
              'regression_passed': (regression.get('candidate_sha256') == artifacts['candidate.pkl']
                                    and regression.get('code_sha256') == {p: sha256(ROOT/p) for p in REGRESSION_CODE}
                                    and regression.get('all_allow') is True and len(regression.get('results', [])) >= 6),
              'quality': {'group_overlap': len(overlap),
                          'all_splits_have_both_labels': all(split_labels[s] == {'0','1'} for s in splits),
                          'previously_seen_holdout_domains': len(seen & split_groups['holdout']),
                          'exposure': exposure,
                          'synthetic_rows': sum(r['source'].endswith(('_subdomain','_long_query')) for r in rows),
                          'unverified_benign_rows': sum(int(r['label']) == 0 and r['source'].startswith(('legacy_', 'audited_')) for r in rows),
                          'temporal_test_available': False},
              'candidate': {}, 'baseline': {}, 'external': {}, 'slices': [], 'examples': [],
              'limitations': ['Historical exploratory results, not proof of current-world accuracy.',
                             'This is not a temporal test; dates are missing or day-precision in some publisher sources.',
                             'Publisher labels, including ROR-sourced benign labels, were not independently reverified by this project.',
                             'FPR confidence bounds assume independent rows; domain correlations can weaken them.',
                             'Feedback and known-benign regression are not independent accuracy benchmarks.']}
    result['quality']['external_test_validated'] = external_is_valid
    result['external_source'] = evaluation.get('external_source_key')
    for stage in ('warning', 'blocking'):
        cut = bundle['policy'][stage+'_threshold']
        result['candidate'][stage] = counts_metrics(labels, scores, cut)
        result['baseline'][stage] = counts_metrics(labels, old_scores, baseline['policy'][stage+'_threshold'])
        if external_is_valid:
            external_labels = [labels[i] for i in external_indexes]
            result['external'][stage] = counts_metrics(external_labels, scores[external_indexes], cut)
            result['external'][stage+'_baseline'] = counts_metrics(external_labels, old_scores[external_indexes], baseline['policy'][stage+'_threshold'])
    indices = defaultdict(list)
    for i, row in enumerate(holdout):
        for dimension, value in [('source', row['source']), ('shape', shape(row['url'])),
                                 ('length', 'long (>200)' if len(row['url']) > 200 else 'short (<=200)'),
                                 ('encoded', 'percent-encoded' if '%' in row['url'] else 'not-encoded')]:
            indices[(dimension, value)].append(i)
    for (dimension, value), indexes in sorted(indices.items()):
        entry = {'dimension': dimension, 'value': value,
                 'domains': len({holdout[i]['group'] for i in indexes})}
        for stage in ('warning', 'blocking'):
            entry[stage] = counts_metrics([labels[i] for i in indexes], scores[indexes], bundle['policy'][stage+'_threshold'])
            entry[stage+'_baseline'] = counts_metrics([labels[i] for i in indexes], old_scores[indexes], baseline['policy'][stage+'_threshold'])
        result['slices'].append(entry)
    # Bounded examples without query strings, credentials, or active links.
    for kind in ('false_positive', 'false_negative'):
        for i, row in enumerate(holdout):
            wrong = (labels[i] == 0 and scores[i] >= bundle['policy']['warning_threshold']) if kind == 'false_positive' else (labels[i] == 1 and scores[i] < bundle['policy']['warning_threshold'])
            if wrong:
                result['examples'].append({'kind': kind, 'url_sha256': hashlib.sha256(row['url'].encode()).hexdigest(),
                                           'source': row['source'], 'shape': shape(row['url']),
                                           'rule_score': float(rules[i]), 'score': round(float(scores[i]), 4)})
            if sum(e['kind'] == kind for e in result['examples']) >= 10:
                break
    result['checks'] = gate_checks(result)
    result['promotion_ready'] = all(c['passed'] for c in result['checks'])
    if artifacts != {f: sha256(path/f) for f in artifacts} or baseline_hash != sha256(production):
        raise ValueError('Artifacts changed during analysis; rerun')
    atomic_json(path/'error_analysis.json', result)
    print(f'{name}: promotion_ready={result["promotion_ready"]}; warning={result["candidate"]["warning"]}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('experiments', nargs='+', help='Directory names, e.g. simple_v2 (not file paths)')
    for experiment in parser.parse_args().experiments:
        analyze(experiment)
