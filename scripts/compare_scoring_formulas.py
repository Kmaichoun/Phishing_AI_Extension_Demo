"""Paired formula diagnostic on local fixtures; NEVER an independent accuracy benchmark.

Uses the same deployed forest, calibrator, feature schema and current rule engine.
Does not visit dataset URLs, fit models, tune production thresholds or replace models.
"""
import argparse
import csv
import hashlib
import html
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone
import joblib
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from feature_extractor import feature_vector
from fuzzy_scoring import fuzzy_score
from risk_policy import apply_consensus_guardrail


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--node', required=True)
    args = parser.parse_args()
    out = ROOT / 'output/formula-comparison'
    out.mkdir(parents=True, exist_ok=True)
    rows = {}
    def add(url, group):
        rows.setdefault(url, {'url': url, 'group': group})
    for url in ['https://www.ku.ac.th/th', 'https://www.chula.ac.th/', 'https://www.cmu.ac.th/',
                'https://www.kmitl.ac.th/', 'https://www.su.ac.th/']:
        add(url, 'education_examples')
    for r in csv.DictReader((ROOT/'backend/data/seed_urls.csv').open(encoding='utf-8-sig')):
        add(r['url'], 'synthetic_suspicious' if r['label'] == '1' else 'benign_seed_examples')
    for r in csv.DictReader((ROOT/'backend/data/legitimate_deep_links.csv').open(encoding='utf-8-sig')):
        add(r['url'], 'unverified_deep_links')
    data = list(rows.values())
    bridge = subprocess.run([args.node, str(ROOT/'scripts/score_dataset.js')],
        input=json.dumps(list(rows)), text=True, capture_output=True, check=True)
    rules = np.asarray(json.loads(bridge.stdout), dtype=float)
    model_path = ROOT/'backend/model.pkl'
    model_hash = hashlib.sha256(model_path.read_bytes()).hexdigest()
    b = joblib.load(model_path)
    assert b.get('probability_calibrator') is not None, 'Do not present raw RF as calibrated RF'
    assert b.get('fusion_model') is not None, 'Expected deployed fusion baseline'
    schema = b['feature_schema_version']
    x = np.asarray([feature_vector(r['url'], schema) for r in data])
    rf = b['model']
    raw = rf.predict_proba(x)[:, list(rf.classes_).index(1)]
    cal = b['probability_calibrator']
    ml = cal.predict_proba(raw.reshape(-1, 1))[:, list(cal.classes_).index(1)]
    fuzzy = np.asarray([fuzzy_score(v) / 100 for v in rules])
    fusion = b['fusion_model']
    fused = fusion.predict_proba(np.column_stack([fuzzy, ml]))[:, list(fusion.classes_).index(1)]
    old = np.asarray([apply_consensus_guardrail(f,m,s)[0] for f,m,s in zip(fuzzy, ml, fused)])
    scores = {'legacy_fusion':old * 100, 'calibrated_rf':ml * 100, 'blend_40_60':.4 * rules + .6 * ml * 100}
    for i, r in enumerate(data):
        r['rule_score'] = float(rules[i])
        r.update({name:float(values[i]) for name,values in scores.items()})
    groups = {}
    for group in dict.fromkeys(r['group'] for r in data):
        mask = np.asarray([r['group'] == group for r in data])
        groups[group] = {'count':int(mask.sum()), 'scores':{}}
        for name,values in scores.items():
            groups[group]['scores'][name] = {'mean':float(values[mask].mean()),
                'median':float(np.median(values[mask])), 'max':float(values[mask].max()),
                'alerts_at_common_cutoffs':{str(cut):int((values[mask] >= cut).sum()) for cut in [50,61,81,90,96,99,100]}}
    report = {'created_at':datetime.now(timezone.utc).isoformat(), 'model_sha256':model_hash,
        'model_version':b['model_version'], 'feature_schema':schema, 'current_policy':b['policy'],
        'design':'Paired diagnostic. Same existing forest/calibration, current rules and URL fixtures; only fusion changes.',
        'limitations':['Not a retrained v4 model. Old feature schema deliberately preserved.',
          'Fixtures may overlap training. Seed suspicious URLs are synthetic, not confirmed live phishing.',
          'Deep links are collected on familiar hosts, not independently verified benign pages.',
          'Shared numeric cutoffs are sensitivity examples, not comparable operating points or deployable thresholds.',
          'No population accuracy/FPR/recall, optimal threshold or statistical winner can be inferred.'],
        'groups':groups, 'rows':data}
    for relative in ['web-app/analyzer.js','backend/feature_extractor.py','backend/fuzzy_scoring.py','backend/risk_policy.py',
                     'backend/data/seed_urls.csv','backend/data/legitimate_deep_links.csv']:
        report.setdefault('input_sha256',{})[relative] = hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()
    (out/'comparison.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    with (out/'scores.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(data[0]));writer.writeheader();writer.writerows(data)
    labels={'legacy_fusion':'สูตรเดิม: Fusion + Guardrail','calibrated_rf':'สูตรเสนอ: Calibrated RF','blend_40_60':'สูตร 40/60'}
    group_labels={'education_examples':'มหาวิทยาลัยตัวอย่าง','benign_seed_examples':'เว็บจริงตัวอย่างเดิม',
                  'synthetic_suspicious':'URL จำลองน่าสงสัย','unverified_deep_links':'Deep links ที่ยังไม่ยืนยันฉลากรายหน้า'}
    summary=''
    for group,g in groups.items():
        for name,s in g['scores'].items():
            summary+=f"<tr><td>{group_labels[group]} ({g['count']})</td><td>{labels[name]}</td><td>{s['mean']:.1f}</td>"+''.join(f"<td>{s['alerts_at_common_cutoffs'][str(c)]}/{g['count']}</td>" for c in [61,81,96])+ '</tr>'
    details=''.join('<tr><td>'+html.escape(r['url'])+'</td><td>'+group_labels[r['group']]+'</td>'+''.join(f'<td>{r[n]:.1f}</td>' for n in ['rule_score',*scores])+'</tr>' for r in data)
    page='''<!doctype html><html lang="th"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>เปรียบเทียบสูตร Phish Radar</title>
    <style>body{font:16px/1.65 system-ui,sans-serif;background:#f5f5f2;color:#202521;margin:32px auto;padding:0 24px;max-width:1200px}h1{font-size:30px}table{border-collapse:collapse;width:100%;background:white;margin:20px 0}th,td{padding:10px 12px;border-bottom:1px solid #ddd;text-align:left}th{background:#e5ece5}td:first-child{overflow-wrap:anywhere}.notice{border-left:5px solid #ac6b0d;padding:14px 20px;background:#fff2d9}.scroll{overflow-x:auto}small{color:#555}</style>
    <h1>เปรียบเทียบสูตรคะแนน Phish Radar</h1>
    <p class="notice"><b>ผลทดลองพฤติกรรมคะแนน ไม่ใช่ผลความแม่นยำบนเว็บจริงชุดใหม่</b><br>ใช้ Random Forest และตัวปรับเทียบเดิมเหมือนกัน เปลี่ยนเฉพาะวิธีรวมคะแนน ไม่มีการฝึกหรือเปลี่ยนโมเดลที่เปิดใช้</p>
    <p>คะแนนลดลงไม่เท่ากับแม่นยำขึ้น ต้องเลือกเกณฑ์ใหม่จาก validation และทดสอบบนข้อมูลที่ไม่เคยเห็นก่อน จึงจะตัดสินผู้ชนะได้</p>
    <h2>จำนวนที่คะแนนถึงจุดตัดตัวอย่าง</h2><p>คอลัมน์ 61 / 81 / 96 คือจำนวน URL ที่ถึงจุดตัดเดียวกันทางตัวเลข ไม่ใช่เกณฑ์ที่เหมาะสมของแต่ละสูตร และไม่ใช่ FPR/Recall ของประชากร</p>
    <div class="scroll"><table><thead><tr><th>กลุ่ม</th><th>สูตร</th><th>คะแนนเฉลี่ย</th><th>≥61</th><th>≥81</th><th>≥96</th></tr></thead><tbody>'''+summary+'''</tbody></table></div>
    <p>มหาวิทยาลัยและเว็บจริงตัวอย่างเป็น regression ที่คัดเลือกไว้ ไม่ใช่ random holdout; URL น่าสงสัยเป็นข้อมูลจำลอง; deep links ยังไม่ตรวจยืนยันว่าทุกหน้าปลอดภัย</p>
    <h2>คะแนนราย URL</h2><p>คะแนนละเอียดและ metadata มีใน scores.csv และ comparison.json การตัดสินใช้ค่าจริงก่อนปัดเศษ</p><div class="scroll"><table><thead><tr><th>URL (ไม่ได้เปิดตรวจปลายทาง)</th><th>กลุ่ม</th><th>Rule</th><th>เดิม</th><th>RF</th><th>40/60</th></tr></thead><tbody>'''+details+'''</tbody></table></div></html>'''
    (out/'report.html').write_text(page,encoding='utf-8')
    assert hashlib.sha256(model_path.read_bytes()).hexdigest() == model_hash
    print(json.dumps({'groups':groups,'examples':data[:5],'output':str(out)},ensure_ascii=True,indent=2))

if __name__ == '__main__': main()
