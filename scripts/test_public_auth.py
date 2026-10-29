"""Exercise real HTTPS register/login/cookies; remove only the generated test user."""
import secrets
import sys
from pathlib import Path

import httpx
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from database import open_session


def main(origin):
    username = 'publictest_' + secrets.token_hex(6)
    password = secrets.token_urlsafe(24)
    headers = {'Origin': origin, 'X-Phish-Radar-Client': 'web-app'}
    payload = {'username': username, 'email': username + '@example.com', 'password': password}
    try:
        with httpx.Client(base_url=origin, timeout=45, trust_env=False,
                          headers={'X-Phish-Radar-Client': 'web-app'}) as client:
            def expect(response, status, label):
                assert response.status_code == status, f'{label}: expected {status}, got {response.status_code}'
                print(f'{label}: {status}')
                return response

            rejected = client.post('/auth/register', headers={**headers, 'Origin': 'https://unrelated.trycloudflare.com'}, json=payload)
            expect(rejected, 403, 'Unrelated origin rejected')
            response = expect(client.post('/auth/register', headers=headers, json=payload), 201, 'Public registration')
            assert response.json()['role'] == 'user'
            assert 'secure' in response.headers['set-cookie'].lower()
            assert 'httponly' in response.headers['set-cookie'].lower()
            me = expect(client.get('/auth/me'), 200, 'Session cookie without Origin header')
            assert me.json()['username'] == username
            expect(client.post('/auth/logout', headers=headers), 204, 'Logout')
            expect(client.post('/auth/login', headers=headers, json={'identifier': payload['email'], 'password': password}), 200, 'Public login')
            expect(client.get('/auth/me'), 200, 'Restored login session')
            expect(client.post('/auth/logout', headers=headers), 204, 'Final logout')
    finally:
        with open_session() as db:
            user_id = db.execute(text('SELECT UserId FROM Users WHERE Username=:name'), {'name': username}).scalar_one_or_none()
            if user_id is not None:
                db.execute(text('DELETE FROM Sessions WHERE UserId=:id'), {'id': user_id})
                db.execute(text('DELETE FROM Users WHERE UserId=:id AND Username=:name'), {'id': user_id, 'name': username})
                db.commit()
                print('Temporary test account removed.')


if __name__ == '__main__':
    main(sys.argv[1].rstrip('/'))
