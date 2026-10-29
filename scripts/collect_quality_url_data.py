"""URL-only UCI ingestion with explicit inverted labels and conflict quarantine.

Publisher URLs are never visited. Existing test domains are excluded from
development. New heldout domains exclude all locally recorded prior exposure.
"""
import csv
import hashlib
import io
import json
import sys
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from domain_parts import domain_parts
from model_registry import atomic_json, sha256
from train_host_context_candidate import read
import collect_host_context_data as history

OUT = ROOT / 'backend/data/quality-augmentation-20261008'
SOURCE = ROOT / 'backend/data/simple_host_context_20261008/dataset.csv'
URL = 'https://archive.ics.uci.edu/static/public/967/phiusiil%2Bphishing%2Burl%2Bdataset.zip'
FIELDS = ['url', 'label', 'source', 'group', 'split', 'observed_at', 'time_precision', 'label_evidence']


def canonical(value):
    p = urlsplit(value.strip())
    if p.scheme not in ('http', 'https') or not p.hostname:
        raise ValueError('Not an absolute HTTP(S) URL')
    host = p.hostname.encode('idna').decode('ascii').lower()
    port = p.port
    if ':' in host: host = '[' + host + ']'
    userinfo = p.netloc.rsplit('@', 1)[0] + '@' if '@' in p.netloc else ''
    netloc = userinfo + host + (f':{port}' if port and not (p.scheme == 'https' and port == 443 or p.scheme == 'http' and port == 80) else '')
    return urlunsplit((p.scheme, netloc, p.path or '/', p.query, p.fragment))


def mapped_label(value):
    if value not in ('0', '1'):
        raise ValueError('Unsupported UCI label')
    return str(1 - int(value))  # UCI 1 legitimate; project 1 phishing.


def main():
    OUT.mkdir(exist_ok=True)
    assert not (OUT / 'dataset.csv').exists(), 'Do not overwrite a completed collection'
    raw_path = OUT / 'publisher.zip'
    if raw_path.exists():
        data = raw_path.read_bytes()
    else:
        req = urllib.request.Request(URL, headers={'User-Agent': 'PhishRadar-Academic-Research/2.0'})
        with urllib.request.urlopen(req, timeout=60) as response:
            data = response.read(20_000_001)
        assert len(data) <= 20_000_000
        raw_path.write_bytes(data)
    with ZipFile(io.BytesIO(data)) as z:
        names = [n for n in z.namelist() if n.endswith('.csv')]
        assert len(names) == 1 and z.getinfo(names[0]).file_size <= 65_000_000
        raw = list(csv.DictReader(io.StringIO(z.read(names[0]).decode('utf-8-sig'))))
    assert len(raw) == 235795, 'Publisher data changed; review metadata before training'
    history.OUT = OUT
    exposed, exposure_files = history.historical_groups()
    prior = read(SOURCE)
    partitions = {r['group']: r['split'] for r in prior}
    assert all(partitions[r['group']] == r['split'] for r in prior)
    known = {}
    for r in prior:
        key = canonical(r['url'])
        known.setdefault(key, set()).add(r['label'])
    by_url, excluded, conflicts = {}, Counter(), set()
    for r in raw:
        try:
            key = canonical(r['URL']); label = mapped_label(r['label'])
            group = domain_parts(urlsplit(key).hostname)[0]
            if not group: raise ValueError('Missing registered domain')
        except (ValueError, UnicodeError, KeyError):
            excluded['invalid'] += 1; continue
        if key in known and known[key] != {label}:
            conflicts.add(key)
        if key in by_url and by_url[key]['label'] != label:
            conflicts.add(key)
        if key in by_url:
            excluded['duplicate'] += 1; continue
        by_url[key] = {'url': key, 'label': label, 'source': 'uci_phiusiil_2024', 'group': group,
            'observed_at': '', 'time_precision': 'unknown',
            'label_evidence': 'UCI PhiUSIIL publisher label; 1=legitimate mapped to project 0; not live safety verification'}
    conflict_rows = []
    for key in sorted(conflicts):
        conflict_rows.append({'url': key, 'prior_labels': '|'.join(sorted(known.get(key, set()))),
                              'incoming_label': by_url[key]['label'], 'action': 'quarantine all development rows for exact canonical URL'})
    clean_prior = [r for r in prior if canonical(r['url']) not in conflicts]
    addition, held = [], []
    for key, r in sorted(by_url.items(), key=lambda kv: hashlib.sha256(kv[0].encode()).digest()):
        if key in conflicts:
            excluded['conflicting_url'] += 1; continue
        if key in known:
            excluded['already_present'] += 1; continue
        if r['group'] in partitions:
            r['split'] = partitions[r['group']]
        elif r['group'] in exposed:
            excluded['prior_exposure_outside_development'] += 1; continue
        else:
            bucket = int.from_bytes(hashlib.sha256(('quality-uci-20261008|' + r['group']).encode()).digest()[:4], 'big') % 10
            r['split'] = 'train' if bucket < 7 else 'calibration' if bucket == 7 else 'validation' if bucket == 8 else 'holdout'
        (held if r['split'] == 'holdout' else addition).append(r)
    # One row per domain in untouched confirmation; selection never reads it.
    groups_seen, held_unique = set(), []
    for r in held:
        if r['group'] not in groups_seen:
            held_unique.append(r); groups_seen.add(r['group'])
    def write(path, rows, fields=FIELDS):
        with path.open('w', encoding='utf-8', newline='') as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore'); w.writeheader(); w.writerows(rows)
    write(OUT / 'incoming-development.csv', addition)
    write(OUT / 'confirmation.csv', held_unique)
    write(OUT / 'conflicts-review.csv', conflict_rows, ['url', 'prior_labels', 'incoming_label', 'action'])
    dev = clean_prior + addition
    groups = {s: {r['group'] for r in dev if r['split'] == s} for s in ('train', 'calibration', 'validation')}
    groups['holdout'] = groups_seen
    assert all(not groups[a] & groups[b] for i, a in enumerate(groups) for b in list(groups)[i+1:])
    write(OUT / 'dataset.csv', dev)
    manifest = {'retrieved_at': datetime.now(timezone.utc).isoformat(), 'publisher_url': URL,
        'publisher_page': 'https://archive.ics.uci.edu/dataset/967/phiusiil+phishing+url+dataset',
        'publisher_zip_sha256': sha256(raw_path), 'publisher_rows': len(raw),
        'license': 'CC BY 4.0', 'attribution': 'Prasad and Chandra (2024), PhiUSIIL, UCI; doi:10.1016/j.cose.2023.103545',
        'label_mapping': {'0': 'phishing/project 1', '1': 'legitimate/project 0'},
        'dataset_sha256': sha256(OUT / 'dataset.csv'), 'confirmation_sha256': sha256(OUT / 'confirmation.csv'),
        'prior_dataset_sha256': sha256(SOURCE), 'incoming_counts': dict(Counter(r['split']+'/'+r['label'] for r in addition)),
        'confirmation_counts': dict(Counter(r['label'] for r in held_unique)), 'conflicts': len(conflicts),
        'removed_prior_conflicting_rows': len(prior)-len(clean_prior), 'excluded': dict(excluded),
        'registered_domain_overlaps': 0, 'prior_exposure_files': exposure_files,
        'limitations': ['Historical 2024 publisher labels; individual observation dates unknown.',
            'No publisher phishing URLs visited; no independent manual label review of every URL.',
            'Missing original baseline training file leaves original exposure audit incomplete.',
            'New confirmation excludes all available prior domains, but is not forward-temporal.']}
    atomic_json(OUT / 'manifest.json', manifest)
    print(json.dumps({k: manifest[k] for k in ('publisher_rows', 'incoming_counts', 'confirmation_counts', 'conflicts', 'excluded')}), flush=True)


if __name__ == '__main__':
    main()
