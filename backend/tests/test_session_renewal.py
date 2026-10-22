import hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import SESSION_IDLE, SESSION_MAX_AGE
from app.migrations import upgrade_login_sessions
from app.models import LoginSession, now
from conftest import login


def session_key(client):
    return hashlib.sha256(client.cookies.get('yandu_session').encode()).hexdigest()


def test_login_cookie_and_foreground_renewal(client, app, monkeypatch):
    instant = now()
    monkeypatch.setattr('app.main.now', lambda: instant)
    result = client.post('/api/v1/auth/demo', json={'profile': 'buyer'})
    assert 'Max-Age=604800' in result.headers['set-cookie']
    assert 'HttpOnly' in result.headers['set-cookie'] and 'SameSite=strict' in result.headers['set-cookie']
    key = session_key(client)
    instant += timedelta(days=6)
    # Polling authenticated endpoints must not extend the session.
    assert client.get('/api/v1/conversations').status_code == 200
    with app.state.session_factory() as db:
        original = db.get(LoginSession, key).expires_at
        assert original == instant + timedelta(days=1)
    result = client.post('/api/v1/auth/refresh')
    assert result.status_code == 200
    assert 'Max-Age=604800' in result.headers['set-cookie']
    with app.state.session_factory() as db:
        assert db.get(LoginSession, key).expires_at == instant + SESSION_IDLE
    instant += timedelta(minutes=30)
    result = client.post('/api/v1/auth/refresh')
    assert result.status_code == 200
    with app.state.session_factory() as db:
        # Database writes are throttled, while the cookie follows the server deadline.
        assert db.get(LoginSession, key).expires_at == instant + SESSION_IDLE - timedelta(minutes=30)
    assert 'Max-Age=603000' in result.headers['set-cookie']


@pytest.mark.parametrize('kind', ['idle', 'absolute'])
def test_expired_sessions_cannot_be_renewed(client, app, kind):
    login(client)
    with app.state.session_factory() as db:
        row = db.get(LoginSession, session_key(client))
        if kind == 'idle':
            row.expires_at = now() - timedelta(seconds=1)
        else:
            row.created_at = now() - SESSION_MAX_AGE
        db.commit()
    assert client.post('/api/v1/auth/refresh').status_code == 401
    assert client.get('/api/v1/auth/me').json()['user'] is None
    assert client.get('/api/v1/conversations').status_code == 401


def test_renewal_stops_at_absolute_deadline(client, app, monkeypatch):
    instant = now()
    monkeypatch.setattr('app.main.now', lambda: instant)
    login(client)
    with app.state.session_factory() as db:
        row = db.get(LoginSession, session_key(client))
        row.created_at = instant - timedelta(days=29)
        row.refreshed_at = instant - timedelta(days=1)
        db.commit()
    response = client.post('/api/v1/auth/refresh')
    assert response.status_code == 200 and 'Max-Age=86400' in response.headers['set-cookie']
    with app.state.session_factory() as db:
        assert db.get(LoginSession, session_key(client)).expires_at == instant + timedelta(days=1)


def test_multiple_tabs_share_renewal_and_logout_cannot_be_undone(client, app):
    login(client)
    token = client.cookies.get('yandu_session')
    key = session_key(client)
    with app.state.session_factory() as db:
        db.get(LoginSession, key).refreshed_at = now() - timedelta(days=1)
        db.commit()
    # Use clients without starting independent application lifespans.
    def refresh(_):
        tab = TestClient(app, cookies={'yandu_session': token})
        try:
            return tab.post('/api/v1/auth/refresh').status_code
        finally:
            tab.close()
    with ThreadPoolExecutor(max_workers=4) as executor:
        assert list(executor.map(refresh, range(4))) == [200] * 4
    # A logout racing a renewal must leave the token revoked in either ordering.
    with ThreadPoolExecutor(max_workers=2) as executor:
        pending = executor.submit(refresh, 0)
        assert client.post('/api/v1/auth/logout').status_code == 200
        assert pending.result() in (200, 401)
    with ThreadPoolExecutor(max_workers=4) as executor:
        assert list(executor.map(refresh, range(4))) == [401] * 4
    with app.state.session_factory() as db:
        assert db.get(LoginSession, key) is None


def test_old_session_upgrade_is_idempotent_and_preserves_expiry(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "legacy.db"}')
    instant = now()
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE login_sessions (token_hash VARCHAR(64) PRIMARY KEY, user_id VARCHAR(36), expires_at TIMESTAMP NOT NULL)'))
        for key, expiry in [('active', instant + timedelta(hours=2)), ('expired', instant - timedelta(days=2))]:
            conn.execute(text('INSERT INTO login_sessions VALUES (:key, :user, :expiry)'), {'key': key, 'user': 'u', 'expiry': expiry})
    upgrade_login_sessions(engine)
    upgrade_login_sessions(engine)
    with engine.connect() as conn:
        rows = conn.execute(LoginSession.__table__.select()).mappings().all()
        assert all(r['created_at'] == r['expires_at'] - timedelta(days=1) for r in rows)
        assert next(r for r in rows if r['token_hash'] == 'expired')['expires_at'] < instant
        assert next(r for r in rows if r['token_hash'] == 'active')['expires_at'] == instant + timedelta(hours=2)
    engine.dispose()
