"""Download publisher-labelled URL columns, never visit dataset destinations.

PhreshPhish is CC BY 4.0, Dalton et al. (2025), arXiv:2507.10854.
HTTP ranges avoid downloading the dataset's many gigabytes of HTML.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import pyarrow.parquet as pq
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[1]
REVISION = 'eabec4b7a66324b79cc8a0ad856d1731dc26fe1a'
REPO = 'https://huggingface.co/datasets/phreshphish/phreshphish'
URLPHISH_DOWNLOAD = 'https://data.mendeley.com/public-files/datasets/65z9twcx3r/files/0e9c55e4-9adb-43f5-8403-1bbd143ebdb6/file_downloaded'
URLPHISH_SHA = 'd68b3cd0648dcf9c775347416ad1a8995e8a025921fbe3871ca6158d4db3c3a1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def project_file(meta, cache):
    path = cache / (Path(meta['path']).stem + '.csv')
    record_path = path.with_suffix('.json')
    if path.exists() and record_path.exists():
        record = json.loads(record_path.read_text(encoding='utf-8'))
        if record['sha256'] == sha(path) and record['revision'] == REVISION:
            return record
    with RangeReader(f"{REPO}/resolve/{REVISION}/{meta['path']}", meta['size']) as stream:
        parquet = pq.ParquetFile(stream)
        columns = parquet.read(columns=['url', 'label', 'date']).to_pydict()
        with path.with_suffix('.tmp').open('w', encoding='utf-8', newline='') as handle:
            writer = csv.writer(handle); writer.writerow(['url','label','observed_at'])
            for url, label, date in zip(columns['url'], columns['label'], columns['date']):
                if label not in {'benign', 'phish'}:
                    raise ValueError('Unexpected publisher label')
                writer.writerow([url, int(label == 'phish'), date.isoformat() if date else ''])
        path.with_suffix('.tmp').replace(path)
        record = {'file':meta['path'], 'revision':REVISION, 'rows':len(columns['url']),
                  'publisher_file_sha256':meta.get('lfs',{}).get('oid'),
                  'sha256':sha(path), 'transferred_bytes':stream.transferred,
                  'columns':['url','label','date'], 'whole_parquet_hash_verified':False}
        record_path.write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')
    print(f"Projected {meta['path']}: {record['rows']:,} URLs; {record['transferred_bytes']:,} bytes", flush=True)
    return record


def download_external(cache):
    path = cache/'urlphish-v1.csv'
    if not path.exists():
        with requests.get(URLPHISH_DOWNLOAD, timeout=(20,90), stream=True) as response:
            response.raise_for_status()
            with path.with_suffix('.tmp').open('wb') as handle:
                count = 0
                for chunk in response.iter_content(1024*1024):
                    count += len(chunk)
                    if count > 20_000_000: raise ValueError('External dataset exceeds expected size')
                    handle.write(chunk)
        path.with_suffix('.tmp').replace(path)
    if sha(path) != URLPHISH_SHA:
        raise ValueError('URL-Phish publisher checksum mismatch')
    return path


class RangeReader(io.RawIOBase):
    """Bounded, seekable HTTPS reader. Reject servers ignoring byte ranges."""
    def __init__(self, url, size):
        self.url, self.size, self.pos, self.transferred = url, size, 0, 0
        self.session = requests.Session()
        self.session.mount('https://', HTTPAdapter(max_retries=Retry(
            total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])))

    def readable(self): return True
    def seekable(self): return True
    def tell(self): return self.pos

    def seek(self, offset, whence=0):
        pos = offset if whence == 0 else self.pos + offset if whence == 1 else self.size + offset
        if pos < 0:
            raise ValueError('negative seek')
        self.pos = pos
        return pos

    def read(self, size=-1):
        size = min(self.size-self.pos, size if size >= 0 else self.size-self.pos)
        if size <= 0: return b''
        if size > 20_000_000 or self.transferred + size > 100_000_000:
            raise ValueError('Range exceeds URL-only transfer budget')
        start, end = self.pos, self.pos + size - 1
        # Unique range query avoids a CDN serving an earlier cached range.
        with self.session.get(self.url + f'?download=true&range={start}-{end}',
                              headers={'Range': f'bytes={start}-{end}', 'Accept-Encoding': 'identity'},
                              timeout=(20, 90), stream=True) as response:
            response.raise_for_status()
            if response.status_code != 206 or response.headers.get('Content-Range') != f'bytes {start}-{end}/{self.size}':
                raise ValueError('Server did not honor the exact byte range')
            data = response.raw.read(size + 1)
            if len(data) != size:
                raise ValueError('Incomplete or oversized byte range')
        self.pos += size
        self.transferred += size
        return data

    def readinto(self, buffer):
        data = self.read(len(buffer)); buffer[:len(data)] = data
        return len(data)

    def close(self):
        self.session.close()
        super().close()


def listing():
    response = requests.get(f'https://huggingface.co/api/datasets/phreshphish/phreshphish/tree/{REVISION}/data',
                            params={'limit': 1000}, timeout=40)
    response.raise_for_status()
    return response.json()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inspect', action='store_true')
    parser.add_argument('--output', type=Path, default=ROOT/'backend/data/cache/research-20260917')
    args = parser.parse_args()
    cache = args.output.resolve()
    if not args.inspect and (cache/'manifest.json').exists():
        manifest = json.loads((cache/'manifest.json').read_text(encoding='utf-8'))
        path = (cache/manifest['csv']).resolve()
        if path.parent != cache or sha(path) != manifest['csv_sha256']:
            raise ValueError('Completed collection changed; refusing to overwrite it')
        print(json.dumps({'cached_collection':str(cache/'manifest.json'), 'counts':manifest['counts'],
                          'notice':'Immutable collection reused; it is not a newly unseen dataset.'}), flush=True)
        return
    files = sorted((f for f in listing() if f['path'].startswith('data/train-')), key=lambda f:f['path'])
    for meta in files[:1] if args.inspect else []:
        with RangeReader(f"{REPO}/resolve/{REVISION}/{meta['path']}", meta['size']) as stream:
            parquet = pq.ParquetFile(stream)
            print(json.dumps({'file':meta['path'], 'size':meta['size'], 'rows':parquet.metadata.num_rows,
                              'schema':str(parquet.schema_arrow), 'sha256':meta.get('lfs',{}).get('oid')}), flush=True)
            if args.inspect:
                print('Metadata inspection only; no HTML or URL values printed.', flush=True)
    if args.inspect: return
    cache.mkdir(parents=True, exist_ok=True)
    records = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(project_file, meta, cache) for meta in files]
        for future in as_completed(futures): records.append(future.result())
    external = download_external(cache)
    sys.path.insert(0, str(ROOT/'backend'))
    from train_simple_model import group
    from build_dataset import normalized_url
    previous = [ROOT/'backend/data/training_urls.csv', *sorted((ROOT/'backend/data').glob('simple_*/dataset.csv'))]
    seen = set()
    for path in previous:
        with path.open(encoding='utf-8-sig', newline='') as handle:
            seen.update(group(r['url']) for r in csv.DictReader(handle))
    output = cache/'publisher-urls.csv'
    counts, excluded = Counter(), Counter()
    with output.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=['url','label','source','observed_at','time_precision','publisher_split'])
        writer.writeheader()
        for record in sorted(records, key=lambda r:r['file']):
            with (cache/(Path(record['file']).stem+'.csv')).open(encoding='utf-8', newline='') as stream:
                for row in csv.DictReader(stream):
                    writer.writerow(dict(row, source='phreshphish_train_v1_0_1', time_precision='day', publisher_split='train'))
                    counts['phreshphish_train_v1_0_1'] += 1
        with external.open(encoding='utf-8-sig', newline='') as stream:
            reader = csv.DictReader(stream)
            if not {'url','label'} <= set(reader.fieldnames or []): raise ValueError('Unexpected URL-Phish columns')
            for row in reader:
                if row['label'] not in {'0','1'}: raise ValueError('Unexpected URL-Phish label')
                url = normalized_url(row['url'])
                try: domain = group(url) if url else None
                except (ValueError, UnicodeError): domain = None
                if not domain:
                    excluded['invalid_external_url'] += 1; continue
                if domain in seen:
                    excluded['previously_seen_external_domain_rows'] += 1; continue
                writer.writerow(dict(url=url, label=row['label'], source='urlphish_v1',
                                     observed_at='', time_precision='unknown', publisher_split='external'))
                counts['urlphish_v1'] += 1
    manifest = {'created_at':datetime.now(timezone.utc).isoformat(), 'csv':output.name,
                'csv_sha256':sha(output), 'counts':dict(counts), 'excluded':dict(excluded),
                'previous_datasets':{str(p.relative_to(ROOT)):sha(p) for p in previous},
                'sources':{
                    'phreshphish_train_v1_0_1':{'url':REPO, 'revision':REVISION, 'license':'CC BY 4.0',
                        'attribution':'Thomas Dalton et al. (2025), arXiv:2507.10854',
                        'label_evidence':'Publisher HTML-URL phishing/benign labels; not independently reverified by this project',
                        'limitations':'Publisher removes benign URL query parameters (paper Appendix C.2); class-dependent preprocessing may bias URL-only detection.',
                        'methodology_url':'https://arxiv.org/html/2507.10854v1',
                        'time_semantics':'Publisher date, day precision; timezone not supplied',
                        'publisher_test_used':False, 'files':sorted(records,key=lambda r:r['file'])},
                    'urlphish_v1':{'url':'https://data.mendeley.com/datasets/65z9twcx3r/1', 'license':'CC BY 4.0',
                        'attribution':'Linh Dam Minh and Hung Tran Cong (2025), DOI:10.17632/65z9twcx3r.1',
                        'label_evidence':'Publisher labels: ROR-sourced benign and PhishTank phishing; not a current security verdict',
                        'limitations':'ROR provenance is not independent verification of current URL safety; historical/source-shift test only',
                        'time_semantics':'Per-URL observation time unavailable; never substitute retrieval date',
                        'download_url':URLPHISH_DOWNLOAD, 'sha256':URLPHISH_SHA}},
                'dataset_destinations_visited':False, 'html_downloaded':False,
                'transformations':['URL/label/date projection only', '0 benign / 1 phishing mapping',
                                   'Exclude previously exposed external domains before any scoring']}
    (cache/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'counts':dict(counts), 'excluded':dict(excluded), 'manifest':str(cache/'manifest.json')}), flush=True)


if __name__ == '__main__':
    main()
