"""Pinned, bounded DeepURLBench URL-only collection for noncommercial research.

Never connects to any dataset URL. Publisher labels are not live safety claims.
New holdout excludes all available historical domains; missing exposure is noted.
"""
import csv
import hashlib
import json
import sys
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'backend'), str(ROOT / 'tmp/research-deps')]
import pyarrow.parquet as pq
from domain_parts import domain_parts
from model_registry import atomic_json, sha256

REV = 'bf17c3fef854ff0ea40bcf93e373fc2c6dc30081'
REPO = 'deepinstinct-algo/DeepURLBench'
OUT = ROOT / 'backend/data/host-context-20261008'
SHARDS = [0, 19, 38, 57, 76]
FIELDS = ['url', 'label', 'source', 'group', 'split', 'observed_at', 'time_precision', 'publisher_split']


def download(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'PhishRadar-Academic-Research/2.0'})
    with urllib.request.urlopen(req, timeout=60) as r:
        value = r.read(25_000_001)
    if len(value) > 25_000_000:
        raise ValueError('Per-file download budget exceeded')
    return value


def historical_groups():
    groups, records = set(), []
    for path in sorted((ROOT / 'backend/data').rglob('*.csv')):
        if OUT in path.parents:
            continue
        with path.open(encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            names = reader.fieldnames or []
            if 'url' not in names:
                continue
            count = 0
            for row in reader:
                try:
                    group = row.get('group') or domain_parts(urlsplit(row['url']).hostname or '')[0]
                    if group:
                        groups.add(group)
                    count += 1
                except (ValueError, UnicodeError):
                    pass
            records.append({'path': str(path.relative_to(ROOT)), 'sha256': sha256(path), 'rows': count})
    return groups, records


def main():
    OUT.mkdir(exist_ok=False)
    raw_dir = OUT / 'publisher'; raw_dir.mkdir()
    listing = json.loads(download(f'https://api.github.com/repos/{REPO}/contents/urls_without_dns?ref={REV}'))
    selected = [listing[i] for i in SHARDS]
    if sum(meta['size'] for meta in selected) > 80_000_000:
        raise ValueError('Total download budget exceeded')
    rows, seen, conflicts = {}, set(), set()
    counts, files = Counter(), []
    for meta in selected:
        name = meta['name']
        print('Downloading publisher shard ' + name, flush=True)
        data = download(f'https://raw.githubusercontent.com/{REPO}/{REV}/urls_without_dns/{name}')
        if len(data) != meta['size'] or hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() != meta['sha']:
            raise ValueError('Pinned Git blob checksum mismatch')
        path = raw_dir / name; path.write_bytes(data)
        table = pq.read_table(path, columns=['url', 'label', 'first_seen']).to_pydict()
        files.append({'path': name, 'sha256': sha256(path), 'git_blob': meta['sha'], 'rows': len(table['url'])})
        for url, label, date in zip(table['url'], table['label'], table['first_seen']):
            counts[str(label)] += 1
            if label not in ('benign', 'phishing'):
                continue
            url = str(url).strip()
            try:
                parsed = urlsplit(url)
                if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or len(url) > 4096:
                    counts['unsupported_url'] += 1; continue
                group = domain_parts(parsed.hostname)[0]
            except (ValueError, UnicodeError):
                counts['invalid_url'] += 1; continue
            y = int(label == 'phishing')
            if url in rows and rows[url]['label'] != y:
                conflicts.add(url)
            elif url not in rows:
                rows[url] = {'url': url, 'label': y, 'group': group, 'source': 'deepurlbench-' + REV[:12],
                    'observed_at': date.isoformat() if hasattr(date, 'isoformat') else str(date or ''),
                    'time_precision': 'publisher_timestamp' if date is not None else 'unknown',
                    'publisher_split': 'unsplit'}
    for url in conflicts:
        rows.pop(url, None)
    print(json.dumps({'publisher_counts': counts, 'unique_binary_urls': len(rows), 'conflicts': len(conflicts)}), flush=True)
    exposed, exposure_files = historical_groups()
    # Fixed domain hashing freezes splits before any model evaluation. Keep all
    # previously seen domains in development; never assert temporal separation.
    domain_counts, label_counts, output = Counter(), Counter(), []
    for row in sorted(rows.values(), key=lambda r: hashlib.sha256(r['url'].encode()).digest()):
        group = row['group']
        if domain_counts[group] >= 10:
            continue
        bucket = int(hashlib.sha256(('host-context-20261008|' + group).encode()).hexdigest()[:8], 16) % 10
        split = 'train' if group in exposed or bucket < 6 else 'calibration' if bucket == 6 else 'validation' if bucket == 7 else 'holdout'
        # Bounded stratified sample, deterministically selected without model scores.
        if label_counts[(split, row['label'])] >= (30000 if split == 'train' else 10000):
            continue
        row['split'] = split
        output.append(row); domain_counts[group] += 1; label_counts[(split, row['label'])] += 1
    with (OUT / 'dataset.csv').open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS); writer.writeheader(); writer.writerows(output)
    holdout_groups = {r['group'] for r in output if r['split'] == 'holdout'}
    assert not holdout_groups & exposed
    splits = {s: dict(Counter(str(r['label']) for r in output if r['split'] == s))
              for s in ('train', 'calibration', 'validation', 'holdout')}
    atomic_json(OUT / 'manifest.json', {'source': 'https://github.com/' + REPO, 'revision': REV,
        'license': 'CC BY-NC 4.0', 'attribution': 'Deep Instinct Research Team, A New Dataset and Methodology for Malicious URL Classification (2025)',
        'collected_at': datetime.now(timezone.utc).isoformat(), 'csv_sha256': sha256(OUT / 'dataset.csv'),
        'files': files, 'publisher_counts': dict(counts), 'splits': splits,
        'exposure_files': exposure_files, 'available_historical_domains': len(exposed),
        'holdout_overlap_with_available_history': 0, 'sample_rule': 'Five fixed shards; SHA256 URL order; max 10 URLs per registered domain; per-class split caps',
        'label_evidence': 'Publisher benign/phishing labels; no independent live re-verification',
        'limitations': ['Historical data; not a live 2026 collection or forward-temporal test.',
            'Five-shard stratified subset, not the entire publisher population.',
            'Original backend/data/training_urls.csv is missing; full historical exposure unknown.',
            'Registered-domain disjoint against AVAILABLE records only; shared-hosting tenants conservatively grouped.']})
    print(json.dumps({'collected_rows': len(output), 'splits': splits, 'historical_domains': len(exposed)}), flush=True)


if __name__ == '__main__':
    main()
