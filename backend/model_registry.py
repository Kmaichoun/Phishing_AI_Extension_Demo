"""Read-only experiment catalog; web requests never unpickle experiment files."""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parent
DATA = BASE / 'data'
ARTIFACTS = ('candidate.pkl', 'dataset.csv', 'evaluation.json', 'regression.json')
SCORE_CODE = ('backend/feature_extractor.py', 'backend/fuzzy_scoring.py', 'backend/risk_policy.py',
              'backend/train_simple_model.py', 'scripts/analyze_model_errors.py', 'backend/app.py',
              'scripts/check_candidate_model.py', 'scripts/score_dataset.js', 'web-app/analyzer.js',
              'scripts/collect_research_urls.py')
REGRESSION_CODE = ('backend/app.py', 'backend/feature_extractor.py', 'backend/fuzzy_scoring.py',
                   'backend/risk_policy.py', 'scripts/check_candidate_model.py',
                   'scripts/score_dataset.js', 'web-app/analyzer.js')


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        raise ValueError('Expected a JSON object')
    return value


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write('\n')
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def experiment_path(name: str, root: Path = DATA) -> Path:
    if not re.fullmatch(r'simple_[a-zA-Z0-9_-]{1,64}', name):
        raise ValueError('Invalid experiment name')
    original = root / name
    path = original.resolve()
    if path.parent != root.resolve() or original.is_symlink() or getattr(original, 'is_junction', lambda: False)():
        raise ValueError('Experiment must be inside backend/data')
    for filename in (*ARTIFACTS, 'error_analysis.json', 'publisher_sources.json'):
        if (path / filename).is_symlink():
            raise ValueError('Linked artifacts are not allowed')
    return path


def fpr_upper(fp: int, negatives: int) -> float | None:
    if negatives == 0:
        return None
    z = 1.6448536269514722  # One-sided 95% Wilson bound, same as threshold selection.
    p = fp / negatives
    return (p + z*z/(2*negatives) + z*math.sqrt(p*(1-p)/negatives + z*z/(4*negatives**2))) / (1+z*z/negatives)


def counts_metrics(labels, scores, threshold: float) -> dict:
    counts = dict(tp=0, fp=0, tn=0, fn=0)
    for label, score in zip(labels, scores):
        counts[('tp' if label else 'fp') if score >= threshold else ('fn' if label else 'tn')] += 1
    tp, fp, tn, fn = (counts[k] for k in ('tp', 'fp', 'tn', 'fn'))
    return {**counts, 'rows': tp+fp+tn+fn, 'negatives': fp+tn, 'positives': tp+fn,
            'fpr': fp/(fp+tn) if fp+tn else None,
            'fpr_upper_95': fpr_upper(fp, fp+tn),
            'recall': tp/(tp+fn) if tp+fn else None,
            'precision': tp/(tp+fp) if tp+fp else None, 'threshold': threshold}


def gate_checks(report: dict) -> list[dict]:
    """Never rely on an old promotion_ready boolean. Recompute from analysis evidence."""
    quality = report.get('quality', {})
    candidate, baseline = report.get('candidate', {}), report.get('baseline', {})
    checks = []

    def check(key, label, passed):
        checks.append({'key': key, 'label': label, 'passed': bool(passed)})

    check('split', 'แบ่งโดเมน Train / Calibration / Validation / Holdout ไม่ซ้ำกัน',
          quality.get('group_overlap') == 0 and quality.get('all_splits_have_both_labels') is True)
    check('fresh', 'โดเมน Holdout ไม่เคยใช้กับโมเดลเดิมหรือรอบทดลองก่อน',
          quality.get('previously_seen_holdout_domains') == 0)
    check('provenance', 'ไม่มีข้อมูลสังเคราะห์หรือป้ายกำกับภายในที่ยังไม่ยืนยัน',
          quality.get('synthetic_rows') == 0 and quality.get('unverified_benign_rows') == 0)
    check('regression', 'ผ่านกรณีทดสอบเว็บปกติ และผูกผลกับไฟล์โมเดลนี้',
          report.get('regression_passed') is True)
    check('external', 'มีชุดทดสอบต่างแหล่งที่กันไว้ และไม่เคยใช้ในรอบก่อน',
          quality.get('external_test_validated') is True)
    for stage, ceiling in [('warning', .01), ('blocking', .001)]:
        value = candidate.get(stage, {}).get('fpr_upper_95')
        check(stage, f'{stage}: ขอบบน FPR 95% ไม่เกิน {ceiling*100:g}%',
              isinstance(value, (int, float)) and math.isfinite(value) and value <= ceiling)
        recall = candidate.get(stage, {}).get('recall')
        previous = baseline.get(stage, {}).get('recall')
        check(stage+'_recall', f'{stage}: Recall ไม่ต่ำกว่ารุ่นใช้งานจริงบนชุดเดียวกัน',
              recall is not None and previous is not None and recall >= previous)
        external = report.get('external', {}).get(stage, {})
        external_baseline = report.get('external', {}).get(stage+'_baseline', {})
        check(stage+'_external', f'{stage}: ชุดต่างแหล่งผ่านขอบบน FPR และ Recall ไม่ลดลง',
              external.get('fpr_upper_95') is not None and external['fpr_upper_95'] <= ceiling
              and external.get('recall') is not None and external_baseline.get('recall') is not None
              and external['recall'] >= external_baseline['recall'])
    return checks


def verified_analysis(path: Path, production: Path = BASE / 'model.pkl') -> dict:
    report = read_json(path / 'error_analysis.json')
    for filename in ARTIFACTS:
        if report.get('artifacts', {}).get(filename) != sha256(path / filename):
            raise ValueError(f'Artifact changed: {filename}; rerun analysis')
    has_publisher = (path/'publisher_sources.json').exists() or 'publisher_sources.json' in report.get('artifacts', {})
    evaluation = read_json(path/'evaluation.json') if has_publisher else {}
    if evaluation.get('publisher_sources_sha256'):
        actual = sha256(path/'publisher_sources.json')
        if actual != evaluation['publisher_sources_sha256'] or actual != report.get('artifacts',{}).get('publisher_sources.json'):
            raise ValueError('Publisher provenance changed; rerun analysis')
    if report.get('baseline_sha256') != sha256(production):
        raise ValueError('Production changed; rerun comparison')
    baseline_dataset = (path.parent/report.get('baseline_dataset', 'training_urls.csv')).resolve()
    baseline_dataset.relative_to(path.parent.resolve())
    if report.get('legacy_dataset_sha256') != sha256(baseline_dataset):
        raise ValueError('Legacy training dataset changed; rerun exposure audit')
    if report.get('score_code') != {p: sha256(BASE.parent/p) for p in SCORE_CODE}:
        raise ValueError('Scoring code changed; rerun analysis')
    # All experiments present at analysis time, and no later one, must be represented.
    inventory = {p.name: sha256(p / 'dataset.csv') for p in path.parent.glob('simple_*')
                 if p.is_dir() and (p / 'dataset.csv').is_file()}
    if report.get('experiment_inventory') != inventory:
        raise ValueError('Experiment inventory changed; rerun exposure audit')
    report['checks'] = gate_checks(report)
    report['promotion_ready'] = all(item['passed'] for item in report['checks'])
    return report


def catalog() -> dict:
    items = []
    for candidate in sorted(DATA.glob('simple_*')):
        if not candidate.is_dir():
            continue
        try:
            path = experiment_path(candidate.name)
            evaluation = read_json(path / 'evaluation.json')
            item = {'id': path.name, 'formula': evaluation.get('risk_formula'),
                    'created_at': evaluation.get('created_at'), 'rows': evaluation.get('dataset_rows'),
                    'promotion_ready': False, 'analysis': None, 'error': None}
            try:
                item['analysis'] = verified_analysis(path)
                item['promotion_ready'] = item['analysis']['promotion_ready']
            except (OSError, ValueError, KeyError, TypeError):
                item['error'] = 'ยังไม่มีรายงานที่ตรงกับไฟล์ปัจจุบัน ให้รัน analyze_model_errors.py อีกครั้ง'
            items.append(item)
        except (OSError, ValueError, KeyError, TypeError):
            items.append({'id': candidate.name, 'error': 'อ่านข้อมูลการทดลองไม่ได้', 'promotion_ready': False})
    return {'items': items, 'production_sha256': sha256(BASE / 'model.pkl') if (BASE / 'model.pkl').exists() else None}
