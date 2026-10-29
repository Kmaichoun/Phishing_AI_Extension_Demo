"""Exercise itemized explanations with local Ollama and real predictor results.

Destination URLs are only analysed as strings, never visited. This check never
calls a cloud LLM. Use --api after restarting the backend to test public access.
"""
import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from dotenv import dotenv_values
import llm_explainer as llm

OUT = ROOT / 'output/llm-detailed-20261009'
CASES = [
    'https://web.facebook.com/?locale=th_TH&_rdc=1&_rdr#',
    'https://gemini.google.com/?hl=th',
    'https://gemini.google.com/?clientId=demo',
    'https://paypal.com.login-security-check.example/login?url=https%3A%2F%2Fevil.example%2F&password=example-test-secret',
]
OUTPUT_FIELDS = {'risk_type', 'simple_explanation', 'user_advice', 'confidence_note',
                 'risk_reasons', 'reassuring_reasons'}


def validate_explanation(explanation, context):
    assert set(explanation) == OUTPUT_FIELDS, explanation
    score_context = context['score_context']
    assert explanation['risk_type'] == score_context['verdict']
    assert explanation['simple_explanation'].startswith(score_context['score_summary'])
    assert len(explanation['simple_explanation']) <= 540
    for field in ('risk_type', 'simple_explanation', 'user_advice', 'confidence_note'):
        assert isinstance(explanation[field], str) and explanation[field]
    for group, approved_group in (('risk_reasons', 'risk_facts'), ('reassuring_reasons', 'reassuring_facts')):
        rows = explanation[group]
        assert isinstance(rows, list) and len(rows) <= 4, rows
        assert bool(rows) == bool(score_context[approved_group]), (group, rows, score_context)
        approved_titles = {row['title'] for row in score_context[approved_group]}
        for row in rows:
            assert isinstance(row, dict) and set(row) == {'title', 'explanation'}, row
            assert isinstance(row['title'], str) and 0 < len(row['title']) <= 120, row
            assert isinstance(row['explanation'], str) and 0 < len(row['explanation']) <= 300, row
            assert row['title'] in approved_titles, row
    serialized = json.dumps(explanation, ensure_ascii=False)
    assert 'example-test-secret' not in serialized
    for unsupported in ('ปลอดภัยแน่นอน', 'ไม่มีความเสี่ยง', 'ตรวจเนื้อหาหน้าเว็บแล้ว', 'สแกนหน้าเว็บแล้ว'):
        assert unsupported not in serialized, serialized


def request(base, endpoint, body=None):
    req = urllib.request.Request(base + endpoint, data=json.dumps(body).encode('utf-8') if body is not None else None,
                                 headers={'Content-Type': 'application/json'} if body is not None else {})
    with urllib.request.urlopen(req, timeout=120) as stream:
        return json.load(stream)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--api', action='store_true')
    parser.add_argument('--limit', type=int, choices=range(1, len(CASES) + 1), default=len(CASES))
    args = parser.parse_args()
    saved = dotenv_values(ROOT / '.env')
    assert saved.get('LLM_PROVIDER') == 'ollama', 'This verifier only permits local Ollama'
    for key in ('LLM_PROVIDER', 'OLLAMA_BASE_URL', 'OLLAMA_MODEL'):
        os.environ[key] = saved[key]
    digest = hashlib.sha256((ROOT / 'backend/model.pkl').read_bytes()).hexdigest()
    rows = []
    for url in CASES[:args.limit]:
        analyzed = subprocess.run(['node', '-e',
            "const a=require('./extension/analyzer.js');process.stdout.write(JSON.stringify(a.analyzeUrl(process.argv[1])));", url],
            cwd=ROOT, capture_output=True, check=True, encoding='utf-8')
        rule = json.loads(analyzed.stdout)
        prediction = request('http://127.0.0.1:8765', '/predict', {'url': url, 'rule_score': rule['score']})
        reasons = [r for r in rule.get('reasons', []) if isinstance(r.get('points'), (int, float)) and math.isfinite(r['points'])][:8]
        payload = llm.ExplainRequest(
            url=url, rule_score=rule['score'], fuzzy_score=prediction.get('fuzzy_score'),
            random_forest_score=prediction.get('random_forest_score'), fusion_method=prediction.get('fusion_method'),
            risk_score=prediction['final_score'], risk_probability=prediction.get('risk_probability'),
            decision=prediction['decision'], warning_threshold=prediction['warning_threshold'], blocking_threshold=prediction['blocking_threshold'],
            model_version=prediction['model_version'], policy_version=prediction['policy_version'],
            feature_schema_version=prediction['feature_schema_version'],
            evidence_reasons=[{'title': r.get('label', ''), 'detail': r.get('detail', ''), 'points': r['points']} for r in reasons],
            reasons=[r.get('detail') or r.get('label', '') for r in reasons], language='th',
        )
        context = llm.build_llm_input(payload)
        assert 'example-test-secret' not in json.dumps(context, ensure_ascii=False)
        started = time.monotonic()
        local = request('http://127.0.0.1:8765', '/explain', payload.model_dump()) if args.api else llm.explain_with_llm(payload)
        elapsed = time.monotonic() - started
        result = {'url': url, 'score': prediction['final_score'], 'decision': prediction['decision'],
                  'rule_score': rule['score'], 'local': local, 'elapsed_seconds': round(elapsed, 3)}
        if args.api:
            result['public'] = request('https://phish-radar.taila97307.ts.net', '/explain', payload.model_dump())
        else:
            result['cached_repeat'] = llm.explain_with_llm(payload)
        for label in ('local', 'public' if args.api else 'cached_repeat'):
            response = result[label]
            assert response['ok'] and response['provider'] == 'ollama', response
            assert response['model'] == saved['OLLAMA_MODEL']
            explanation = response['llm']
            validate_explanation(explanation, context)
        assert result['public' if args.api else 'cached_repeat']['cached'] is True
        rows.append(result)
        OUT.mkdir(exist_ok=True, parents=True)
        (OUT / ('api-check.json' if args.api else 'direct-check.json')).write_text(json.dumps({
            'explanation_version': llm.EXPLANATION_VERSION, 'model_sha256': digest, 'checks': rows,
        }, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'url': llm.sanitize_url_for_llm(url)['url'], 'score': prediction['final_score'],
                          'rule_score': rule['score'], 'elapsed_seconds': round(elapsed, 3), 'llm': local['llm']}, ensure_ascii=False), flush=True)
    assert hashlib.sha256((ROOT / 'backend/model.pkl').read_bytes()).hexdigest() == digest
    print('Live itemized Ollama explanations and cache passed; model score artifact unchanged.', flush=True)


if __name__ == '__main__':
    main()
