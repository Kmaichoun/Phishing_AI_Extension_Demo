"""Re-evaluate stored, reused benchmark scores; does not train on test labels."""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'backend/data/simple_recovered_query_structural_rf_20261005'
OUT = ROOT / 'output/warning60-20261007'


def metrics(rows, threshold):
    c = Counter((int(r['label']), float(r['candidate_score']) >= threshold) for r in rows)
    tn, fp, fn, tp = c[0, False], c[0, True], c[1, False], c[1, True]
    return dict(threshold=threshold, rows=len(rows), true_negative=tn,
                false_positive=fp, false_negative=fn, true_positive=tp,
                false_positive_rate=fp / (tn + fp), recall=tp / (tp + fn),
                precision=tp / (tp + fp), accuracy=(tp + tn) / len(rows))


def main():
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    current_hash = digest(ROOT / 'backend/model.pkl')
    source_hash = digest(SOURCE / 'candidate.pkl')
    if current_hash != source_hash:
        active = json.loads((OUT / 'active-policy.json').read_text(encoding='utf-8'))
        if (active['model_sha256'] != current_hash or active.get('model_retrained') is not False
                or active['threshold_evaluation'].get('scoring_model_sha256', active['threshold_evaluation']['model_sha256']) != source_hash):
            raise ValueError('Stored scores do not belong to the current scoring model')
    with (SOURCE / 'holdout-scores.csv').open(encoding='utf-8', newline='') as f:
        rows = list(csv.DictReader(f))
    report = {
        'model_sha256': digest(ROOT / 'backend/model.pkl'),
        'scoring_model_sha256': source_hash,
        'scores_sha256': digest(SOURCE / 'holdout-scores.csv'),
        'limitation': 'Reused historical benchmark, not independent or current-world accuracy.',
        'existing_policy': metrics(rows, 85.05),
        'requested_policy': metrics(rows, 60),
        'existing_blocking_policy': metrics(rows, 95.77),
        'requested_blocking_policy': metrics(rows, 80),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'threshold-evaluation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
