"""Audit recovered URL data without evaluating a detector on reserved test rows."""
import csv,json,hashlib,sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from domain_parts import domain_parts
from build_dataset import normalized_url
out=ROOT/'backend/data/recovered-20261004'
m=json.loads((out/'recovery-manifest.json').read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
model_hash_before=sha(ROOT/'backend/model.pkl')
for info in [*m['outputs'].values(),m['development_deduplicated'],m['education_review_candidates'],m['development_review_required']]:
    assert sha(out/info['csv'])==info['sha256'],info['csv']
labels=Counter(); seen=set(); domains=set(); edu=Counter()
with (out/m['development_deduplicated']['csv']).open(encoding='utf-8',newline='') as f:
    for r in csv.DictReader(f):
        assert r['publisher_split']=='train' and r['url'] not in seen
        assert r['label'] in {'0','1'}
        seen.add(r['url']); domains.add(r['group']); labels[r['label']]+=1
with (out/m['education_review_candidates']['csv']).open(encoding='utf-8',newline='') as f:
    for r in csv.DictReader(f):
        assert r['url'] in seen
        edu[r['label']]+=1
reserved=Counter(); reserved_domains=set(); overlapping=Counter(); candidates={}; conflicts=set()
with (out/m['outputs']['test']['csv']).open(encoding='utf-8',newline='') as f:
    for r in csv.DictReader(f):
        assert r['publisher_split']=='test'
        reserved[r['label']]+=1
        u=normalized_url(r['url'])
        if not u:
            overlapping['unsupported_urls']+=1;continue
        try: d=domain_parts(urlsplit(u).hostname)[0]
        except (ValueError,UnicodeError):
            overlapping['unsupported_urls']+=1;continue
        reserved_domains.add(d)
        if d in domains: overlapping['rows_with_development_domain']+=1
        if u in seen: overlapping['exact_normalized_urls_in_development']+=1
        if d in domains: continue
        if u in candidates:
            overlapping['duplicate_urls_within_disjoint_test']+=1
            if candidates[u]['label']!=r['label']: conflicts.add(u)
        else:
            candidates[u]=dict(r,url=u,group=d)
for u in conflicts: candidates.pop(u,None)
candidate_path=out/'quarantined-domain-disjoint-test.csv'
with candidate_path.open('w',encoding='utf-8',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=['url','label','source','observed_at','time_precision','publisher_split','group'])
    writer.writeheader(); writer.writerows(candidates.values())
candidate_labels=Counter(r['label'] for r in candidates.values())
assert not {r['group'] for r in candidates.values()} & domains
assert sha(ROOT/'backend/model.pkl')==model_hash_before
assert m['historical_train_projection_hashes_matched']==56
report={'development_rows':sum(labels.values()),'development_labels':dict(labels),'development_domains':len(domains),'education_review_labels':dict(edu),'reserved_test_labels':dict(reserved),'test_development_overlap':dict(overlapping),'overlapping_registered_domains':len(reserved_domains&domains),'model_unchanged':True,'old_projection_hashes_verified':56,'test_scored':False,'prior_exposure_audit_complete':m['prior_exposure_audit_complete']}
report['domain_disjoint_test_candidate']={'csv':candidate_path.name,'sha256':sha(candidate_path),'rows':len(candidates),'labels':dict(candidate_labels),'conflicting_urls_removed':len(conflicts),'status':'Quarantined: disjoint from recovered development data, but original exposure audit is incomplete.'}
(ROOT/'output/dataset-recovery/audit.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report))
