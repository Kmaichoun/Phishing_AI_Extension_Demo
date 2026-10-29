"""Verify the running local demo, including a real local explanation."""
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/retrained-rf-query-20261005'


def request(path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request('http://127.0.0.1:8765' + path, data=data,
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=120) as response:
        return json.load(response)


health = request('/health')
urls = {
    'KU': 'https://www.ku.ac.th/th',
    'YouTube': 'https://www.youtube.com/watch?v=aQT2HyfmVbk',
    'Nike': 'https://www.nike.com/th/men?cp=43541719207_search_%7Cth%7CCore+Brand+-+Core+Brand+-+General+-+TH_TH%7CGOOGLE%7Cnike',
    'Google query shape probe': 'https://www.google.com/search?q=google&sxsrf=APpeQnsLpyYr3XOY1LTTV6HhYzoRAhC3dA%3A1791124961816&mstk=' + 'AUtExfBj3wGS5dzGDSTuEkrd3g1mCG_XIYnpbc-mdzS0'*10,
    'Facebook': 'https://web.facebook.com/',
    'PerfectWorld': 'https://nte.perfectworld.com/en/',
}
results = {name: request('/predict', {'url': url, 'rule_score': 0}) for name, url in urls.items()}
prediction = results['KU']
payload = {'url': urls['KU'], 'language': 'th', 'risk_score': prediction['final_score'],
           'random_forest_score': prediction['ml_score'], 'decision': prediction['decision'],
           'fusion_method': 'ml_only',
           'warning_threshold': prediction['warning_threshold'],
           'blocking_threshold': prediction['blocking_threshold'],
           'model_version': prediction['model_version']}
explanation = request('/explain', payload)
assert health['llm']['llm_ready'], health['llm']
assert explanation['ok'] and explanation['provider'] == 'ollama', explanation
cached = request('/explain', payload)
assert cached['cached'], cached
OUT.mkdir(parents=True, exist_ok=True)
(OUT / 'demo-live-check.json').write_text(json.dumps({'health': health, 'urls': urls, 'predictions': results}, ensure_ascii=False, indent=2), encoding='utf-8')
(OUT / 'llm-live-check.json').write_text(json.dumps({'first': explanation, 'cached': cached}, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'scores': {name: result['final_score'] for name, result in results.items()},
                  'llm': explanation, 'cache_verified': cached['cached']}, ensure_ascii=False))
