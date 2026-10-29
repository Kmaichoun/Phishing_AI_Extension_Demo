import csv,json,sys,tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path('scripts').resolve()))
import recover_research_data as m
with tempfile.TemporaryDirectory(dir='tmp') as td:
    root=Path(td); (root/'backend/data/simple_v4').mkdir(parents=True)
    old={'sources':{'phreshphish_train_v1_0_1':{'files':[],'attribution':'Fixture'},'urlphish_v1':{'url':'https://example.org','license':'CC BY 4.0','attribution':'Fixture'}}}
    (root/'backend/data/simple_v4/publisher_sources.json').write_text(json.dumps(old))
    def project(meta,cache):
        rows=([['https://www.ku.ac.th/th','0','2025-01-01'],['https://www.ku.ac.th/th','0','2025-01-02'],['https://bad.example/','0','2025-01-01'],['https://bad.example/','1','2025-01-02'],['university.edu/path','0','2025-01-01']] if 'train' in meta['path'] else [['https://reserved.example/','1','2025-01-01']])
        p=cache/(Path(meta['path']).stem+'.csv')
        with p.open('w',encoding='utf-8',newline='') as f:
            w=csv.writer(f);w.writerow(['url','label','observed_at']);w.writerows(rows)
        return {'file':meta['path'],'rows':len(rows),'sha256':m.sha(p)}
    def ext(cache):
        p=cache/'urlphish-v1.csv';p.write_text('url,label\nhttps://college.edu/,0\n');return p
    out=root/'recovered'
    with patch.object(m,'ROOT',root),patch.object(m,'listing',lambda:[{'path':'data/train-000.parquet'},{'path':'data/test-000.parquet'}]),patch.object(m,'project_file',project),patch.object(m,'download_external',ext),patch.object(sys,'argv',['recover','--output',str(out)]):
        m.main()
    report=json.loads((out/'recovery-manifest.json').read_text())
    rows=list(csv.DictReader((out/'development-deduplicated.csv').open()))
    assert len(rows)==2 and all(r['label']=='0' for r in rows)
    assert all('reserved.example' not in r['url'] and 'bad.example' not in r['url'] for r in rows)
    assert report['development_cleanup']['conflicting_normalized_urls_removed']==1
    assert report['development_cleanup']['invalid']==1
    assert len(list(csv.DictReader((out/'development-review-required.csv').open())))==1
    assert len(list(csv.DictReader((out/'education-review-candidates.csv').open())))==2
    assert report['production_ready'] is False and report['test_scored'] is False
    assert report['prior_exposure_audit_complete'] is False
print('PASS: partition isolation, conflicts, normalization rejects, education review, and nondeployment status')
