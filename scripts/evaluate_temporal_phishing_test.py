"""Read-only, once-frozen post-selection phishing recall diagnostic."""
import csv
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
import app
import joblib
import numpy as np
from train_recovered_rf import scores, subgroup_metrics
from model_registry import sha256, atomic_json


def interval(success, n):
    z = 1.96; p = success / n
    mid = (p + z*z/(2*n)) / (1 + z*z/n)
    radius = z * np.sqrt(p*(1-p)/n + z*z/(4*n*n)) / (1 + z*z/n)
    return [float(mid-radius), float(mid+radius)]


def main():
    source = ROOT / 'backend/data/host-context-20261008'
    out = ROOT / 'backend/data/simple_host_context_20261008'
    selection = json.loads((out / 'selection.json').read_text(encoding='utf-8'))
    evaluation = json.loads((out / 'evaluation.json').read_text(encoding='utf-8'))
    manifest = json.loads((source / 'temporal-phishing-test.manifest.json').read_text(encoding='utf-8'))
    assert sha256(source / 'temporal-phishing-test.csv') == manifest['csv_sha256']
    assert sha256(out / 'candidate.pkl') == evaluation['candidate_sha256']
    assert sha256(app.MODEL_PATH) == selection['baseline_sha256']
    with (source / 'temporal-phishing-test.csv').open(encoding='utf-8', newline='') as f:
        rows = list(csv.DictReader(f))
    if not rows: raise ValueError('No recent available-unseen domains')
    y = np.ones(len(rows), dtype=np.int8)
    results = {}
    for name, bundle in [('baseline', app.load_model_bundle()), ('candidate', joblib.load(out / 'candidate.pkl'))]:
        p = scores(bundle, rows)
        results[name] = {key: {**subgroup_metrics(y, p, threshold),
            'recall_wilson_95': interval(int((p >= threshold).sum()), len(rows))}
            for key, threshold in [('warning', .6), ('blocking', .8)]}
    atomic_json(out / 'temporal-phishing-diagnostic.json', {'rows': len(rows), 'domains': len({r['group'] for r in rows}),
        'results': results, 'test_used_for_training_or_selection': False,
        'new_model_better_warning_recall': results['candidate']['warning']['recall'] >= results['baseline']['warning']['recall'],
        'limitation': 'Phishing-only recent-feed diagnostic, after baseline training date; no FPR/accuracy/calibration inference. Candidate official references were collected later, so this is not a strict forward-temporal full test.',
        'csv_sha256': manifest['csv_sha256']})
    print(json.dumps({'rows': len(rows), 'results': results}), flush=True)


if __name__ == '__main__':
    main()
