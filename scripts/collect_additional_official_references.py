"""Current bounded official-page references, not a blanket-domain whitelist."""
import csv
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from domain_parts import domain_parts
from model_registry import atomic_json, sha256
from collect_official_url_references import fetch

OUT = ROOT / 'backend/data/quality-official-references-20261008'
SEEDS = [
    'https://web.facebook.com/', 'https://m.facebook.com/', 'https://www.facebook.com/help/',
    'https://accounts.google.com/', 'https://support.google.com/accounts/',
    'https://login.microsoftonline.com/', 'https://account.microsoft.com/',
    'https://learn.microsoft.com/en-us/entra/', 'https://login.yahoo.com/',
    'https://account.apple.com/', 'https://support.apple.com/',
    'https://github.com/login', 'https://docs.github.com/en',
    'https://www.wikipedia.org/', 'https://en.wikipedia.org/wiki/Phishing',
    'https://www.buu.ac.th/', 'https://www.ku.ac.th/th', 'https://www.chula.ac.th/',
    'https://www.mahidol.ac.th/', 'https://www.kmitl.ac.th/', 'https://www.cmu.ac.th/',
    'https://www.kasikornbank.com/th/', 'https://www.scb.co.th/th/personal-banking.html',
    'https://www.bangkokbank.com/th-TH', 'https://www.bot.or.th/th/home.html',
    'https://www.rd.go.th/', 'https://www.thaipbs.or.th/',
]


def main():
    OUT.mkdir(exist_ok=False)
    with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(fetch, SEEDS))
    rows, seen = [], set()
    for result in results:
        for url in result.get('urls', []):
            if url in seen: continue
            seen.add(url)
            rows.append({'url': url, 'label': '0', 'source': 'official_reference_quality_20261008',
                'group': domain_parts(urlsplit(url).hostname)[0], 'observed_at': result['retrieved_at'],
                'time_precision': 'retrieval_timestamp',
                'label_evidence': 'Selected official HTTPS page or same-host href: ' + result['final']})
    assert rows
    path = OUT / 'references.csv'
    with path.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    atomic_json(OUT / 'manifest.json', {'csv_sha256': sha256(path), 'rows': len(rows),
        'query_rows': sum(bool(urlsplit(r['url']).query) for r in rows),
        'subdomain_rows': sum((urlsplit(r['url']).hostname or '') != r['group'] for r in rows),
        'references': [{k: v for k, v in r.items() if k != 'urls'} for r in results],
        'use': 'Selected development references; not independent safety or accuracy evidence.',
        'limitations': ['Selection bias: curated official hosts, not representative of Internet.',
            'Only seed pages fetched. Extracted destinations not independently reviewed.',
            'No synthetic URL variants; no domain-level safety labels or score exceptions.']})
    print(json.dumps({'rows': len(rows), 'failed_seeds': sum('error' in r for r in results)}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
