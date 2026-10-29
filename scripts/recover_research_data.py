"""Recover attributed publisher URL data without pretending to recover old splits.

Only downloads URL/label/date columns. Publisher test rows remain quarantined;
this command neither trains a model nor visits any URL contained in the data.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from collect_research_urls import ROOT, REPO, REVISION, URLPHISH_SHA, download_external, listing, project_file, sha

sys.path.insert(0, str(ROOT / 'backend'))
from build_dataset import normalized_url
from domain_parts import domain_parts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'backend/data/recovered-20261004')
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.workers <= 8:
        parser.error('--workers must be between 1 and 8')
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    cache = out / 'publisher-columns'
    cache.mkdir(exist_ok=True)
    old_manifest = ROOT / 'backend/data/simple_v4/publisher_sources.json'
    previous = json.loads(old_manifest.read_text(encoding='utf-8'))
    expected = {r['file']: r['sha256'] for r in previous['sources']['phreshphish_train_v1_0_1']['files']}
    files = sorted((f for f in listing() if f['path'].startswith(('data/train-', 'data/test-'))), key=lambda f: f['path'])
    if not files or not any(f['path'].startswith('data/train-') for f in files):
        raise ValueError('Missing publisher partitions')
    records = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        pending = {pool.submit(project_file, meta, cache): meta for meta in files}
        for future in as_completed(pending):
            record = future.result()
            if record['file'] in expected and record['sha256'] != expected[record['file']]:
                raise ValueError('Recovered publisher projection differs from the historical hash')
            records.append(record)
    external = download_external(cache)
    records.sort(key=lambda row: row['file'])
    sources = previous['sources']
    fields = ['url', 'label', 'source', 'observed_at', 'time_precision', 'publisher_split']
    counts = Counter()
    outputs = {}
    for split, name in [('train', 'development-urls.csv'), ('test', 'quarantined-publisher-test.csv')]:
        path = out / name
        with path.with_suffix('.tmp').open('w', encoding='utf-8', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for record in records:
                if not record['file'].startswith('data/' + split + '-'):
                    continue
                with (cache / (Path(record['file']).stem + '.csv')).open(encoding='utf-8', newline='') as stream:
                    for row in csv.DictReader(stream):
                        source = 'phreshphish_' + split + '_v1_0_1'
                        writer.writerow(dict(row, source=source, time_precision='day', publisher_split=split))
                        counts[source + '/label_' + row['label']] += 1
            if split == 'train':
                with external.open(encoding='utf-8-sig', newline='') as stream:
                    for row in csv.DictReader(stream):
                        if row['label'] not in {'0', '1'}:
                            raise ValueError('Unexpected URL-Phish label')
                        writer.writerow(dict(url=row['url'], label=row['label'], source='urlphish_v1',
                                             observed_at='', time_precision='unknown', publisher_split='train'))
                        counts['urlphish_v1/label_' + row['label']] += 1
        path.with_suffix('.tmp').replace(path)
        outputs[split] = {'csv': name, 'sha256': sha(path)}
    # Training candidate cleanup uses only development rows, never reserved test data.
    stats, candidates, conflicts, rejected = Counter(), {}, set(), []
    with (out / outputs['train']['csv']).open(encoding='utf-8', newline='') as handle:
        for row in csv.DictReader(handle):
            try:
                url = normalized_url(row['url'])
                if not url:
                    raise ValueError('Invalid URL')
                host = urlsplit(url).hostname
                if not host:
                    raise ValueError('Missing hostname')
                domain = domain_parts(host)[0]
                if not domain:
                    raise ValueError('Missing domain')
            except (ValueError, UnicodeError, KeyError):
                stats['invalid'] += 1
                stats['rejected/' + row['source'] + '/label_' + row['label']] += 1
                rejected.append(dict(row, reason='Not supported by current HTTP(S) URL normalizer or domain parser; not a phishing verdict'))
                continue
            if url in candidates:
                stats['duplicate_normalized_urls'] += 1
                if candidates[url]['label'] != row['label']:
                    conflicts.add(url)
            else:
                candidates[url] = dict(row, url=url, group=domain)
    for url in conflicts:
        candidates.pop(url, None)
    stats['conflicting_normalized_urls_removed'] = len(conflicts)
    clean = out / 'development-deduplicated.csv'
    education = out / 'education-review-candidates.csv'
    rejects = out / 'development-review-required.csv'
    with rejects.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields + ['reason'])
        writer.writeheader()
        writer.writerows(rejected)
    with clean.open('w', encoding='utf-8', newline='') as handle, education.open('w', encoding='utf-8', newline='') as edu:
        writer = csv.DictWriter(handle, fieldnames=fields + ['group'])
        subset = csv.DictWriter(edu, fieldnames=fields + ['group'])
        writer.writeheader(); subset.writeheader()
        for row in candidates.values():
            writer.writerow(row)
            stats['clean_label_' + row['label']] += 1
            domain = row['group']
            # A naming-pattern review queue, not a safety label or whitelist.
            if domain.endswith(('.ac.th', '.edu', '.ac.uk')) or '.edu.' in domain:
                subset.writerow(row)
                stats['education_pattern_label_' + row['label']] += 1
    missing = [str(p.relative_to(ROOT)) for p in [ROOT / 'backend/data/training_urls.csv',
               *(p.parent / 'dataset.csv' for p in sorted((ROOT / 'backend/data').glob('simple_*/evaluation.json')))] if not p.is_file()]
    development_manifest = {
        'csv': clean.name, 'csv_sha256': sha(clean),
        'purpose': 'Development only. All prior experimental sources are treated as exposed.',
        'production_ready': False, 'prior_exposure_audit_complete': not missing,
        'sources': {
            'phreshphish_train_v1_0_1': dict(sources['phreshphish_train_v1_0_1'],
                limitations='Publisher strips benign query parameters; URL-only source bias is possible.',
                files=[r for r in records if r['file'].startswith('data/train-')]),
            'urlphish_v1': dict(sources['urlphish_v1'],
                limitations='Previously used in v4 holdout; development only. ROR origin does not prove current safety.')},
    }
    (out / 'development-publisher-manifest.json').write_text(json.dumps(development_manifest, indent=2) + '\n', encoding='utf-8')
    manifest = {
        'created_at': datetime.now(timezone.utc).isoformat(),
        'purpose': 'Recovery and development data; NOT recovered original training/evaluation splits',
        'production_ready': False, 'training_performed': False, 'test_scored': False,
        'prior_exposure_audit_complete': not missing, 'missing_original_files': missing,
        'counts': dict(counts), 'development_cleanup': dict(stats),
        'outputs': outputs,
        'development_deduplicated': {'csv': clean.name, 'sha256': sha(clean)},
        'development_review_required': {'csv': rejects.name, 'sha256': sha(rejects),
            'limitation': 'Missing schemes are retained here, not silently replaced with HTTPS. Exclusions can introduce class/source bias.'},
        'education_review_candidates': {'csv': education.name, 'sha256': sha(education),
            'limitation': 'Publisher labels plus domain naming filter; not independently verified benign websites, not representative of Thai schools'},
        'historical_train_projection_hashes_matched': sum(r['file'] in expected for r in records),
        'sources': {
            'phreshphish': {'url': REPO, 'revision': REVISION, 'license': 'CC BY 4.0; anti-phishing research',
                'attribution': sources['phreshphish_train_v1_0_1']['attribution'],
                'labels': 'benign=0, phish=1; publisher supplied', 'files': records,
                'limitations': 'Benign query parameters were removed by publisher; URL-only models may learn source preprocessing artifacts.'},
            'urlphish': {'url': sources['urlphish_v1']['url'], 'license': sources['urlphish_v1']['license'],
                'attribution': sources['urlphish_v1']['attribution'], 'raw_sha256': URLPHISH_SHA,
                'labels': '0 benign, 1 phishing; publisher supplied',
                'limitations': 'Previously used in v4 evaluation: now development only. Observation dates unknown. ROR origin is not proof of current safety.'}},
        'limitations': ['Publisher test stays quarantined until prior exposure and domain overlap are audited.',
                       'Retrieval date is not an observation date.',
                       'No claim of improved accuracy or reduced FPR follows from collection alone.',
                       'Original training_urls.csv and simple_v*/dataset.csv cannot be reconstructed exactly from publisher data alone.'],
        'dataset_destinations_visited': False, 'html_columns_downloaded': False,
    }
    (out / 'recovery-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'manifest': str(out / 'recovery-manifest.json'), 'counts': dict(counts), 'cleanup': dict(stats)}), flush=True)


if __name__ == '__main__':
    main()
