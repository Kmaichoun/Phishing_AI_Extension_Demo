"""Build the self-contained, Thai RF/MLP Colab demo (no runtime imports)."""
from pathlib import Path
import json
import textwrap

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output' / 'colab-rf-dl-20261023'
cells = []


def md(source):
    cells.append({'cell_type': 'markdown', 'metadata': {},
                  'source': textwrap.dedent(source).strip() + '\n'})


def code(source, tag):
    cells.append({'cell_type': 'code', 'execution_count': None,
                  'metadata': {'tags': [tag]}, 'outputs': [],
                  'source': textwrap.dedent(source).strip() + '\n'})


md('''
# Phish Radar: Random Forest vs Deep Learning บน Colab

**เดโมเพื่อพรีเซนต์ — ฝึก RF ใหม่เทียบ MLP 3 hidden layers บนข้อมูลเดียวกัน**

1. เปิด notebook นี้ใน [Google Colab](https://colab.research.google.com/) ด้วย File → Upload notebook
2. เลือก Runtime → Change runtime type → GPU ถ้ามี; CPU ก็รันได้
3. รันจากบนลงล่าง เมื่อช่องอัปโหลดปรากฏให้เลือก **`demo_dataset.zip`** ที่แนบมา
4. รันให้เสร็จก่อนพรีเซนต์ บันทึก notebook ที่มี outputs และดาวน์โหลด `results.zip`

ค่าเริ่มต้น DEMO ใช้ **30,000 แถว**; เปลี่ยน `MODE="QUICK"` เพื่อทดลองขั้นตอนด้วยประมาณ 6,000 แถวก่อน
QUICK เป็นการรันอีกการทดลองหนึ่ง จำนวน test ต่างจาก DEMO ห้ามนำตัวเลขสองโหมดมาเทียบกันเป็นผลเดียว

**สิ่งที่เปรียบเทียบ:** RF ใหม่กับ MLP ใหม่ใช้ 172 features จาก URL ชุดเดียวกัน
(schema `url-v8-domain-enriched` ของ snapshot 20 ต.ค. 2026) โดยไม่ใช้ 2 publisher-reference features
ของ RF 174 features เดิม ไม่โหลด/เปลี่ยน `backend/model.pkl` และไม่เชื่อม backend/Extension
ข้อมูลมีเฉพาะ features, label, source, split และรหัสกลุ่ม ไม่มี URL ดิบให้คลิกหรือเปิด
''')

md('''
## 1. ไลบรารีและเครื่องที่ใช้

| ไลบรารี | ใช้ทำอะไร |
|---|---|
| NumPy | เมทริกซ์ features และคำนวณตัวเลข |
| pandas | อ่านข้อมูล ตารางผล และ CSV |
| scikit-learn | Random Forest, StandardScaler, metrics |
| PyTorch (`torch`) | ฝึก MLP ด้วย CPU/GPU |
| Matplotlib | กราฟเปรียบเทียบและ Confusion Matrix |

cell นี้ติดตั้งเฉพาะแพ็กเกจที่ยังไม่มี ไม่อัปเกรดแพ็กเกจทั้งหมดของ Colab
`google.colab` ใช้เฉพาะอัปโหลด/ดาวน์โหลดใน Colab; Python มาตรฐาน เช่น `zipfile`, `json`, `hashlib`
ไม่ต้อง pip install และไม่ต้อง TensorFlow, MySQL, Ollama หรือ `tldextract`
ถ้าระบบไม่มี torch จะติดตั้ง CPU wheel; Colab ที่มี torch อยู่แล้วจะใช้ของเดิมรวมถึง CUDA ถ้าใช้งานได้
''')
code('''
import importlib.util
import subprocess
import sys

if not globals().get('SKIP_INSTALL', False):
    packages = {'numpy': 'numpy', 'pandas': 'pandas', 'sklearn': 'scikit-learn',
                'matplotlib': 'matplotlib'}
    missing = [package for module, package in packages.items()
               if importlib.util.find_spec(module) is None]
    if missing:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q', *missing])
    if importlib.util.find_spec('torch') is None:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q', 'torch',
                               '--index-url', 'https://download.pytorch.org/whl/cpu',
                               '--extra-index-url', 'https://pypi.org/simple'])
print('Libraries ready; installations are on this runtime, not your local PC.')
''', 'dependencies')

code('''
import os
os.environ.setdefault('OMP_NUM_THREADS', '2')
os.environ.setdefault('MKL_NUM_THREADS', '2')
import copy
import gzip
import hashlib
import io
import json
import pickle
import platform
import random
import time
import zipfile
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import sklearn
import matplotlib
import matplotlib.pyplot as plt
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (accuracy_score, average_precision_score,
    balanced_accuracy_score, confusion_matrix, f1_score, log_loss,
    precision_score, recall_score, roc_auc_score, precision_recall_curve,
    roc_curve, ConfusionMatrixDisplay)
from threadpoolctl import threadpool_limits
from IPython.display import display, Markdown

SEED = 20261023
MODE = globals().get('MODE_OVERRIDE', 'DEMO')  # DEMO or QUICK
CONFIG = {
    'DEMO': {'fraction': 1.0, 'trees': 120, 'epochs': 35, 'patience': 6},
    'QUICK': {'fraction': 0.2, 'trees': 60, 'epochs': 12, 'patience': 4},
}[MODE]
# Primary metric fixed before viewing test: Average Precision (AP).
# Both models unweighted; no model/threshold tuning using test labels.
PRIMARY_METRIC = 'AP'
BATCH_SIZE = 256
LEARNING_RATE = 1e-3
USE_GPU = globals().get('USE_GPU_OVERRIDE', True)
DEVICE = torch.device('cuda' if USE_GPU and torch.cuda.is_available() else 'cpu')
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)
torch.set_num_threads(2)
if torch.cuda.is_available():
    torch.cuda.manual_seed_all(SEED)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
torch.use_deterministic_algorithms(True, warn_only=True)
RUN_DIR = Path(globals().get('RUN_DIR_OVERRIDE', 'phish_radar_results'))
RUN_DIR.mkdir(parents=True, exist_ok=True)
try:
    import google.colab
    IS_COLAB = True
except ImportError:
    IS_COLAB = False
RUN_CONTEXT = globals().get('RUN_CONTEXT_OVERRIDE',
    'Google Colab' if IS_COLAB
    else 'local Python (not verified on Google Colab)')
environment = {
    'run_context': RUN_CONTEXT, 'timestamp_utc': datetime.now(timezone.utc).isoformat(),
    'python': platform.python_version(), 'platform': platform.platform(),
    'cpu': platform.processor(), 'logical_cpus': os.cpu_count(),
    'numpy': np.__version__, 'pandas': pd.__version__, 'sklearn': sklearn.__version__,
    'torch': torch.__version__, 'matplotlib': matplotlib.__version__,
    'training_device_mlp': str(DEVICE), 'gpu': torch.cuda.get_device_name(0)
    if DEVICE.type == 'cuda' else None, 'seed': SEED, 'mode': MODE,
    'threads_training': 2, 'threads_latency': 1,
}
display(pd.DataFrame(environment.items(), columns=['Setting', 'Value']))
print('Configuration:', CONFIG)
''', 'configuration')

md('''
## 2. โหลด Dataset ที่เตรียมจากโปรเจกต์

ไฟล์ต้นทาง `backend/data/simple_quality_rf_20261008/dataset.csv` มี 925,602 แถว ประมาณ 125 MB
เป็นยอดรวม train/calibration/validation เดิม ไม่ใช่จำนวนฝึกอย่างเดียว
ชุดแนบสุ่ม 30,000 แถวจากข้อมูลผู้เผยแพร่หลังตรวจ URL ซ้ำ/label ขัดกันและไม่ใช้ official-reference records
แบ่ง registered domain เป็น train/validation/test ก่อนสุ่ม จึงไม่มีโดเมนเดียวกันข้ามชุด
ใช้ ICANN Public Suffix List แบบ offline; สำหรับ private hosting อาจรวมหลาย tenant เป็นกลุ่มใหญ่เดียวกัน

การแบ่งครั้งนี้ใช้ **ข้อมูลพัฒนาเดิม** จึงเป็น holdout ภายในเดโม ไม่ใช่ test ใหม่ตามเวลา
ยังอาจมีอคติของผู้เผยแพร่ (เช่น benign queries ถูกลบ) แม้จะกันโดเมนซ้ำแล้ว
source ใช้ตรวจที่มาเท่านั้น ไม่ป้อนเป็น feature ให้โมเดล
''')
code('''
DATA_ZIP = Path(globals().get('DATA_ZIP_OVERRIDE', 'demo_dataset.zip'))
if not DATA_ZIP.exists():
    alternatives = [Path('data/demo_dataset.zip'), Path('/content/demo_dataset.zip')]
    DATA_ZIP = next((p for p in alternatives if p.exists()), DATA_ZIP)
if not DATA_ZIP.exists():
    try:
        from google.colab import files
    except ImportError as exc:
        raise FileNotFoundError('Place demo_dataset.zip beside this notebook, '
                                'or set DATA_ZIP_OVERRIDE to its path.') from exc
    print('Upload the supplied demo_dataset.zip (not the original URL CSV).')
    uploaded = files.upload()
    choices = [name for name in uploaded if name.lower().endswith('.zip')]
    if len(choices) != 1:
        raise ValueError('Please upload exactly one demo_dataset.zip file.')
    DATA_ZIP = Path(choices[0])

# Read only two known members in memory; never extract arbitrary uploaded paths.
with zipfile.ZipFile(DATA_ZIP) as archive:
    member_names = set(archive.namelist())
    assert {'features.csv.gz', 'manifest.json'} <= member_names, member_names
    assert archive.getinfo('features.csv.gz').file_size < 100_000_000
    assert archive.getinfo('manifest.json').file_size < 5_000_000
    manifest = json.loads(archive.read('manifest.json'))
    compressed_csv = archive.read('features.csv.gz')
csv_bytes = gzip.decompress(compressed_csv)
csv_sha256 = hashlib.sha256(csv_bytes).hexdigest()
# The builder supplies the expected bytes hash, independent of CSV parsing.
expected = manifest.get('features_csv_sha256')
assert expected, 'Manifest must record features_csv_sha256.'
assert csv_sha256 == expected, 'Dataset hash mismatch; use the supplied package again.'
df = pd.read_csv(io.BytesIO(csv_bytes), dtype={'source': str, 'split': str, 'group_id': str})
FEATURES = manifest['feature_names']
assert len(FEATURES) == 172 and len(set(FEATURES)) == 172
assert set(df.columns) == set(FEATURES) | {'label', 'source', 'split', 'group_id'}
assert set(df['label'].unique()) == {0, 1}
assert set(df['split'].unique()) == {'train', 'validation', 'test'}
assert df['group_id'].notna().all() and df['source'].notna().all()
assert df.groupby('group_id')['split'].nunique().max() == 1, 'Domain leakage!'
assert np.isfinite(df[FEATURES].to_numpy(dtype=np.float32)).all()
full_rows = len(df)
if CONFIG['fraction'] < 1:
    # Subsample within already assigned splits, never repartition domains.
    parts = []
    for _, part in df.groupby(['split', 'source', 'label'], sort=True):
        n = max(1, int(round(len(part) * CONFIG['fraction'])))
        parts.append(part.sample(n=n, random_state=SEED))
    df = pd.concat(parts, ignore_index=True)
df = df.sample(frac=1, random_state=SEED).reset_index(drop=True)
assert df.groupby('group_id')['split'].nunique().max() == 1
for split in ['train', 'validation', 'test']:
    assert set(df.loc[df['split'].eq(split), 'label'].unique()) == {0, 1}
split_table = pd.crosstab(df['split'], df['label']).reindex(['train', 'validation', 'test'])
split_table.columns = ['Benign (0)', 'Phishing (1)']
split_table['Total'] = split_table.sum(axis=1)
split_table['Domains'] = df.groupby('split')['group_id'].nunique()
display(split_table)
source_table = pd.crosstab([df['source'], df['split']], df['label'])
display(source_table.rename(columns={0: 'Benign', 1: 'Phishing'}))
print(f'Loaded {len(df):,}/{full_rows:,} rows, {len(FEATURES)} features; no domain overlap.')
print('Feature schema:', manifest.get('feature_schema'))
print('CSV SHA256:', csv_sha256)
split_table.to_csv(RUN_DIR / 'dataset_split_counts.csv', encoding='utf-8-sig')
source_table.to_csv(RUN_DIR / 'dataset_source_counts.csv', encoding='utf-8-sig')
''', 'load-data')

md('''
## 3. เตรียม input และฝึก Random Forest

ข้อมูลเข้า: URL → features ที่เตรียมไว้ 172 ตัว → โมเดล → phishing score
ทั้งสองโมเดลใช้ตัวอย่าง/labels และลำดับ features เดียวกัน
RF ใช้ค่าดิบ ส่วน MLP ใช้ StandardScaler ที่ **fit เฉพาะ train**
ไม่ใช้ label/source/split/group_id เป็น input และไม่มี class weighting ทั้งคู่
RF มีจำนวนต้นไม้ตามโหมด, max_depth=20, min_samples_leaf=2; กำหนดไว้ก่อนดู test
''')
code('''
arrays = {}
for split in ['train', 'validation', 'test']:
    part = df.loc[df['split'].eq(split)].reset_index(drop=True)
    arrays[split] = (part[FEATURES].to_numpy(dtype=np.float32),
                     part['label'].to_numpy(dtype=np.int64), part)
X_train, y_train, _ = arrays['train']
X_val, y_val, _ = arrays['validation']
X_test, y_test, test_rows = arrays['test']
scale_start = time.perf_counter()
scaler = StandardScaler()
X_train_s = scaler.fit_transform(X_train).astype(np.float32)
scaler_fit_and_train_transform_s = time.perf_counter() - scale_start
X_val_s = scaler.transform(X_val).astype(np.float32)
# Test transform only applies the frozen train-fitted parameters.
X_test_s = scaler.transform(X_test).astype(np.float32)

rf = RandomForestClassifier(n_estimators=CONFIG['trees'], max_depth=20,
    min_samples_leaf=2, max_features='sqrt', class_weight=None,
    n_jobs=2, random_state=SEED)
started = time.perf_counter()
rf.fit(X_train, y_train)
rf_train_s = time.perf_counter() - started
print(f'RF trained: {rf_train_s:.2f} seconds, CPU, {len(rf.estimators_)} trees')
''', 'train-rf')

md('''
## 4. ฝึก Deep Learning: MLP 3 hidden layers

โครงสร้าง **172 → 128 → 64 → 32 → 1** ใช้ ReLU, Dropout 0.15 และ sigmoid ตอนทำนาย
ฝึกด้วย AdamW, learning rate 0.001, batch size 256 และ BCEWithLogitsLoss
หยุดเมื่อ validation loss ไม่ดีขึ้นตาม patience แล้วคืน weights ของ epoch ที่ validation loss ต่ำสุด
ใช้ test หลังฝึกเสร็จเท่านั้น ไม่เลือก epoch จาก test
เวลา train ที่รายงานรวม scaler fit/transform(train) และ validation/early stopping
หาก MLP ใช้ GPU แต่ RF ใช้ CPU เวลา train เป็นต้นทุนบน hardware ของการรันนี้ ไม่ใช่ข้อพิสูจน์ algorithm เร็วกว่า
''')
code('''
class MLP(nn.Module):
    def __init__(self, input_dim):
        super().__init__()
        self.layers = nn.Sequential(
            nn.Linear(input_dim, 128), nn.ReLU(), nn.Dropout(0.15),
            nn.Linear(128, 64), nn.ReLU(), nn.Dropout(0.15),
            nn.Linear(64, 32), nn.ReLU(), nn.Linear(32, 1))
    def forward(self, x):
        return self.layers(x).squeeze(-1)

mlp = MLP(len(FEATURES)).to(DEVICE)
optimizer = torch.optim.AdamW(mlp.parameters(), lr=LEARNING_RATE, weight_decay=1e-4)
loss_fn = nn.BCEWithLogitsLoss()
generator = torch.Generator().manual_seed(SEED)
train_loader = DataLoader(TensorDataset(torch.from_numpy(X_train_s),
    torch.from_numpy(y_train.astype(np.float32))), batch_size=BATCH_SIZE,
    shuffle=True, generator=generator, num_workers=0)
val_x = torch.from_numpy(X_val_s).to(DEVICE)
val_y = torch.from_numpy(y_val.astype(np.float32)).to(DEVICE)
best_loss, stale, best_epoch, best_state = float('inf'), 0, 0, None
training_history = []
if DEVICE.type == 'cuda':
    torch.cuda.synchronize()
started = time.perf_counter()
for epoch in range(1, CONFIG['epochs'] + 1):
    mlp.train()
    total_loss = 0.0
    for xb, yb in train_loader:
        xb, yb = xb.to(DEVICE), yb.to(DEVICE)
        optimizer.zero_grad(set_to_none=True)
        loss = loss_fn(mlp(xb), yb)
        loss.backward()
        optimizer.step()
        total_loss += float(loss.detach().cpu()) * len(yb)
    mlp.eval()
    with torch.inference_mode():
        val_loss = float(loss_fn(mlp(val_x), val_y).cpu())
    train_loss = total_loss / len(y_train)
    training_history.append({'epoch': epoch, 'train_loss': train_loss, 'val_loss': val_loss})
    print(f'Epoch {epoch:02d} | train loss {train_loss:.4f} | validation loss {val_loss:.4f}')
    if val_loss < best_loss - 1e-5:
        best_loss, stale, best_epoch = val_loss, 0, epoch
        best_state = copy.deepcopy({k: v.detach().cpu() for k, v in mlp.state_dict().items()})
    else:
        stale += 1
    if stale >= CONFIG['patience']:
        print('Early stopping; restore the best validation checkpoint.')
        break
if DEVICE.type == 'cuda':
    torch.cuda.synchronize()
mlp_training_loop_s = time.perf_counter() - started
assert best_state is not None
mlp.load_state_dict(best_state)
mlp.eval()
mlp_train_s = mlp_training_loop_s + scaler_fit_and_train_transform_s
print(f'Best epoch: {best_epoch}; MLP training including train preprocessing: {mlp_train_s:.2f}s')
print('Trainable MLP parameters:', sum(p.numel() for p in mlp.parameters()))
''', 'train-mlp')

md('''
## 5. Freeze thresholds ด้วย validation แล้ววัด test

ตารางหลักใช้ **threshold 0.50** เหมือนกัน: score ≥ threshold ถือว่า phishing
ตารางรองใช้ threshold ที่ให้ F1 สูงสุดบน validation ของแต่ละโมเดล (เสมอกันเลือก threshold สูงกว่า)
จากนั้น freeze ก่อนคำนวณผล test; ตารางรองไม่ใช่การปรับ threshold ด้วย test
คะแนนยัง **ไม่ได้ calibrate** จึงไม่ใช่เปอร์เซ็นต์ความเสี่ยงที่รับรองแล้ว
threshold ของเดโมไม่ใช่นโยบาย Warning 60 / Block 80 ของแอปเดิม

**Primary metric = AP** (Average Precision; สรุป precision-recall แบบถ่วงน้ำหนัก ไม่ใช่ trapezoidal PR-AUC)
และต้องอ่าน **Recall คู่กับ FPR** เสมอ ไม่มีการกำหนดล่วงหน้าว่า DL ต้องชนะ
''')
code('''
def mlp_probabilities(matrix_scaled, model=mlp, device=DEVICE):
    model.eval()
    outputs = []
    with torch.inference_mode():
        for start in range(0, len(matrix_scaled), 1024):
            batch = torch.from_numpy(matrix_scaled[start:start+1024]).to(device)
            outputs.append(torch.sigmoid(model(batch)).cpu().numpy())
    return np.concatenate(outputs)

def validation_f1_threshold(y, scores):
    precision, recall, thresholds = precision_recall_curve(y, scores)
    f1_values = 2 * precision[:-1] * recall[:-1] / np.maximum(precision[:-1] + recall[:-1], 1e-12)
    best = np.flatnonzero(np.isclose(f1_values, np.max(f1_values), atol=1e-12, rtol=0))[-1]
    return float(thresholds[best])

val_probabilities = {'Random Forest': rf.predict_proba(X_val)[:, 1],
                     'Deep Learning (MLP)': mlp_probabilities(X_val_s)}
thresholds_f1 = {name: validation_f1_threshold(y_val, score)
                 for name, score in val_probabilities.items()}
print('Thresholds fixed using validation only:', thresholds_f1)
# Evaluate held-out test only after all training and threshold choices above.
test_probabilities = {'Random Forest': rf.predict_proba(X_test)[:, 1],
                      'Deep Learning (MLP)': mlp_probabilities(X_test_s)}

def evaluate(name, y, scores, threshold):
    predicted = (scores >= threshold).astype(np.int64)
    tn, fp, fn, tp = confusion_matrix(y, predicted, labels=[0, 1]).ravel()
    return {'Model': name, 'Threshold': threshold, 'Accuracy': accuracy_score(y, predicted),
        'Balanced_accuracy': balanced_accuracy_score(y, predicted) if len(np.unique(y)) == 2 else np.nan,
        'Precision': precision_score(y, predicted, zero_division=0),
        'Recall': recall_score(y, predicted, zero_division=0),
        'F1': f1_score(y, predicted, zero_division=0),
        'FPR': float(fp / (fp + tn)) if fp + tn else np.nan,
        'ROC_AUC': roc_auc_score(y, scores) if len(np.unique(y)) == 2 else np.nan,
        'AP': average_precision_score(y, scores) if len(np.unique(y)) == 2 else np.nan,
        'TN': int(tn), 'FP': int(fp), 'FN': int(fn), 'TP': int(tp), 'N': len(y),
        'Phishing_prevalence': float(np.mean(y))}

main_results = pd.DataFrame([evaluate(name, y_test, scores, 0.5)
                             for name, scores in test_probabilities.items()]).set_index('Model')
tuned_results = pd.DataFrame([evaluate(name, y_test, scores, thresholds_f1[name])
                              for name, scores in test_probabilities.items()]).set_index('Model')
display(Markdown('### Test: threshold 0.50 (ตารางหลัก)'))
display(main_results.round(4))
display(Markdown('### Test: threshold เลือกด้วย validation F1 (ตารางรอง)'))
display(tuned_results.round(4))
print(f'Test phishing prevalence: {np.mean(y_test):.2%}; random-ranking AP baseline is this prevalence.')
''', 'evaluate')

md('''
## 6. เทียบความเร็วบน CPU เดียวกัน และขนาดไฟล์ที่ใช้ทำนาย

Latency: CPU ทั้งคู่, 1 thread, batch size 1, warm-up 10 ครั้ง แล้ววัด 100 แถวเดียวกัน
รายงาน median และ p95; MLP รวม StandardScaler + tensor conversion + sigmoid, RF รวม predict_proba
**ไม่รวม** URL feature extraction, disk I/O, network และ backend; ไม่ใช่ latency ของ Extension
เวลาฝึก RF/MLP ใช้ hardware ที่รายงานด้านบน (RF CPU, MLP CPU หรือ GPU)
ขนาดไฟล์เป็นขนาด serialization ที่ไม่บีบอัด: RF pickle รวมชื่อ features, MLP checkpoint รวม weights/scaler/features
ขนาดต่างรูปแบบเป็นเพียง storage footprint ไม่ใช่ RAM/VRAM
''')
code('''
rf_file = RUN_DIR / 'random_forest_demo.pkl'
with rf_file.open('wb') as handle:
    pickle.dump({'model': rf, 'feature_names': FEATURES, 'seed': SEED,
                 'schema': manifest.get('feature_schema')}, handle, protocol=5)
mlp_cpu = copy.deepcopy(mlp).to('cpu').eval()
mlp_file = RUN_DIR / 'mlp_demo.pt'
torch.save({'state_dict': mlp_cpu.state_dict(), 'feature_names': FEATURES,
    'scaler_mean': torch.tensor(scaler.mean_, dtype=torch.float64),
    'scaler_scale': torch.tensor(scaler.scale_, dtype=torch.float64),
    'architecture': [len(FEATURES), 128, 64, 32, 1], 'seed': SEED}, mlp_file)

def predict_one_rf(row):
    return rf.predict_proba(np.asarray(row, dtype=np.float32).reshape(1, -1))[0, 1]

def predict_one_mlp(row):
    scaled = scaler.transform(np.asarray(row, dtype=np.float32).reshape(1, -1)).astype(np.float32)
    with torch.inference_mode():
        return float(torch.sigmoid(mlp_cpu(torch.from_numpy(scaled)))[0])

old_jobs, old_threads = rf.n_jobs, torch.get_num_threads()
rf.n_jobs = 1
torch.set_num_threads(1)
latency_rows = X_test[:min(100, len(X_test))]
timing_results = {}
with threadpool_limits(limits=1):
    for name, function in [('Random Forest', predict_one_rf), ('Deep Learning (MLP)', predict_one_mlp)]:
        for _ in range(10):
            function(latency_rows[0])
        elapsed_ms = []
        for row in latency_rows:
            began = time.perf_counter_ns()
            function(row)
            elapsed_ms.append((time.perf_counter_ns() - began) / 1e6)
        timing_results[name] = {'CPU_median_ms': float(np.median(elapsed_ms)),
                                'CPU_p95_ms': float(np.percentile(elapsed_ms, 95))}
rf.n_jobs = old_jobs
torch.set_num_threads(old_threads)
resources = pd.DataFrame(timing_results).T
resources['Train_seconds'] = [rf_train_s, mlp_train_s]
resources['Train_device'] = ['cpu', str(DEVICE)]
resources['Model_file_MiB'] = [rf_file.stat().st_size / 2**20, mlp_file.stat().st_size / 2**20]
resources['Latency_samples'] = len(latency_rows)
display(resources.round(4))
''', 'resources')

md('''
## 7. ตารางว่าค่าใดมาก/น้อยดีกว่า และใครได้ค่าดีกว่าในการรันนี้

| ค่า | ทิศทาง | ความหมาย |
|---|---|---|
| AP | มากดีกว่า | คุณภาพการจัดอันดับ phishing ตลอดช่วง precision-recall; เทียบได้บน test เดียวกัน |
| Recall | มากดีกว่า | TP/(TP+FN): จับ phishing ได้กี่ส่วน |
| FPR | น้อยดีกว่า | FP/(FP+TN): เว็บปกติถูกเตือนผิดกี่ส่วน |
| Precision | มากดีกว่า | TP/(TP+FP): สิ่งที่เตือนเป็น phishing จริงกี่ส่วน |
| F1 | มากดีกว่า | สมดุล Precision กับ Recall แต่ไม่ได้รวม TN โดยตรง |
| ROC-AUC | มากดีกว่า | แยกอันดับสอง class ได้ดีเพียงใด; ใช้คู่ AP เมื่อข้อมูลไม่สมดุล |
| Accuracy | มากดีกว่า | สัดส่วนถูกทั้งหมด; อาจดูสูงเพราะ class ใหญ่ จึงห้ามอ่านค่าเดียว |
| CPU latency / train time / file size | น้อยดีกว่า | ต้นทุนภายใต้เครื่องและวิธีวัดที่ระบุ |

ตารางต่อไปสร้างจากค่าที่รันจริง **ไม่สรุปผู้ชนะรวมด้วยการนับจำนวนช่องที่ชนะ**
ความต่าง single-seed ไม่ใช่ข้อยืนยันทางสถิติ และ Recall ที่สูงขึ้นพร้อม FPR ที่สูงขึ้นคือ trade-off
''')
code('''
metrics_for_comparison = [
    ('AP', 'higher', 'Average precision; primary metric'),
    ('Recall', 'higher', 'Phishing detected'), ('FPR', 'lower', 'Benign false alarms'),
    ('Precision', 'higher', 'Correctness of phishing alerts'), ('F1', 'higher', 'Precision-recall balance'),
    ('ROC_AUC', 'higher', 'Ranking discrimination'), ('Accuracy', 'higher', 'Overall correctness'),
    ('CPU_median_ms', 'lower', 'CPU batch-1 median latency, preprocessing included'),
    ('CPU_p95_ms', 'lower', 'CPU batch-1 p95 latency'),
    ('Train_seconds', 'lower', 'Actual training cost; check CPU/GPU difference'),
    ('Model_file_MiB', 'lower', 'Serialized storage; different formats'),
]
combined = main_results.join(resources)
comparison_rows = []
for metric, direction, meaning in metrics_for_comparison:
    a, b = float(combined.loc['Random Forest', metric]), float(combined.loc['Deep Learning (MLP)', metric])
    tie = np.isclose(a, b, atol=1e-6, rtol=0)
    winner = 'Tie' if tie else ('Random Forest' if (a > b) == (direction == 'higher') else 'Deep Learning (MLP)')
    comparison_rows.append({'Metric': metric, 'Better': direction, 'Random Forest': a,
        'Deep Learning (MLP)': b, 'MLP_minus_RF': b-a, 'Better_in_this_run': winner, 'Meaning': meaning})
comparison_table = pd.DataFrame(comparison_rows)
display(comparison_table.round(5))

ap_rf, ap_mlp = main_results.loc['Random Forest', 'AP'], main_results.loc['Deep Learning (MLP)', 'AP']
ap_text = ('ใกล้เคียงกัน' if abs(ap_rf-ap_mlp) < 1e-6 else
           ('MLP ได้ AP สูงกว่า' if ap_mlp > ap_rf else 'Random Forest ได้ AP สูงกว่า'))
summary_lines = [
    f'ขอบเขต: {RUN_CONTEXT}; โหมด {MODE}; train={len(y_train):,}, validation={len(y_val):,}, test={len(y_test):,}; 172 features',
    f'AP: RF={ap_rf:.4f}, MLP={ap_mlp:.4f} — {ap_text}ในการรันนี้',
]
for name in test_probabilities:
    row = main_results.loc[name]
    summary_lines.append(f'{name}: Recall={row.Recall:.2%}, FPR={row.FPR:.2%}, Precision={row.Precision:.2%}, F1={row.F1:.4f}; '
        f'เว็บปกติถูกเตือนผิดประมาณ {1000*row.FPR:.1f} ต่อ 1,000 เว็บปกติ และพลาด phishing ประมาณ {1000*(1-row.Recall):.1f} ต่อ 1,000 phishing '
        '(แปลงอัตราจาก test นี้ ไม่ใช่จำนวนเว็บที่เก็บเพิ่ม)')
delta_recall = main_results.loc['Deep Learning (MLP)', 'Recall'] - main_results.loc['Random Forest', 'Recall']
delta_fpr = main_results.loc['Deep Learning (MLP)', 'FPR'] - main_results.loc['Random Forest', 'FPR']
if delta_recall * delta_fpr > 0:
    summary_lines.append('Recall และ FPR เปลี่ยนไปในทิศเดียวกัน: มี trade-off ระหว่างจับ phishing กับเตือนเว็บปกติผิด')
summary_lines += [
    'ตัวเลขนี้เป็น single-seed demo บนข้อมูลพัฒนาเดิม ไม่ใช่ผลใหม่ของ RF 174 features ใน Extension',
    'ไม่ได้ยืนยันว่า algorithm หนึ่งเหนือกว่าโดยทั่วไป ไม่ใช่ fresh temporal evaluation และยังไม่ใช่ production readiness',
    'โมเดลไม่ได้ calibrate; threshold 0.5/validation-F1 ใช้เฉพาะเดโม ไม่ใช่นโยบาย 60/80 เดิม',
]
summary_text = '\\n'.join(summary_lines)
print(summary_text)
''', 'comparison')

md('''
## 8. กราฟสำหรับพรีเซนต์

แกน Confusion Matrix: แถวเป็น label จริง คอลัมน์เป็น prediction
Benign→Phishing คือ FP; Phishing→Benign คือ FN
เส้น PR ที่ดีกว่าควรรักษา Precision ได้สูงเมื่อ Recall เพิ่ม; เส้นประคือ phishing prevalence ของ test
กราฟ loss ใช้ train กับ validation เท่านั้น ไม่ใช้ test เพื่อเฝ้าดูการฝึก
''')
code('''
plt.rcParams.update({'figure.dpi': 130, 'font.size': 10})
colors = {'Random Forest': '#2563a6', 'Deep Learning (MLP)': '#d16b35'}
fig, axes = plt.subplots(1, 2, figsize=(11, 4.3))
for ax, (name, scores) in zip(axes, test_probabilities.items()):
    ConfusionMatrixDisplay.from_predictions(y_test, scores >= 0.5,
        labels=[0, 1], display_labels=['Benign', 'Phishing'], ax=ax,
        colorbar=False, cmap='Blues', values_format='d')
    ax.set_title(name + ' | threshold 0.50')
fig.tight_layout()
fig.savefig(RUN_DIR / 'confusion_matrices.png', bbox_inches='tight')
plt.show()

fig, axes = plt.subplots(1, 2, figsize=(11, 4.3))
for name, scores in test_probabilities.items():
    fpr_curve, tpr_curve, _ = roc_curve(y_test, scores)
    p, r, _ = precision_recall_curve(y_test, scores)
    axes[0].plot(fpr_curve, tpr_curve, color=colors[name],
        label=f'{name}: AUC={main_results.loc[name, "ROC_AUC"]:.3f}')
    axes[1].plot(r, p, color=colors[name],
        label=f'{name}: AP={main_results.loc[name, "AP"]:.3f}')
axes[0].plot([0, 1], [0, 1], '--', color='gray', linewidth=1)
axes[1].axhline(np.mean(y_test), linestyle='--', color='gray', label='Test prevalence')
axes[0].set(xlabel='False positive rate', ylabel='Recall / true positive rate', title='ROC')
axes[1].set(xlabel='Recall', ylabel='Precision', title='Precision–Recall')
for ax in axes:
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.02)
    ax.legend(fontsize=8)
    ax.grid(alpha=0.2)
fig.tight_layout()
fig.savefig(RUN_DIR / 'roc_pr_curves.png', bbox_inches='tight')
plt.show()

fig, axes = plt.subplots(1, 2, figsize=(11, 4.3))
history_df = pd.DataFrame(training_history)
axes[0].plot(history_df.epoch, history_df.train_loss, label='Train BCE')
axes[0].plot(history_df.epoch, history_df.val_loss, label='Validation BCE')
axes[0].axvline(best_epoch, color='gray', linestyle='--', label=f'Best epoch {best_epoch}')
axes[0].set(xlabel='Epoch', ylabel='Binary cross entropy', title='MLP learning curve')
axes[0].legend()
metric_names = ['AP', 'Precision', 'Recall', 'F1', 'FPR']
x = np.arange(len(metric_names))
for offset, name in [(-0.18, 'Random Forest'), (0.18, 'Deep Learning (MLP)')]:
    axes[1].bar(x + offset, main_results.loc[name, metric_names].to_numpy(dtype=float),
                width=0.36, label=name, color=colors[name])
axes[1].set_xticks(x, ['AP ↑', 'Precision ↑', 'Recall ↑', 'F1 ↑', 'FPR ↓'])
axes[1].set(ylim=(0, 1.05), title='Test metrics | threshold 0.50')
axes[1].legend(fontsize=8)
fig.tight_layout()
fig.savefig(RUN_DIR / 'learning_and_metrics.png', bbox_inches='tight')
plt.show()
''', 'plots')

md('''
## 9. ตรวจผลแยกแหล่งข้อมูล และสาธิตตัวอย่าง held-out

ข้อมูลหลายแหล่งอาจมีรูปแบบการเก็บ/label ต่างกัน ตารางราย source ช่วยเห็นว่าโมเดลพลาดที่แหล่งใด
แหล่งที่มี class เดียวจะไม่รายงาน FPR หรือ Recall ของ class ที่ไม่มี และ AP/AUC เป็น NaN
จำนวนตัวอย่างน้อยต้องอ่านอย่างระมัดระวัง
การสาธิตเลือกแถว test ที่ไม่เคยใช้ฝึก; ไม่มีช่องรับ URL ใหม่ เพราะไฟล์นี้รับ features ที่ precompute แล้ว
''')
code('''
source_results = []
for source in sorted(test_rows['source'].unique()):
    mask = test_rows['source'].eq(source).to_numpy()
    for name, scores in test_probabilities.items():
        yy, ss = y_test[mask], scores[mask]
        result = evaluate(name, yy, ss, 0.5)
        if not np.any(yy == 0):
            result['FPR'] = np.nan
        if not np.any(yy == 1):
            result['Recall'] = np.nan
        result['Source'] = source
        source_results.append(result)
source_results = pd.DataFrame(source_results)
display(source_results[['Source', 'Model', 'N', 'Phishing_prevalence', 'Recall', 'FPR', 'F1', 'AP']].round(4))

EXAMPLE_INDEX = 0  # change to any integer from 0 through len(y_test)-1
assert 0 <= EXAMPLE_INDEX < len(y_test)
example = pd.DataFrame([{'Model': name, 'Score_not_calibrated': float(scores[EXAMPLE_INDEX]),
    'Prediction_at_0.5': 'Phishing' if scores[EXAMPLE_INDEX] >= 0.5 else 'Benign',
    'Actual_label': 'Phishing' if y_test[EXAMPLE_INDEX] == 1 else 'Benign'}
    for name, scores in test_probabilities.items()])
display(example)
''', 'source-and-demo')

md('''
## 10. บันทึกและดาวน์โหลดผลสำหรับพรีเซนต์

`results.zip` มีตาราง CSV, กราฟ PNG, สรุปภาษาไทย, environment/config, provenance และโมเดลที่ฝึกจากการรันนี้
CSV เก็บค่าจริงเต็ม precision; ตารางบนจอปัดเพื่ออ่านง่าย
ไฟล์โมเดลใช้กับข้อมูลที่มีลำดับ features เดียวกันเท่านั้น และห้ามโหลด pickle จากผู้ที่ไม่เชื่อถือ
บันทึก notebook ด้วย File → Save a copy in Drive / Download .ipynb เพื่อเก็บ outputs ก่อน runtime หมดอายุ
''')
code('''
main_results.to_csv(RUN_DIR / 'metrics_threshold_0_5.csv', encoding='utf-8-sig')
tuned_results.to_csv(RUN_DIR / 'metrics_validation_f1_threshold.csv', encoding='utf-8-sig')
resources.to_csv(RUN_DIR / 'resource_comparison.csv', encoding='utf-8-sig')
comparison_table.to_csv(RUN_DIR / 'metric_comparison.csv', index=False, encoding='utf-8-sig')
source_results.to_csv(RUN_DIR / 'metrics_by_source.csv', index=False, encoding='utf-8-sig')
history_df.to_csv(RUN_DIR / 'mlp_training_history.csv', index=False)
(RUN_DIR / 'summary_TH.txt').write_text(summary_text, encoding='utf-8')
(RUN_DIR / 'environment.json').write_text(json.dumps(environment, ensure_ascii=False, indent=2), encoding='utf-8')
(RUN_DIR / 'dataset_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
config_record = {'seed': SEED, 'mode': MODE, 'config': CONFIG, 'primary_metric': PRIMARY_METRIC,
    'batch_size': BATCH_SIZE, 'learning_rate': LEARNING_RATE,
    'mlp_layers': [len(FEATURES), 128, 64, 32, 1], 'best_epoch': best_epoch,
    'threshold_main': 0.5, 'thresholds_validation_f1': thresholds_f1,
    'class_weighting': 'none for both models', 'feature_names': FEATURES,
    'dataset_csv_sha256': csv_sha256, 'rows_used': len(df),
    'split_counts': {split: len(arrays[split][1]) for split in arrays},
    'latency_protocol': 'CPU 1 thread, batch1, warmup10, up to100 rows, preprocessing included; no URL/network',
    'statistical_significance_tested': False, 'production_ready': False,
    'calibrated': False, 'runtime_verified_on_colab': RUN_CONTEXT == 'Google Colab'}
(RUN_DIR / 'run_config.json').write_text(json.dumps(config_record, ensure_ascii=False, indent=2), encoding='utf-8')
prediction_rows = test_rows[['source', 'label']].copy()
for name, scores in test_probabilities.items():
    prediction_rows[name + '_score'] = scores
prediction_rows.to_csv(RUN_DIR / 'test_predictions_no_urls.csv', index=False, encoding='utf-8-sig')
zip_result = RUN_DIR.parent / 'results.zip'
with zipfile.ZipFile(zip_result, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(RUN_DIR.iterdir()):
        if path.is_file():
            archive.write(path, arcname=path.name)
print('Saved:', zip_result.resolve())
print('Run context:', RUN_CONTEXT)
if not globals().get('SKIP_DOWNLOAD', False):
    try:
        from google.colab import files
        files.download(str(zip_result))
    except ImportError:
        print('Local run: open results.zip from the output folder.')
''', 'export')

md('''
## ข้อจำกัดและแหล่งอ้างอิง

- ข้อมูล demo เป็น subset ของ development pool เดิมจากหลายผู้เผยแพร่ การกันโดเมนไม่ได้ลบ publisher artifacts
  หรือยืนยันการเห็นข้อมูลในประวัติเดิมครบทั้งหมด และไม่ได้เป็นการทดสอบตามเวลาข้างหน้า
- การจัดสัดส่วน source/class ทำให้ prevalence อาจต่างจากโลกจริง Precision/AP จึงไม่ควรยกไปอ้างกับ Internet ทั้งหมด
- RF และ MLP ใช้ features เหมือนกัน แต่ architecture และวิธี optimization ต่างกัน ไม่มี exhaustive tuning หรือหลาย seed
  ผลบอกได้ว่าใครได้ค่าดีกว่า **ในการรันนี้** ไม่ใช่ข้อพิสูจน์ว่า ML/DL กลุ่มใดเหนือกว่า
- ไม่ใช้ 2 publisher-reference features, ไม่ใช้ forest/calibrator เดิม, ไม่เรียกผลนี้ว่า RF 174 features ในระบบจริง
- source เดิมอาจมีเงื่อนไขสิทธิ์/attribution ต่างกัน โดยเฉพาะ DeepURLBench (CC BY-NC 4.0 ตามหลักฐานโครงการ)
  ชุดนี้จัดสำหรับพรีเซนต์ภายในงานวิชาการ ไม่ได้อัปโหลดเผยแพร่ข้อมูลให้สาธารณะ

เอกสารอ่านต่อ:
[PyTorch Quickstart](https://docs.pytorch.org/tutorials/beginner/basics/quickstart_tutorial.html),
[scikit-learn metrics](https://scikit-learn.org/stable/modules/model_evaluation.html),
[Average Precision](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.average_precision_score.html),
[Colab FAQ](https://research.google.com/colaboratory/faq.html).
ต้นทาง dataset: [PhreshPhish](https://huggingface.co/datasets/phreshphish/phreshphish),
[URL-Phish](https://data.mendeley.com/datasets/65z9twcx3r/1),
[Web page phishing detection](https://data.mendeley.com/datasets/c2gw7fy2j4/3),
[PhiUSIIL](https://archive.ics.uci.edu/dataset/967/phiusiil+phishing+url+dataset),
[DeepURLBench](https://github.com/deepinstinct-algo/DeepURLBench).
ที่มาและ hash ของ source จริงดู `manifest.json` ที่แนบกับ dataset
''')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for i, cell in enumerate(cells):
        cell['id'] = f'phish-radar-{i:02d}'
    notebook = {'cells': cells, 'metadata': {
        'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
        'language_info': {'name': 'python'},
        'colab': {'name': 'Phish_Radar_RF_vs_DL_Colab.ipynb', 'provenance': []}},
        'nbformat': 4, 'nbformat_minor': 5}
    path = OUT / 'Phish_Radar_RF_vs_DL_Colab.ipynb'
    path.write_text(json.dumps(notebook, ensure_ascii=False, indent=1), encoding='utf-8')
    for i, cell in enumerate(cells):
        if cell['cell_type'] == 'code':
            compile(cell['source'], f'<cell-{i}>', 'exec')
    print(path)
    print(f'{len(cells)} cells; all code cells compile.')


if __name__ == '__main__':
    main()
