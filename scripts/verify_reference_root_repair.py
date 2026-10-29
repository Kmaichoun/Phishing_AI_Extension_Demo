"""Verify the evaluated repair through the operating local and public APIs.

Only sends URL strings to this project's predictor; never visits destinations.
"""
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
import joblib
import numpy as np
from feature_extractor import feature_vector
from model_registry import atomic_json, sha256

EXPERIMENT = ROOT / 'backend/data/simple_reference_root_sparse_repair_20261008'
OUTPUT = ROOT / 'output/reference-root-repair-20261008'
PUBLIC = 'https://phish-radar.taila97307.ts.net'
PROBES = [
    'https://web.facebook.com/',
    'https://web.facebook.com/?locale=th_TH&_rdc=1&_rdr#',
    'https://gemini.google.com/',
    'https://gemini.google.com/?hl=th',
    'https://www.facebook.com/',
    'https://m.facebook.com/',
    'https://sites.google.com/go.buu.ac.th/regservice-burapha-university/home',
    'https://www.ku.ac.th/th',
]
OUTSIDE_CONTEXT = [
    'https://gemini.google.com.evil.example/',
    'https://gemini-google.com/',
    'https://gemini.google.com@evil.example/',
    'https://unlisted.google.com/',
    'http://gemini.google.com/',
    'https://gemini.google.com:444/',
    'https://gemini.google.com/share/abc',
    'https://gemini.google.com/?url=https://evil.example/login',
    'https://web.facebook.com/?password=x',
    'https://gemini.google.com/?access_token=x',
    'https://gemini.google.com/?clientId=x&redirectUri=https%3A%2F%2Fevil.example%2F',
]
PROTECTED_TRAINING_POSITIVE = 'https://login.yahoo.com/?.intl=nz'


def probability(bundle, url):
    x = [feature_vector(url, bundle['feature_schema_version'])]
    raw = bundle['model'].predict_proba(x)[0, list(bundle['model'].classes_).index(1)]
    calibrator = bundle['probability_calibrator']
    return float(calibrator.predict_proba([[raw]])[0, list(calibrator.classes_).index(1)])


def request(base, endpoint, data=None):
    req = urllib.request.Request(base + endpoint,
        data=json.dumps(data).encode('utf-8') if data is not None else None,
        headers={'Content-Type': 'application/json'} if data is not None else {})
    with urllib.request.urlopen(req, timeout=35) as stream:
        return json.load(stream)


def main():
    evaluation = json.loads((EXPERIMENT / 'evaluation.json').read_text(encoding='utf-8'))
    authorization = json.loads((ROOT / 'backend/model-demo-authorization.json').read_text(encoding='utf-8'))
    assert evaluation['measured_gate_passed']
    assert sha256(ROOT / 'backend/model.pkl') == evaluation['candidate_sha256']
    assert sha256(Path(authorization['backup'])) == evaluation['baseline_sha256']
    candidate = joblib.load(ROOT / 'backend/model.pkl')
    baseline = joblib.load(authorization['backup'])
    controls = []
    for url in OUTSIDE_CONTEXT + [PROTECTED_TRAINING_POSITIVE]:
        x = feature_vector(url, candidate['feature_schema_version'])
        if url != PROTECTED_TRAINING_POSITIVE:
            assert x[-1] == 0, url
        old, new = probability(baseline, url), probability(candidate, url)
        np.testing.assert_allclose(new, old, rtol=0, atol=1e-12, err_msg=url)
        controls.append({'url': url, 'baseline_score': old * 100,
                         'candidate_score': new * 100, 'score_preserved': True})
    checks = {}
    for name, base in [('local', 'http://127.0.0.1:8765'), ('public', PUBLIC)]:
        health = request(base, '/health')
        scans = []
        for url in PROBES:
            result = request(base, '/predict', {'url': url, 'rule_score': 0})
            expected = probability(candidate, url)
            assert result['model_version'] == candidate['model_version']
            assert result['feature_schema_version'] == candidate['feature_schema_version']
            assert result['model_status'] == 'ready'
            assert result['fusion_method'] == 'ml_only'
            assert result['production_ready'] is False
            assert result['warning_threshold'] == 60 and result['blocking_threshold'] == 80
            assert result['decision'] == 'allow'
            assert result['final_score'] == round(expected * 100)
            scans.append({'url': url, 'baseline_score': round(probability(baseline, url) * 100),
                          'final_score': result['final_score'], 'decision': result['decision'],
                          'model_version': result['model_version'], 'model_status': result['model_status']})
        checks[name] = {'health': health, 'scans': scans}
    atomic_json(OUTPUT / 'after-live.json', {
        'verified_at': datetime.now(timezone.utc).isoformat(),
        'active_sha256': evaluation['candidate_sha256'], 'checks': checks,
        'unchanged_controls': controls, 'production_ready': False,
    })
    print(json.dumps({'local': checks['local']['scans'], 'public': checks['public']['scans'],
                      'unchanged_controls': len(controls), 'passed': True}, indent=2))


if __name__ == '__main__':
    main()
