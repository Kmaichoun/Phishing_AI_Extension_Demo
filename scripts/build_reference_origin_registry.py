"""Freeze publisher-reference metadata; presence is not a safety label."""
import hashlib
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from model_registry import atomic_json, sha256


def origin(url):
    p = urlsplit(url)
    if p.scheme != 'https' or p.username or not p.hostname or p.port not in (None, 443):
        raise ValueError('Expected a standard HTTPS publisher origin')
    return 'https://' + p.hostname.lower().rstrip('.').encode('idna').decode('ascii')


def main():
    target = ROOT / 'backend/reference-origin-v1.json'
    assert not target.exists(), 'Registry is immutable; create a versioned new schema for changes'
    manifests = [ROOT / 'backend/data/quality-official-references-20261008/manifest.json',
                 ROOT / 'backend/data/host-context-20261008/official-references.manifest.json']
    entries = {}
    for path in manifests:
        doc = json.loads(path.read_text(encoding='utf-8'))
        for reference in doc['references']:
            if reference.get('error'): continue
            for url in (reference['seed'], reference['final']):
                entries.setdefault(origin(url), []).append({'manifest': str(path.relative_to(ROOT)),
                    'manifest_sha256': sha256(path), 'reference_url': url,
                    'html_sha256': reference['html_sha256'], 'retrieved_at': reference['retrieved_at']})
    url = 'https://support.google.com/gemini/answer/13275745?hl=en'
    request = urllib.request.Request(url, headers={'User-Agent': 'PhishRadar-Academic-URL-Research/2.0'})
    with urllib.request.urlopen(request, timeout=25) as response:
        final = response.geturl(); data = response.read(2_000_001)
        assert urlsplit(final).hostname == 'support.google.com'
        assert len(data) <= 2_000_000 and 'text/html' in response.headers.get('Content-Type', '')
    assert 'gemini.google.com' in data.decode('utf-8', errors='replace')
    evidence = ROOT / 'backend/data/reference-origin-evidence-20261008'
    evidence.mkdir(exist_ok=False)
    (evidence / 'google-gemini-help.html').write_bytes(data)
    entries['https://gemini.google.com'] = [{'reference_url': url, 'final': final,
        'html_sha256': hashlib.sha256(data).hexdigest(), 'retrieved_at': datetime.now(timezone.utc).isoformat(),
        'evidence': 'Google help identifies gemini.google.com as its Gemini web application; not a claim all content is safe'}]
    atomic_json(target, {'version': 'publisher-reference-origin-v1-20261008', 'origins': sorted(entries), 'evidence': entries,
        'meaning': 'Exact HTTPS origin present in bounded publisher-reference metadata. Not a benign label, whitelist decision, score cap, or content guarantee.',
        'limitations': ['Curated coverage; no inheritance to other subdomains.',
                        'Shared/user-controlled content and redirects can remain malicious on a referenced origin.',
                        'Metadata is frozen, dated, and must be reevaluated for a new schema version.']})
    print(json.dumps({'origins': len(entries), 'registry_sha256': sha256(target)}), flush=True)


if __name__ == '__main__': main()
