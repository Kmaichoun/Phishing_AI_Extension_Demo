"""Package the locally verified Colab demo and report measured results only."""
from pathlib import Path
import csv
import hashlib
import json
import math
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output' / 'colab-rf-dl-20261023'


def read_rows(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    result = OUT / 'local_cpu_results'
    executed = json.loads((OUT / 'Phish_Radar_RF_vs_DL_LOCAL_CPU_DEMO_executed.ipynb').read_text(encoding='utf-8'))
    assert executed['metadata']['local_verification']['complete'] is True
    code_cells = [cell for cell in executed['cells'] if cell['cell_type'] == 'code']
    assert code_cells and all(cell['execution_count'] is not None for cell in code_cells)
    assert not any(output.get('output_type') == 'error' for cell in code_cells for output in cell['outputs'])
    metrics = {r['Model']: r for r in read_rows(result / 'metrics_threshold_0_5.csv')}
    resources = {r['']: r for r in read_rows(result / 'resource_comparison.csv')}
    config = json.loads((result / 'run_config.json').read_text(encoding='utf-8'))
    environment = json.loads((result / 'environment.json').read_text(encoding='utf-8'))
    assert config['mode'] == 'DEMO' and config['rows_used'] == 30000
    assert config['split_counts'] == {'train': 21000, 'validation': 4500, 'test': 4500}
    assert config['runtime_verified_on_colab'] is False
    assert environment['training_device_mlp'] == 'cpu'
    for row in metrics.values():
        tn, fp, fn, tp = [int(row[key]) for key in ['TN', 'FP', 'FN', 'TP']]
        assert tn + fp + fn + tp == int(row['N']) == 4500
        expected = {'Recall': tp / (tp + fn), 'FPR': fp / (fp + tn),
                    'Precision': tp / (tp + fp) if tp + fp else 0,
                    'F1': 2 * tp / (2 * tp + fp + fn),
                    'Accuracy': (tp + tn) / 4500}
        assert all(math.isclose(float(row[key]), value, abs_tol=1e-12)
                   for key, value in expected.items())
        assert all(0 <= float(row[key]) <= 1 for key in ['AP', 'ROC_AUC'])
    for row in resources.values():
        assert 0 <= float(row['CPU_median_ms']) <= float(row['CPU_p95_ms'])
        assert float(row['Train_seconds']) >= 0 and float(row['Model_file_MiB']) > 0
    report = [
        '# ผลเดโม Random Forest เทียบกับ Deep Learning ที่รันจริง', '',
        '**แหล่งผล: Local CPU verification — ยังไม่ได้รันใน Google Colab**', '',
        'ฝึกโมเดลใหม่ทั้งคู่บน 21,000 แถว ใช้ validation 4,500 แถวและ test 4,500 แถว '
        'จากชุดเดโม 30,000 แถว ใช้ 172 URL-derived features เหมือนกัน '
        'ไม่มี registered domain ซ้ำข้ามชุด ใช้ threshold 0.50 และ seed 20261023', '',
        '| ค่า | Random Forest | Deep Learning (MLP) | ทิศทางที่ต้องการ |',
        '|---|---:|---:|---|',
    ]
    metric_specs = [('Accuracy', 'Accuracy', True), ('Precision', 'Precision', True),
                    ('Recall', 'Recall', True), ('FPR', 'FPR', False),
                    ('F1', 'F1', True), ('AP', 'AP', True), ('ROC-AUC', 'ROC_AUC', True)]
    for label, key, higher in metric_specs:
        a = float(metrics['Random Forest'][key])
        b = float(metrics['Deep Learning (MLP)'][key])
        percent = key in {'Accuracy', 'Precision', 'Recall', 'FPR'}
        aa, bb = (f'{a:.2%}', f'{b:.2%}') if percent else (f'{a:.4f}', f'{b:.4f}')
        report.append(f'| {label} | {aa} | {bb} | {"สูงกว่า" if higher else "ต่ำกว่า"} |')
    for label, key, unit in [('เวลาฝึก', 'Train_seconds', 's'),
                             ('CPU median latency / ตัวอย่าง', 'CPU_median_ms', 'ms'),
                             ('CPU p95 latency / ตัวอย่าง', 'CPU_p95_ms', 'ms'),
                             ('ขนาดไฟล์โมเดล', 'Model_file_MiB', 'MiB')]:
        a = float(resources['Random Forest'][key])
        b = float(resources['Deep Learning (MLP)'][key])
        report.append(f'| {label} | {a:.4f} {unit} | {b:.4f} {unit} | ต่ำกว่า |')
    tuned = read_rows(result / 'metrics_validation_f1_threshold.csv')
    report += ['', '## ตารางรอง: threshold เลือกด้วย validation F1', '',
               'เลือก threshold ด้วย validation เท่านั้นก่อนวัด test ไม่ใช้ test เลือกค่า '
               'ตารางนี้ใช้ชุด test เดียวกับตารางหลัก แต่ operating point ต่างกัน', '',
               '| โมเดล | Threshold | Precision | Recall | FPR | F1 |',
               '|---|---:|---:|---:|---:|---:|']
    for row in tuned:
        report.append(f'| {row["Model"]} | {float(row["Threshold"]):.4f} | '
                      f'{float(row["Precision"]):.2%} | {float(row["Recall"]):.2%} | '
                      f'{float(row["FPR"]):.2%} | {float(row["F1"]):.4f} |')
    report += ['', 'ผู้ที่ได้ F1 สูงกว่าอาจเปลี่ยนเมื่อ threshold เปลี่ยน '
               'จึงควรบอกทั้ง threshold และ Recall/FPR ทุกครั้ง '
               'AP และ ROC-AUC ไม่เปลี่ยนในสองตารางนี้เพราะใช้ scores ของ test เดียวกัน', '',
               f'MLP เลือก checkpoint epoch {config["best_epoch"]} จาก validation loss ต่ำสุด '
               'กราฟแสดง train loss ลดลงต่อแต่ validation loss ผันผวน จึงไม่เลือก epoch สุดท้ายโดยอัตโนมัติ']
    report += ['', '## อ่านผลอย่างไร', '',
               (result / 'summary_TH.txt').read_text(encoding='utf-8'), '',
               'ตารางราย metric พร้อมส่วนต่าง MLP − RF และชื่อผู้ที่ได้ค่าดีกว่าอยู่ใน '
               '`local_cpu_results/metric_comparison.csv` ส่วนตาราง threshold ที่เลือกด้วย validation F1 '
               'อยู่ใน `metrics_validation_f1_threshold.csv` เป็นผลรอง และห้ามใช้แทนนโยบาย 60/80 เดิม', '',
               '## ขอบเขตการวัดและข้อจำกัด', '',
               '- CPU inference ใช้ 1 thread, batch 1, warm-up 10 ครั้ง และวัด 100 แถวเดียวกัน '
               'รวม preprocessing ของแต่ละโมเดล แต่ไม่รวม URL extraction/network/backend',
               '- เวลาฝึก MLP รวม scaling ของ train และ validation/early stopping; '
               'เวลาฝึก RF เป็น fit บน CPU จำนวน 120 ต้น โมเดลใช้ optimization และสถาปัตยกรรมต่างกัน',
               '- ขนาดไฟล์เป็น serialization ต่างรูปแบบรวมข้อมูล inference ที่จำเป็น ไม่ใช่ RAM/VRAM',
               '- ใช้ข้อมูลพัฒนาเดิมจากหลาย publisher ไม่ใช่ fresh temporal test '
               'และไม่ได้ทดลองหลาย seed หรือทดสอบความต่างทางสถิติ',
               '- ผลนี้ไม่ใช่ RF 174 features เดิมใน Extension ไม่ได้ calibrate probability '
               'และไม่ใช่หลักฐานพร้อม production',
               '- เมื่อรันบน Colab ให้ใช้ตารางและเวลาที่ notebook วัดจากรอบนั้น '
               'อย่าใส่เวลา CPU รอบนี้เป็นเวลา GPU ของ Colab', '',
               '## กราฟ', '',
               '![Confusion Matrix](local_cpu_results/confusion_matrices.png)', '',
               '![ROC and PR](local_cpu_results/roc_pr_curves.png)', '',
               '![Learning curve and metrics](local_cpu_results/learning_and_metrics.png)', '',
               '## Software ของรอบทดสอบนี้', '']
    for key in ['python', 'numpy', 'pandas', 'sklearn', 'torch', 'matplotlib', 'cpu']:
        report.append(f'- {key}: {environment[key]}')
    (OUT / 'RESULTS_LOCAL_CPU_TH.md').write_text('\n'.join(report) + '\n', encoding='utf-8')
    version_map = {'numpy': 'numpy', 'pandas': 'pandas', 'sklearn': 'scikit-learn',
                   'torch': 'torch', 'matplotlib': 'matplotlib'}
    (OUT / 'tested-library-versions.txt').write_text(
        '# Versions used for local CPU verification; not a required Colab upgrade.\n' +
        '\n'.join(f'{package}=={environment[key]}' for key, package in version_map.items()) + '\n',
        encoding='utf-8')
    # Explicit allowlist: no raw dataset, registry, original model, venv or secrets.
    wanted = [OUT / 'Phish_Radar_RF_vs_DL_Colab.ipynb',
              OUT / 'Phish_Radar_RF_vs_DL_LOCAL_CPU_DEMO_executed.ipynb',
              OUT / 'README_TH.md', OUT / 'RESULTS_LOCAL_CPU_TH.md',
              OUT / 'requirements-colab.txt', OUT / 'tested-library-versions.txt',
              OUT / 'data' / 'demo_dataset.zip', OUT / 'data' / 'manifest.json',
              OUT / 'results.zip']
    # Trained models are already inside results.zip; avoid duplicating them.
    wanted += sorted(p for p in result.iterdir() if p.is_file() and p.suffix not in {'.pkl', '.pt'})
    assert all(path.is_file() for path in wanted)
    package_manifest = {'purpose': 'Thai RF/MLP Colab academic demonstration',
        'local_cpu_execution_complete': True, 'google_colab_execution_verified': False,
        'files': [{'path': p.relative_to(OUT).as_posix(), 'bytes': p.stat().st_size,
                   'sha256': digest(p)} for p in wanted]}
    package_manifest_path = OUT / 'PACKAGE_MANIFEST.json'
    package_manifest_path.write_text(json.dumps(package_manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    wanted.append(package_manifest_path)
    package = OUT.parent / 'Phish_Radar_Colab_RF_vs_DL_20261023.zip'
    with zipfile.ZipFile(package, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in wanted:
            archive.write(path, arcname='Phish_Radar_Colab_RF_vs_DL/' + path.relative_to(OUT).as_posix())
    print('Package:', package)
    print('Bytes:', package.stat().st_size)
    print('SHA256:', digest(package))
    print('Files:', len(wanted))


if __name__ == '__main__':
    main()
