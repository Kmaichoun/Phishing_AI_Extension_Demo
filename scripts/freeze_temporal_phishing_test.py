"""Freeze recent verified PhishTank rows before evaluating the chosen model.

Single-class diagnostic: estimates phishing recall only, never overall FPR.
Does not visit phishing destinations or add this snapshot to training.
"""
import csv
import gzip
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
import app
from collect_host_context_data import historical_groups, OUT
from domain_parts import domain_parts
from model_registry import atomic_json, sha256


def main():
    if (OUT / 'temporal-phishing-test.csv').exists():
        raise ValueError('Temporal test already frozen; do not overwrite')
    baseline = app.load_model_bundle()
    cutoff = datetime.fromisoformat(baseline['trained_at'])
    snapshot = OUT / 'phishtank-online-valid.csv.gz'
    with gzip.open(snapshot, 'rt', encoding='utf-8', newline='') as f:
        data = list(csv.DictReader(f))
    exposed, records = historical_groups()
    rows, seen, counts = [], set(), Counter()
    for row in sorted(data, key=lambda r: r['submission_time'], reverse=True):
        if row['verified'] != 'yes' or row['online'] != 'yes':
            counts['not_verified_online'] += 1; continue
        submission = datetime.fromisoformat(row['submission_time'])
        if not cutoff < submission <= datetime.now(timezone.utc):
            counts['outside_time_window'] += 1; continue
        parsed = urlsplit(row['url'])
        if parsed.scheme not in ('http', 'https') or not parsed.hostname:
            counts['unsupported_url'] += 1; continue
        group = domain_parts(parsed.hostname)[0]
        if group in exposed or group in seen:
            counts['exposed_or_repeated_domain'] += 1; continue
        seen.add(group)
        rows.append({'url': row['url'], 'label': '1', 'source': 'phishtank_verified_online_20261008',
            'group': group, 'split': 'temporal_diagnostic', 'observed_at': row['submission_time'],
            'verification_time': row['verification_time'], 'phish_id': row['phish_id'],
            'label_evidence': row['phish_detail_url']})
    path = OUT / 'temporal-phishing-test.csv'
    with path.open('w', encoding='utf-8', newline='') as f:
        fields = list(rows[0]) if rows else ['url', 'label', 'group']
        writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    atomic_json(OUT / 'temporal-phishing-test.manifest.json', {'rows': len(rows), 'domains': len(seen),
        'source': 'https://data.phishtank.com/data/online-valid.csv.gz',
        'documentation': 'https://phishtank.net/developer_info.php',
        'snapshot_sha256': sha256(snapshot), 'csv_sha256': sha256(path),
        'cutoff': cutoff.isoformat(), 'frozen_at': datetime.now(timezone.utc).isoformat(),
        'excluded': dict(counts), 'available_exposure_files': records,
        'limitation': 'Phishing-only temporal diagnostic, one URL per available-unseen domain; no benign FPR estimate. Original training file missing; prior exposure incomplete.'})
    print(json.dumps({'temporal_test_rows': len(rows), 'cutoff': cutoff.isoformat(), 'excluded': dict(counts)}), flush=True)


if __name__ == '__main__':
    main()
