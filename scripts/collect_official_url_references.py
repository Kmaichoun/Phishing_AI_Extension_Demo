"""Small current official-link reference set, not a general security benchmark.

Fetch only listed official pages; harvest same-host HTTPS links without visiting
them. Exclude nested destinations/user-generated hosts. Record evidence honestly.
"""
import csv
import hashlib
import json
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, urljoin, urldefrag, unquote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from domain_parts import domain_parts
from model_registry import atomic_json, sha256
OUT = ROOT / 'backend/data/host-context-20261008'
SEEDS = [
    'https://support.google.com/accounts/answer/185839',
    'https://accounts.google.com/',
    'https://www.microsoft.com/en-us/',
    'https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-auth-code-flow',
    'https://www.facebook.com/help/',
    'https://www.youtube.com/',
    'https://www.ku.ac.th/th',
    'https://www.chula.ac.th/',
]


class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.links = []
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.links.extend(v for k, v in attrs if k == 'href' and v)


def fetch(seed):
    try:
        req = urllib.request.Request(seed, headers={'User-Agent': 'PhishRadar-Academic-URL-Research/2.0'})
        with urllib.request.urlopen(req, timeout=20) as response:
            final = response.geturl(); data = response.read(2_000_001)
            if len(data) > 2_000_000 or 'text/html' not in response.headers.get('Content-Type', ''):
                raise ValueError('Not bounded HTML')
        if domain_parts(urlsplit(final).hostname)[0] != domain_parts(urlsplit(seed).hostname)[0]:
            raise ValueError('Cross-domain redirect excluded')
        parser = Links(); parser.feed(data.decode('utf-8', errors='replace'))
        host = urlsplit(final).hostname
        candidates = set([final])
        for href in parser.links:
            url = urldefrag(urljoin(final, href))[0]
            parsed = urlsplit(url)
            if (parsed.scheme == 'https' and parsed.hostname == host and not parsed.username
                    and len(url) <= 2048 and 'http' not in unquote(parsed.query).lower()
                    and not parsed.path.lower().endswith(('.exe', '.zip', '.pdf', '.apk'))):
                candidates.add(url)
        # Query-bearing references first, followed by original path links.
        candidates = sorted(candidates, key=lambda u: (not bool(urlsplit(u).query), hashlib.sha256(u.encode()).digest()))[:100]
        return {'seed': seed, 'final': final, 'html_sha256': hashlib.sha256(data).hexdigest(),
                'retrieved_at': datetime.now(timezone.utc).isoformat(), 'urls': candidates}
    except Exception as error:
        return {'seed': seed, 'error': str(error)}


def main():
    results = list(ThreadPoolExecutor(max_workers=3).map(fetch, SEEDS))
    rows, seen = [], set()
    for result in results:
        for url in result.get('urls', []):
            if url in seen: continue
            seen.add(url)
            rows.append({'url': url, 'label': '0', 'source': 'official_reference_20261008',
                'group': domain_parts(urlsplit(url).hostname)[0],
                'observed_at': result['retrieved_at'], 'time_precision': 'retrieval_timestamp',
                'publisher_split': 'development_reference',
                'label_evidence': 'HTTPS same-host link on selected official page: ' + result['final'],
                'split': 'train'})
    path = OUT / 'official-references.csv'
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    atomic_json(OUT / 'official-references.manifest.json', {'csv_sha256': sha256(path), 'rows': len(rows),
        'query_rows': sum(bool(urlsplit(r['url']).query) for r in rows),
        'references': [{k: v for k, v in r.items() if k != 'urls'} for r in results],
        'label_evidence': 'Selected official-host references; linked destinations not visited or independently security-vetted.',
        'use': 'Development reference examples only; never independent safety/accuracy evidence.',
        'limitations': ['Small selected-host sample; does not represent Internet prevalence.',
            'Official provenance is evidence for reference labeling, not a guarantee of page safety.']})
    print(json.dumps({'reference_rows': len(rows), 'query_rows': sum(bool(urlsplit(r['url']).query) for r in rows),
                      'failed_seeds': sum('error' in r for r in results)}), flush=True)


if __name__ == '__main__':
    main()
