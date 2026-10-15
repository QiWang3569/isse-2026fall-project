import hashlib
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, inspect, text

from app.config import Settings
from app.main import create_app
from app.models import Base, Conversation, Intent, Item, LoginSession, User, Wanted, now
from conftest import login


def test_email_preference_is_private_partial_and_requires_registered_account(client, app):
    login(client)
    assert client.patch('/api/v1/users/me', json={'email_notifications': True}).status_code == 422
    with app.state.session_factory() as db:
        db.add(User(id='registered-pref-user', nickname='原昵称', campus='万柳学区',
                    email='local-qa@stu.pku.edu.cn', bio='保留这段简介', avatar_color='blue'))
        db.flush()
        db.add(LoginSession(token_hash=hashlib.sha256(b'local-test-session').hexdigest(),
                            user_id='registered-pref-user', expires_at=now() + timedelta(hours=1)))
        db.commit()
    client.cookies.set('yandu_session', 'local-test-session')
    result = client.patch('/api/v1/users/me', json={'email_notifications': True})
    assert result.status_code == 200, result.text
    user = result.json()['user']
    assert user['email_notifications'] is True
    assert (user['nickname'], user['campus'], user['bio'], user['avatar_color']) == (
        '原昵称', '万柳学区', '保留这段简介', 'blue')
    assert client.patch('/api/v1/users/me', json={'email_notifications': None}).status_code == 422
    assert client.patch('/api/v1/users/me', json={'email_notifications': 'true'}).status_code == 422
    assert client.patch('/api/v1/users/me', json={'email_notifications': False}).json()['user']['email_notifications'] is False
    assert client.get('/api/v1/meta').json()['chat_email_ready'] is False
    public = client.get('/api/v1/items/').json()['items'][0]['seller']
    assert 'email_notifications' not in public and 'email' not in public


def test_new_database_email_preference_server_default_is_true(client, app):
    with app.state.engine.begin() as connection:
        connection.execute(text("INSERT INTO users (id, nickname, campus, role, contact, bio, avatar_color) "
                                "VALUES ('server-default-user', '默认用户', '万柳学区', 'student', '', '', 'sage')"))
    with app.state.session_factory() as db:
        assert db.get(User, 'server-default-user').email_notifications is True


def test_default_enabled_but_user_opt_out_survives_restart(tmp_path):
    settings = Settings(database_url=f'sqlite:///{tmp_path / "preference.db"}', data_dir=tmp_path,
                        demo_mode=False, ai_mode='local')
    app = create_app(settings)
    with TestClient(app) as client:
        with app.state.session_factory.begin() as db:
            db.add(User(id='default-on', nickname='默认开启用户', campus='万柳学区', email='new@pku.edu.cn'))
            db.flush()
            assert db.get(User, 'default-on').email_notifications is True
            db.add(LoginSession(token_hash=hashlib.sha256(b'preference-session').hexdigest(),
                                user_id='default-on', expires_at=now() + timedelta(hours=1)))
        client.cookies.set('yandu_session', 'preference-session')
        assert client.patch('/api/v1/users/me', json={'email_notifications': False}).status_code == 200
    for _ in range(2):
        restarted = create_app(settings)
        with TestClient(restarted):
            with restarted.state.session_factory() as db:
                assert db.get(User, 'default-on').email_notifications is False


def test_email_link_can_load_older_authorized_conversation_outside_recent_list(client, app):
    assert client.get('/api/v1/conversations/missing').status_code == 401
    login(client)
    result = client.post('/api/v1/items/sample-1/conversations', json={'body': '需要保留的旧会话'})
    target = result.json()['conversation']['id']
    with app.state.session_factory() as db:
        db.get(Conversation, target).last_message_at = now() - timedelta(days=1)
        db.add_all([Item(id=f'new-chat-item-{index}', seller_id='demo-seller', title='新的商品会话',
                         category='数码与影音', campus='万柳学区', price_cents=1000) for index in range(100)])
        db.flush()
        db.add_all([Conversation(item_id=f'new-chat-item-{index}', buyer_id='demo-buyer',
                                 seller_id='demo-seller') for index in range(100)])
        db.commit()
    recent = client.get('/api/v1/conversations').json()
    assert len(recent) == 100 and target not in {row['id'] for row in recent}
    detail = client.get(f'/api/v1/conversations/{target}')
    assert detail.status_code == 200
    assert detail.json()['last_message']['body'] == '需要保留的旧会话'
    login(client, 'admin')
    assert client.get(f'/api/v1/conversations/{target}').status_code == 404
    login(client, 'seller')
    assert client.get(f'/api/v1/conversations/{target}').status_code == 200


@pytest.mark.parametrize('url', ['http://example.com', 'https://site.test/path',
                                     'https://site.test:notaport', 'https://site.test:99999', 'https://site.test:0',
                                     'https://name:secret@site.test', 'https://site.test/#messages/x',
                                     'https://site.test/?redirect=x'])
def test_email_site_origin_validation(url):
    with pytest.raises(ValueError):
        Settings(public_app_url=url)


def test_email_enabled_requires_delivery_configuration():
    with pytest.raises(ValueError):
        Settings(chat_email_enabled=True)
    configured = Settings(chat_email_enabled=True, public_app_url='http://127.0.0.1:18081',
                          smtp_host='smtp.test.invalid', smtp_from='noreply@test.invalid')
    assert configured.chat_email_ready


def test_followup_tables_and_email_preference_upgrade_idempotently(tmp_path):
    url = f'sqlite:///{tmp_path / "before-followup.db"}'
    settings = Settings(database_url=url, data_dir=tmp_path, demo_mode=True, ai_mode='local')
    with TestClient(create_app(settings)) as client:
        login(client)
        conversation = client.post('/api/v1/items/sample-1/conversations', json={'body': '旧聊天保留'}).json()
        conversation_id = conversation['conversation']['id']
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text('DROP TABLE chat_email_receipts'))
        connection.execute(text('DROP TABLE chat_email_queue'))
        connection.execute(text('ALTER TABLE users DROP COLUMN email_notifications'))
    engine.dispose()
    for _ in range(2):
        app = create_app(settings)
        with TestClient(app) as client:
            assert login(client)['email_notifications'] is False
            rows = client.get(f'/api/v1/conversations/{conversation_id}/messages').json()['messages']
            assert rows[0]['body'] == '旧聊天保留'
            assert {'chat_email_receipts', 'chat_email_queue'} <= set(inspect(app.state.engine).get_table_names())


def test_local_link_migrates_to_shared_need_without_duplicate_or_lost_history(tmp_path):
    from sqlalchemy.orm import Session
    url = f'sqlite:///{tmp_path / "local-linked.db"}'
    engine = create_engine(url)
    @event.listens_for(engine, 'connect')
    def foreign_keys(connection, _):
        connection.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(User(id='local-owner', nickname='本地用户', campus='万柳学区'))
        db.flush()
        db.add(Intent(id='existing-watch', buyer_id='local-owner', raw_query='鼠标', keywords=['鼠标'], status='PAUSED'))
        db.add(Item(id='withdrawn-item', seller_id='local-owner', title='已撤回商品', description='保持撤回',
                    category='数码与影音', price_cents=100, campus='万柳学区', status='WITHDRAWN'))
        db.commit()
    with engine.begin() as conn:
        conn.execute(text('DROP TABLE wanted_posts'))
        conn.execute(text('''CREATE TABLE wanted_posts (
            id VARCHAR(36) PRIMARY KEY, buyer_id VARCHAR(36) NOT NULL REFERENCES users(id),
            title VARCHAR(120) NOT NULL, description TEXT NOT NULL, category VARCHAR(30) NOT NULL,
            budget_cents INTEGER NOT NULL, campus VARCHAR(30) NOT NULL, status VARCHAR(20) NOT NULL,
            created_at TIMESTAMP NOT NULL, expires_at TIMESTAMP NOT NULL, validity_days INTEGER NOT NULL DEFAULT 7)'''))
        conn.execute(text("INSERT INTO wanted_posts VALUES ('linked-post', 'local-owner', '求购鼠标', '万柳面交', '数码与影音', 30000, '万柳学区', 'ACTIVE', '2000-01-01', '2000-01-08', 7)"))
        conn.execute(text('''CREATE TABLE wanted_watches (
            wanted_id VARCHAR(36) PRIMARY KEY REFERENCES wanted_posts(id),
            intent_id VARCHAR(36) NOT NULL UNIQUE REFERENCES buyer_intents(id))'''))
        conn.execute(text("INSERT INTO wanted_watches VALUES ('linked-post', 'existing-watch')"))
    engine.dispose()
    settings = Settings(database_url=url, data_dir=tmp_path, demo_mode=False, ai_mode='local')
    for _ in range(2):
        app = create_app(settings)
        event.listen(app.state.engine, 'connect', foreign_keys)
        with TestClient(app):
            with app.state.session_factory() as db:
                wanted = db.get(Wanted, 'linked-post')
                assert wanted.intent_id == 'existing-watch' and wanted.status == 'PAUSED'
                assert db.query(Intent).count() == 1
                assert db.get(Intent, 'existing-watch').keywords == ['鼠标']
                assert db.get(Item, 'withdrawn-item').status == 'WITHDRAWN'
            assert 'wanted_watches' not in inspect(app.state.engine).get_table_names()
