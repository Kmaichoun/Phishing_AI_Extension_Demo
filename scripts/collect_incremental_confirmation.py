"""Freeze two uninspected publisher shards without touching destination URLs."""
import csv
import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from urllib.parse import urlsplit
import collect_host_context_data as collect
from model_registry import atomic_json, sha256
from domain_parts import domain_parts
import pyarrow.parquet as pq

OUT = collect.ROOT / 'backend/data/incremental-confirmation-20261008'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--round',type=int,choices=[1,2],default=1);args=parser.parse_args()
    out=collect.ROOT/'backend/data/incremental-confirmation-round2-20261008' if args.round==2 else OUT
    shards=(2,40) if args.round==2 else (1,39)
    out.mkdir(exist_ok=False)
    collect.OUT = out  # include ALL previous source/test CSVs in the exposure audit
    exposed, records = collect.historical_groups()
    listing = json.loads(collect.download(f'https://api.github.com/repos/{collect.REPO}/contents/urls_without_dns?ref={collect.REV}'))
    metas = [listing[i] for i in shards]
    assert sum(m['size'] for m in metas) < 50_000_000
    candidates, files, conflicts = {}, [], set()
    for meta in metas:
        print('Downloading uninspected shard ' + meta['name'], flush=True)
        value = collect.download(f'https://raw.githubusercontent.com/{collect.REPO}/{collect.REV}/urls_without_dns/{meta["name"]}')
        assert len(value) == meta['size']
        assert hashlib.sha1(b'blob ' + str(len(value)).encode() + b'\0' + value).hexdigest() == meta['sha']
        path = out / meta['name']; path.write_bytes(value)
        table = pq.read_table(path, columns=['url', 'label', 'first_seen']).to_pydict()
        files.append({'name': meta['name'], 'sha256': sha256(path), 'git_blob': meta['sha']})
        for url, label, date in zip(table['url'], table['label'], table['first_seen']):
            if label not in ('benign', 'phishing'): continue
            try:
                parsed = urlsplit(url)
                if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or len(url) > 4096: continue
                group = domain_parts(parsed.hostname)[0]
            except (UnicodeError, ValueError): continue
            if group in exposed: continue
            y = int(label == 'phishing')
            if url in candidates and candidates[url]['label'] != y: conflicts.add(url)
            else: candidates[url] = {'url': url, 'label': y, 'group': group, 'source': 'deepurlbench-uninspected-shards',
                'observed_at': date.isoformat() if hasattr(date, 'isoformat') else str(date or ''), 'split': 'holdout'}
    groups, counts, rows = set(), Counter(), []
    for url, row in sorted(candidates.items(), key=lambda kv: hashlib.sha256(kv[0].encode()).digest()):
        if url in conflicts or row['group'] in groups or counts[row['label']] >= 5000: continue
        groups.add(row['group']); counts[row['label']] += 1; rows.append(row)
    assert set(counts) == {0, 1} and min(counts.values()) >= 1000
    with (out / 'dataset.csv').open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    atomic_json(out / 'manifest.json', {'created_at': datetime.now(timezone.utc).isoformat(),
        'rows': len(rows), 'domains': len(groups), 'labels': dict(counts), 'csv_sha256': sha256(out / 'dataset.csv'),
        'files': files, 'revision': collect.REV, 'source': 'https://github.com/' + collect.REPO,
        'license': 'CC BY-NC 4.0', 'exposure_files': records, 'available_exposure_domains': len(exposed),
        'model_scores_read': False, 'prior_exposure_audit_complete': False, 'forward_temporal_test': False,
        'sampling': f'Fixed shards {shards}; exclude available exposed domains; one row/domain; SHA256 order; cap 5000/class.',
        'limitations': ['Historical publisher labels, not live independently reviewed labels.',
            'Original training_urls.csv missing: cannot guarantee full historical independence.',
            'Fixed shard subset and capped class prevalence; not a production population.']})
    print(json.dumps({'rows': len(rows), 'labels': dict(counts), 'domains': len(groups)}), flush=True)


if __name__ == '__main__': main()
