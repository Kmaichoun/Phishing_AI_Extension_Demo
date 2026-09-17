"""Model workflow unit/API tests; uses a disposable SQLite DB, never real accounts."""
from __future__ import annotations

from copy import deepcopy
import csv
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'backend'))
sys.path.insert(0, str(ROOT/'scripts'))
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app import app
from auth_router import require_authenticated_user, _session_scope
from model_registry import ARTIFACTS, SCORE_CODE, atomic_json, counts_metrics, experiment_path, gate_checks, sha256, verified_analysis
from manage_model import install, locked
from train_simple_model import read_reviewed_rows


def passing_report():
    metrics = counts_metrics([0]*5000 + [1]*100, [0]*5000 + [100]*100, 70)
    return {'quality': {'group_overlap': 0, 'all_splits_have_both_labels': True,
                        'previously_seen_holdout_domains': 0, 'synthetic_rows': 0,
                        'unverified_benign_rows': 0, 'external_test_validated': True}, 'regression_passed': True,
            'candidate': {'warning': metrics, 'blocking': metrics},
            'baseline': {'warning': metrics, 'blocking': metrics},
            'external': {stage: metrics for stage in ['warning','blocking','warning_baseline','blocking_baseline']}}


class ModelWorkflowTests(unittest.TestCase):
    def test_confidence_bound_and_no_negative_samples(self):
        small = counts_metrics([0]*10 + [1], [0]*10 + [100], 50)
        self.assertEqual(small['fpr'], 0)
        self.assertGreater(small['fpr_upper_95'], .001)
        self.assertIsNone(counts_metrics([1], [100], 50)['fpr_upper_95'])
        self.assertEqual(counts_metrics([0,1], [50,49.9], 50)['fp'], 1)

    def test_gates_reject_quality_regression_and_recall_failures(self):
        report = passing_report()
        self.assertTrue(all(c['passed'] for c in gate_checks(report)))
        for key in ['group_overlap', 'previously_seen_holdout_domains', 'synthetic_rows', 'unverified_benign_rows']:
            modified = deepcopy(report); modified['quality'][key] = 1
            self.assertFalse(all(c['passed'] for c in gate_checks(modified)))
        report['candidate']['blocking'] = {**report['candidate']['blocking'], 'recall': .1}
        self.assertFalse(all(c['passed'] for c in gate_checks(report)))
        self.assertFalse(all(c['passed'] for c in gate_checks({'promotion_ready': True})))

    def test_safe_paths(self):
        for name in ['../model.pkl', 'simple_../../outside', 'C:/outside', 'simple_x/other']:
            with self.assertRaises(ValueError): experiment_path(name)

    def test_integrity_invalidates_stale_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); path = root/'simple_test'; path.mkdir()
            production = root/'model.pkl'; production.write_bytes(b'original')
            (root/'training_urls.csv').write_bytes(b'url,label\n')
            for name in ARTIFACTS: (path/name).write_bytes(b'test-only')
            report = passing_report()
            report.update(artifacts={f: sha256(path/f) for f in ARTIFACTS}, baseline_sha256=sha256(production),
                          legacy_dataset_sha256=sha256(root/'training_urls.csv'),
                          score_code={p: sha256(ROOT/p) for p in SCORE_CODE},
                          experiment_inventory={'simple_test': sha256(path/'dataset.csv')})
            atomic_json(path/'error_analysis.json', report)
            self.assertTrue(verified_analysis(path, production)['promotion_ready'])
            (path/'candidate.pkl').write_bytes(b'changed')
            with self.assertRaises(ValueError): verified_analysis(path, production)
            (path/'candidate.pkl').write_bytes(b'test-only')
            production.write_bytes(b'new production')
            with self.assertRaises(ValueError): verified_analysis(path, production)

    def test_backup_rollback_and_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); production = root/'model.pkl'; registry = root/'registry'
            source = root/'candidate.pkl'; production.write_bytes(b'incumbent'); source.write_bytes(b'candidate')
            original = sha256(production)
            with locked(registry):
                with self.assertRaises(FileExistsError):
                    with locked(registry): pass
                event = install(source, sha256(source), 'test-promote', production, registry)
            self.assertEqual(event['status'], 'installed')
            self.assertEqual(sha256(registry/(original+'.pkl')), original)
            with locked(registry): install(registry/(original+'.pkl'), original, 'test-rollback', production, registry)
            self.assertEqual(sha256(production), original)
            with self.assertRaises(ValueError): install(source, '0'*64, 'bad-hash', production, registry)
            self.assertEqual(sha256(production), original)

    def test_publisher_manifest_is_bound_to_verified_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); path = root/'simple_test'; path.mkdir()
            production = root/'model.pkl'; production.write_bytes(b'original')
            (root/'training_urls.csv').write_bytes(b'url,label\n')
            for name in ARTIFACTS: (path/name).write_bytes(b'fixture')
            atomic_json(path/'publisher_sources.json', {'sources': {'fixture': {'license':'test only'}}})
            atomic_json(path/'evaluation.json', {'publisher_sources_sha256':sha256(path/'publisher_sources.json')})
            report = passing_report()
            report.update(artifacts={f: sha256(path/f) for f in (*ARTIFACTS,'publisher_sources.json')},
                          baseline_sha256=sha256(production),
                          legacy_dataset_sha256=sha256(root/'training_urls.csv'),
                          score_code={p: sha256(ROOT/p) for p in SCORE_CODE},
                          experiment_inventory={'simple_test':sha256(path/'dataset.csv')})
            atomic_json(path/'error_analysis.json', report)
            self.assertTrue(verified_analysis(path, production)['promotion_ready'])
            (path/'publisher_sources.json').unlink()
            with self.assertRaises(FileNotFoundError): verified_analysis(path, production)

    def test_reviewed_data_requires_original_url_and_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'review.csv'
            path.write_text('sanitized_url,reviewed_label\nhttps://example.com,safe\n', encoding='utf-8')
            with self.assertRaises(ValueError): list(read_reviewed_rows(path))
            fields = ['url','label','source','observed_at','label_evidence','reviewed_by']
            row = ['https://example.com/?q=test','0','test_fixture','2026-01-01T00:00:00Z','test only','test reviewer']
            with path.open('w', encoding='utf-8', newline='') as handle:
                writer = csv.writer(handle); writer.writerow(fields); writer.writerow(row)
            self.assertEqual(len(list(read_reviewed_rows(path))), 1)


class ModelApiTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread':False}, poolclass=StaticPool)
        with self.engine.begin() as db:
            db.execute(text('CREATE TABLE SearchHistory (HistoryId INT, Url TEXT, CreatedAt TEXT, Decision TEXT, FinalScore INT, ModelVersion TEXT, PolicyVersion TEXT, WarningThreshold FLOAT, BlockingThreshold FLOAT)'))
            db.execute(text('CREATE TABLE ScanFeedback (FeedbackId INT, HistoryId INT, UserLabel TEXT, ReviewStatus TEXT, ReviewedAt TEXT, ReviewNote TEXT)'))
            db.execute(text("INSERT INTO SearchHistory VALUES (1,'https://example.com/path','2026-09-01','warn',70,'v1','p1',60,90)"))
            for i,(label,status) in enumerate([('safe','confirmed'),('dangerous','confirmed'),('unsure','confirmed'),('safe','pending'),('safe','dismissed')]):
                db.execute(text('INSERT INTO ScanFeedback VALUES (:id,1,:label,:status,\'2026-09-02\',\'private reviewer note\')'), dict(id=i+1,label=label,status=status))
        def session():
            with Session(self.engine) as db: yield db
        app.dependency_overrides[_session_scope] = session
        self.client = TestClient(app, headers={'Origin':'http://127.0.0.1:5505','X-Phish-Radar-Client':'web-app'})

    def tearDown(self):
        app.dependency_overrides.clear()
        self.client.close(); self.engine.dispose()

    def role(self, value):
        app.dependency_overrides[require_authenticated_user] = lambda: {'Role':value,'UserId':1}

    def test_permissions_and_untrusted_origin(self):
        for endpoint in ['/workspace/admin/models', '/workspace/admin/feedback-export']:
            self.assertEqual(self.client.get(endpoint).status_code, 401)
            self.role('user'); self.assertEqual(self.client.get(endpoint).status_code, 403)
            self.role('admin')
            self.assertEqual(self.client.get(endpoint, headers={'Origin':'https://untrusted.example'}).status_code, 403)
            app.dependency_overrides.pop(require_authenticated_user)

    def test_model_catalog_and_feedback_export(self):
        self.role('admin')
        with patch('workspace_router.catalog', return_value={'items': []}):
            self.assertEqual(self.client.get('/workspace/admin/models').json(), {'items': []})
        response = self.client.get('/workspace/admin/feedback-export')
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json(); self.assertEqual(data['total'], 2)
        self.assertEqual({r['reviewed_label'] for r in data['items']}, {'safe','dangerous'})
        self.assertTrue(all(r['training_eligible'] is False for r in data['items']))
        self.assertNotIn('private reviewer note', response.text)
        self.assertEqual(self.client.get('/workspace/admin/feedback-export?offset=30').json()['items'], [])
        self.assertEqual(self.client.get('/workspace/admin/feedback-export?offset=-1').status_code, 422)


if __name__ == '__main__':
    unittest.main(verbosity=2)
