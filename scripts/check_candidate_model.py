"""Smoke/regression gate, separate from statistical holdout accuracy."""
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlencode
import argparse
import json
import sys
import joblib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'backend'))
import app
from build_dataset import calculate_rule_scores
from model_registry import REGRESSION_CODE, sha256, atomic_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('experiment', type=Path)
    args = parser.parse_args()
    candidate_hash = sha256(args.experiment/'candidate.pkl')
    bundle = joblib.load(args.experiment/'candidate.pkl')
    urls = [
        'https://web.facebook.com/',
        'https://www.facebook.com/',
        'https://m.facebook.com/',
        'https://sites.google.com/go.buu.ac.th/regservice-burapha-university/home',
        'https://www.ku.ac.th/th',
        'https://www.chula.ac.th/',
        'https://www.cmu.ac.th/',
        'https://www.kmitl.ac.th/',
        'https://www.su.ac.th/',
        'https://www.youtube.com/watch?v=AwKnraP_Wno',
        'https://www.youtube.com/results?search_query=cybersecurity',
        'https://www.google.com/',
        'https://www.google.com/search?' + urlencode({'q':'เว็บไซต์สำหรับค้นหาข้อมูลภาษาไทย',
            'sca_esv':'588441138e93f763','gs_lp':'Egdnd3Mtd2l6IjdQAgEgAMgCQIxjQAhgm'*8}),
        'https://github.com/openai/openai-python/issues/123',
        'https://en.wikipedia.org/wiki/Phishing',
    ]
    rules = calculate_rule_scores(urls)
    with patch.object(app, 'load_model_bundle', return_value=bundle):
        results = [app.predict(app.PredictRequest(url=url,rule_score=rule)) for url,rule in zip(urls,rules)]
    output = {'description':'Known benign URL-shape regressions; NOT an accuracy benchmark or independent test.',
              'candidate_sha256': candidate_hash,
              'code_sha256': {p: sha256(ROOT/p) for p in REGRESSION_CODE},
              'all_allow':all(r['decision']=='allow' for r in results),
              'results':[{'url':u,'rule_score':rule,'final_score':r['final_score'],'decision':r['decision']} for u,rule,r in zip(urls,rules,results)]}
    if sha256(args.experiment/'candidate.pkl') != candidate_hash:
        raise RuntimeError('Candidate changed during regression test')
    atomic_json(args.experiment/'regression.json', output)
    evaluation_path = args.experiment/'evaluation.json'
    evaluation = json.loads(evaluation_path.read_text(encoding='utf-8'))
    evaluation['regression_gate_passed'] = output['all_allow']
    # Full promotion also needs provenance, exposure and confidence-bound checks.
    evaluation['promotion_ready'] = False
    evaluation['promotion_check'] = 'Run analyze_model_errors.py, then manage_model.py check'
    atomic_json(evaluation_path, evaluation)
    print(json.dumps(output,ensure_ascii=True,indent=2))
    if not output['all_allow']:
        raise SystemExit('Do not promote: known benign regressions still fail')


if __name__ == '__main__':
    main()
