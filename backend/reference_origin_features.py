"""Exact-origin publisher metadata used as a learned model input only."""
import hashlib
import json
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit
REGISTRY_PATH = Path(__file__).resolve().with_name('reference-origin-v1.json')


@lru_cache(maxsize=1)
def registry():
    data = REGISTRY_PATH.read_bytes()
    doc = json.loads(data)
    if doc['version'] != 'publisher-reference-origin-v1-20261008':
        raise ValueError('Unknown reference-origin feature version; retrain the model')
    return frozenset(doc['origins']), hashlib.sha256(data).hexdigest()


def reference_origin_match(url):
    p = urlsplit(url)
    try:
        if p.scheme != 'https' or not p.hostname or p.port not in (None, 443): return 0.
    except ValueError:
        return 0.
    host = p.hostname.lower().rstrip('.').encode('idna').decode('ascii')
    return float('https://' + host in registry()[0])
