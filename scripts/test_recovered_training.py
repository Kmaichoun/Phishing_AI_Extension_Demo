"""Check dataset integrity and non-degenerate FP-constrained threshold selection."""
from pathlib import Path
from tempfile import TemporaryDirectory
import csv
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from train_recovered_rf import partition, read_rows, cutoff, subgroup_metrics
from model_registry import sha256

# With enough benign examples, the Wilson bound is estimable, and positives
# remain detected rather than achieving zero FP by predicting everything safe.
y=np.array([0]*5000+[1]*1000)
p=np.array([.1]*4995+[.8]*5+[.95]*1000)
warning,wm=cutoff(y,p,.01)
blocking,bm=cutoff(y,p,.001,warning)
assert warning<=blocking and wm['recall']==bm['recall']==1.0
assert wm['false_positive_rate_upper_95']<=.01
assert bm['false_positive_rate_upper_95']<=.001
assert blocking>.8
try:
    cutoff(np.array([0,1]),np.array([.1,.9]),.001)
    raise AssertionError('Small samples cannot substantiate a 0.1% Wilson ceiling')
except ValueError:pass
assert partition('ku.ac.th')==partition('ku.ac.th')
only_phish=subgroup_metrics(np.array([1,1]),np.array([.95,.1]),.8)
assert only_phish['false_positive_rate'] is None and only_phish['recall']==.5
with TemporaryDirectory(dir=ROOT/'tmp') as name:
    path=Path(name)/'rows.csv'
    with path.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['url','label','group','publisher_split'])
        w.writeheader();w.writerow({'url':'https://www.ku.ac.th/th','label':'0','group':'ku.ac.th','publisher_split':'train'})
    assert read_rows(path,sha256(path),'train')[0]['group']=='ku.ac.th'
    for expected_hash,split in [('incorrect','train'),(sha256(path),'test')]:
        try:
            read_rows(path,expected_hash,split)
            raise AssertionError('Tampered data or publisher test in development must be rejected')
        except ValueError:pass
print('PASS: pinned input integrity, publisher partition checks and non-degenerate Wilson-constrained cutoffs')
