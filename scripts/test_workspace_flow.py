"""Integration coverage for workspace permissions and history, using disposable local accounts."""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from fastapi.testclient import TestClient
from sqlalchemy import text
from app import app
from database import engine, open_session, database_status

HEADERS = {'Origin': 'http://127.0.0.1:5505', 'X-Phish-Radar-Client': 'web-app'}
PASSWORD = 'Disposable-Workspace-2026!'


def local_only():
    if engine.url.host not in {'127.0.0.1', 'localhost', '::1'}:
        raise RuntimeError('Workspace integration tests only run against a local database.')
    assert database_status()['workspace_schema_ready'], 'Apply SQL migrations 005 and 006 first.'
    with engine.connect() as connection:
        assert connection.execute(text('SELECT @@session.time_zone')).scalar_one() == '+00:00'


def expect(response, status):
    assert response.status_code == status, (status, response.status_code, response.text)
    return response.json() if response.content else None


def client():
    return TestClient(app, base_url='http://127.0.0.1:8765', headers=HEADERS)


def create(account, name):
    return expect(account.post('/auth/register', json={
        'username': name, 'email': name + '@example.com', 'password': PASSWORD,
        'device_name': name + ' primary',
    }), 201)['user_id']


def login(account, name, device):
    expect(account.post('/auth/login', json={
        'identifier': name, 'password': PASSWORD, 'device_name': device,
    }), 200)


def history(account, url, decision='warn'):
    return expect(account.post('/history', json={
        'url': url, 'rule_score': 12, 'ml_score': 85, 'risk_score': 72,
        'final_score': 72, 'decision': decision, 'warning_threshold': 60,
        'blocking_threshold': 90, 'model_version': 'workspace-test',
        'policy_version': 'workspace-test', 'source': 'qr-scanner',
        'layer_results': {'audit': {'risk_formula': 'test policy'}},
    }), 201)


def cleanup(ids):
    # IDs are collected only from accounts created by this test run.
    with open_session() as db:
        for uid in ids:
            for table, column in [('ScanFeedback', 'UserId'), ('AuditEvents', 'ActorUserId'),
                                  ('SearchHistory', 'UserId'), ('Sessions', 'UserId'),
                                  ('UserDevices', 'UserId'), ('Users', 'UserId')]:
                db.execute(text(f'DELETE FROM {table} WHERE {column}=:uid'), {'uid': uid})
        db.commit()
        for uid in ids:
            assert db.execute(text('SELECT COUNT(*) FROM Users WHERE UserId=:uid'), {'uid': uid}).scalar_one() == 0


def main():
    local_only()
    suffix = uuid.uuid4().hex[:10]
    names = ['wsqa_' + role + '_' + suffix for role in ['admin', 'member', 'other']]
    ids = []
    admin, member, other, second = client(), client(), client(), client()
    try:
        for account, name in zip([admin, member, other], names):
            ids.append(create(account, name))
        with open_session() as db:
            db.execute(text("UPDATE Users SET Role='admin' WHERE UserId=:uid"), {'uid': ids[0]})
            db.commit()

        expect(client().get('/workspace/security'), 401)
        for path in ['/workspace/admin/users', '/workspace/admin/feedback', '/workspace/admin/audit',
                     '/workspace/admin/models', '/workspace/admin/feedback-export']:
            expect(member.get(path), 403)
            expect(client().get(path), 401)
        models = expect(admin.get('/workspace/admin/models'), 200)
        assert isinstance(models, dict)
        expect(admin.get('/workspace/admin/users', headers={'Origin': 'https://untrusted.example'}), 403)
        expect(member.patch(f'/workspace/admin/users/{ids[2]}', json={'role': 'admin', 'active': True}), 403)
        expect(admin.patch(f'/workspace/admin/users/{ids[0]}', json={'role': 'user', 'active': False}), 400)

        first = history(member, 'https://name:secret@example.com/path?token=secret#fragment')
        second_history = history(member, 'https://example.org/next', 'allow')
        assert first['url'] == 'https://example.com/path'
        assert first['source'] == 'qr-scanner'
        assert first['layer_results']['audit']['risk_formula'] == 'test policy'
        assert expect(other.get('/history'), 200)['total'] == 0
        assert expect(member.get('/history', params={'q': 'example.com', 'decision': 'warn'}), 200)['total'] == 1
        assert expect(member.get('/history', params={'decision': 'block'}), 200)['total'] == 0
        page = expect(member.get('/history', params={'limit': 1, 'offset': 1}), 200)
        assert page['total'] == 2 and len(page['items']) == 1 and page['items'][0]['history_id'] == first['history_id']
        day = first['created_at'][:10]
        assert expect(member.get('/history', params={'date_from': day, 'date_to': day}), 200)['total'] == 2
        expect(member.get('/history', params={'date_from': '2026-09-11', 'date_to': '2026-09-10'}), 422)
        expect(member.get('/history', params={'decision': 'invalid'}), 422)

        payload = {'history_id': first['history_id'], 'user_label': 'safe'}
        expect(other.post('/workspace/feedback', json=payload), 404)
        expect(member.post('/workspace/feedback', json=payload), 200)
        expect(member.post('/workspace/feedback', json=payload), 409)
        queue = expect(admin.get('/workspace/admin/feedback'), 200)
        report = next(item for item in queue['items'] if item['username'] == names[1])
        expect(member.patch(f"/workspace/admin/feedback/{report['id']}", json={'status': 'confirmed', 'note': 'test'}), 403)
        expect(admin.patch(f"/workspace/admin/feedback/{report['id']}", json={'status': 'confirmed', 'note': '   '}), 422)
        expect(admin.patch(f"/workspace/admin/feedback/{report['id']}", json={'status': 'confirmed', 'note': 'Reviewed test example URL'}), 200)
        expect(admin.patch(f"/workspace/admin/feedback/{report['id']}", json={'status': 'dismissed', 'note': 'cannot overwrite'}), 409)
        exported = expect(admin.get('/workspace/admin/feedback-export'), 200)
        reviewed = next(item for item in exported['items'] if item['feedback_id'] == report['id'])
        assert reviewed['sanitized_url'] == 'https://example.com/path'
        assert reviewed['reviewed_label'] == 'safe' and reviewed['reviewed_at']
        assert reviewed['training_eligible'] is False
        assert not {'username', 'email', 'password', 'note', 'device_key'} & set(reviewed)
        expect(admin.get('/workspace/admin/feedback-export', params={'offset': -1}), 422)
        stats = expect(member.get('/workspace/stats'), 200)
        assert stats['totals']['total'] == 2 and stats['totals']['warned'] == 1
        assert stats['feedback']['reported_false_positives'] == stats['feedback']['confirmed_false_positives'] == 1

        login(second, names[1], 'Disposable second browser')
        security = expect(member.get('/workspace/security'), 200)
        current = next(s for s in security['sessions'] if s['current'])
        remote = next(s for s in security['sessions'] if not s['current'])
        expect(member.delete('/workspace/sessions/' + current['id']), 400)
        expect(other.delete('/workspace/sessions/' + remote['id']), 404)
        expect(member.delete('/workspace/sessions/' + remote['id']), 200)
        expect(second.get('/auth/me'), 401)
        login(second, names[1], 'Disposable second browser')
        security = expect(member.get('/workspace/security'), 200)
        device = next(d for d in security['devices'] if not d['current'])
        own = next(d for d in security['devices'] if d['current'])
        expect(member.delete(f"/workspace/devices/{own['id']}"), 400)
        expect(other.delete(f"/workspace/devices/{device['id']}"), 404)
        expect(member.delete(f"/workspace/devices/{device['id']}"), 200)
        expect(second.get('/auth/me'), 401)
        assert expect(member.get('/history', params={'device_id': own['id']}), 200)['total'] == 2
        assert expect(member.get('/history', params={'device_id': device['id']}), 200)['total'] == 0

        # Role changes must be checked server-side and invalidate old sessions.
        expect(admin.patch(f'/workspace/admin/users/{ids[2]}', json={'role': 'admin', 'active': True}), 200)
        expect(other.get('/auth/me'), 401)
        login(other, names[2], 'Disposable admin browser')
        expect(other.get('/workspace/admin/users'), 200)
        expect(admin.patch(f'/workspace/admin/users/{ids[2]}', json={'role': 'user', 'active': False}), 200)
        expect(other.get('/workspace/admin/users'), 401)
        expect(other.post('/auth/login', json={'identifier': names[2], 'password': PASSWORD, 'device_name': 'blocked'}), 401)

        expect(member.delete('/history'), 200)
        assert expect(member.get('/history'), 200)['total'] == 0
        with open_session() as db:
            assert db.execute(text('SELECT COUNT(*) FROM ScanFeedback WHERE UserId=:uid'), {'uid': ids[1]}).scalar_one() == 0
        audit = expect(admin.get('/workspace/admin/audit'), 200)
        actions = {item['action'] for item in audit['items'] if item['actor'] in names}
        assert {'history.clear', 'session.revoke', 'device.revoke', 'user.update', 'feedback.review'} <= actions
        print('Workspace integration passed: authentication, admin authorization, owner isolation,')
        print('session/device revocation, history filters/pagination, feedback review/export, Model Lab, audit and cleanup.')
    finally:
        cleanup(ids)


if __name__ == '__main__':
    main()
