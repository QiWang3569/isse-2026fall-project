from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import Settings
from app.main import create_app
from app.models import ActionLog, Intent, Item, Notification, now
from app.services import parse_local
from conftest import intent, login, photo, publish


def test_guest_can_browse_but_cannot_publish_or_see_personal_data(client):
    response = client.get('/api/v1/items/')
    assert response.status_code == 200
    assert response.json()['total'] == 10
    assert 'contact' not in response.json()['items'][0]['seller']
    assert client.get('/api/v1/intents/my').status_code == 401
    assert client.post('/api/v1/items/sample-1/favorite').status_code == 401
    assert client.get('/api/v1/admin/reports').status_code == 401


@pytest.mark.parametrize('query,category,price,campus,condition', [
    ('蹲一个万柳附近 300 内静音鼠标', '数码与影音', 300, '万柳学区', None),
    ('帮我找一本不超过50元、燕园可以自取的高数教材，九成新', '课程资料与书籍', 50, '燕园校本部', '9成新'),
    ('医学部预算0元的台灯', '宿舍生活与家电', 0, '医学部', None),
    ('求一个显示器', '数码与影音', None, '不限校区', None),
])
def test_parser_extracts_budget_campus_condition_without_inventing_constraints(query, category, price, campus, condition):
    parsed = parse_local(query)
    assert (parsed.category, parsed.max_price, parsed.campus, parsed.condition_grade) == (category, price, campus, condition)


def test_intent_first_search_and_new_item_match_with_dedup(client):
    login(client)
    result = intent(client)
    assert result.status_code == 201, result.text
    task = result.json()['intent']['id']
    assert [i['id'] for i in result.json()['matches']] == ['sample-1']
    login(client, 'seller')
    product = publish(client).json()
    assert 'id' in product
    login(client)
    notices = client.get('/api/v1/notifications/').json()
    assert {n['item']['id'] for n in notices} == {'sample-1', product['id']}
    assert client.patch(f'/api/v1/intents/{task}', json={'action': 'renew'}).status_code == 200
    assert len(client.get('/api/v1/notifications/').json()) == 2
    client.patch(f"/api/v1/notifications/{notices[0]['id']}/read")
    assert client.get('/api/v1/notifications/').json()[0]['is_read']


def test_hard_filters_budget_campus_condition_and_self_exclusion(client):
    login(client)
    intent(client, '万柳 300 以内 九成新 静音鼠标')
    own = publish(client, title='自己的静音鼠标').json()
    login(client, 'seller')
    costly = publish(client, price=301).json()
    wrong_campus = publish(client, campus='医学部').json()
    worn = publish(client, condition_grade='8成新').json()
    unrelated = publish(client, title='机械键盘', description='机械键盘，适合办公室。', tags=['键盘']).json()
    valid = publish(client, price=300, condition_grade='9成新').json()
    login(client)
    ids = {n['item']['id'] for n in client.get('/api/v1/notifications/').json()}
    assert valid['id'] in ids
    assert not ids.intersection({own['id'], costly['id'], wrong_campus['id'], worn['id'], unrelated['id']})


def test_old_items_stay_available_but_reserved_and_sold_do_not_match(client, app):
    login(client)
    with app.state.session_factory() as db:
        db.get(Item, 'sample-1').created_at = now() - timedelta(days=365)
        db.commit()
    assert intent(client).json()['matches'][0]['id'] == 'sample-1'
    login(client, 'seller')
    client.patch('/api/v1/items/sample-1/status', json={'status': 'RESERVED'})
    login(client)
    assert intent(client).json()['matches'] == []
    assert not client.get('/api/v1/notifications/').json()[0]['available']
    login(client, 'seller')
    client.patch('/api/v1/items/sample-1/status', json={'status': 'SOLD'})
    assert client.patch('/api/v1/items/sample-1/status', json={'status': 'ACTIVE'}).status_code == 200
    login(client)
    assert client.get('/api/v1/notifications/').json()[0]['available']


def test_more_than_five_tasks_can_run_and_pause_resume_end_still_work(client):
    login(client)
    tasks = [intent(client).json()['intent']['id'] for _ in range(6)]
    assert len(client.get('/api/v1/intents/my').json()) == 6
    assert client.patch(f'/api/v1/intents/{tasks[0]}', json={'action': 'pause'}).status_code == 200
    assert client.patch(f'/api/v1/intents/{tasks[0]}', json={'action': 'resume'}).status_code == 200
    client.delete(f'/api/v1/intents/{tasks[1]}')
    assert client.patch(f'/api/v1/intents/{tasks[1]}', json={'action': 'resume'}).status_code == 409


def test_paused_intents_stop_matching_while_old_active_intents_keep_matching(client, app):
    login(client)
    paused = intent(client).json()['intent']['id']
    old = intent(client).json()['intent']['id']
    client.patch(f'/api/v1/intents/{paused}', json={'action': 'pause'})
    with app.state.session_factory() as db:
        db.get(Intent, old).created_at = now() - timedelta(days=365)
        db.commit()
    login(client, 'seller')
    product = publish(client).json()
    login(client)
    assert product['id'] not in {n['item']['id'] for n in client.get(f'/api/v1/notifications/?intent_id={paused}').json()}
    assert product['id'] in {n['item']['id'] for n in client.get(f'/api/v1/notifications/?intent_id={old}').json()}
    assert client.patch(f'/api/v1/intents/{paused}', json={'action': 'resume'}).status_code == 200
    assert product['id'] in {n['item']['id'] for n in client.get(f'/api/v1/notifications/?intent_id={paused}').json()}


def test_accounts_cannot_modify_each_others_items_tasks_notifications(client):
    login(client)
    task = intent(client).json()['intent']['id']
    notice = client.get('/api/v1/notifications/').json()[0]['id']
    assert client.patch('/api/v1/items/sample-1/status', json={'status': 'SOLD'}).status_code == 403
    assert client.get('/api/v1/admin/reports').status_code == 403
    login(client, 'seller')
    assert client.delete(f'/api/v1/intents/{task}').status_code == 404
    assert client.patch(f'/api/v1/notifications/{notice}/read').status_code == 404
    assert client.get('/api/v1/notifications/').json() == []


def test_favorites_search_and_drafts_do_not_send_messages(client, app):
    login(client)
    client.post('/api/v1/items/sample-2/favorite')
    assert client.get('/api/v1/items/?favorites=true').json()['total'] == 1
    assert client.get('/api/v1/items/?q=高数&max_price=40').json()['items'][0]['id'] == 'sample-2'
    draft = client.post('/api/v1/items/sample-2/message-draft').json()
    assert draft['sent'] is False
    assert '高等数学' in draft['draft']
    with app.state.session_factory() as db:
        assert [l.action for l in db.scalars(select(ActionLog))] == ['message.draft']
    client.delete('/api/v1/items/sample-2/favorite')
    assert client.get('/api/v1/items/?favorites=true').json()['total'] == 0


def test_report_requires_admin_confirmation_and_writes_audit_log(client, app):
    login(client)
    report = client.post('/api/v1/items/sample-1/reports', json={'reason': '怀疑图片与实际商品不一致，请协助核实。'})
    assert report.status_code == 201
    rid = report.json()['id']
    assert client.get('/api/v1/items/sample-1').json()['status'] == 'ACTIVE'
    action = {'action': 'hide', 'note': '经人工核实暂时隐藏商品', 'confirmed': True}
    assert client.post(f'/api/v1/admin/reports/{rid}/review', json=action).status_code == 403
    login(client, 'admin')
    assert client.post(f'/api/v1/admin/reports/{rid}/review', json={**action, 'confirmed': False}).status_code == 422
    assert client.post(f'/api/v1/admin/reports/{rid}/review', json=action).status_code == 200
    assert client.get('/api/v1/items/sample-1').json()['status'] == 'BANNED'
    assert client.post(f'/api/v1/admin/reports/{rid}/review', json={**action, 'action': 'restore'}).status_code == 200
    assert client.get('/api/v1/items/sample-1').json()['status'] == 'ACTIVE'
    actions = [l['action'] for l in client.get('/api/v1/admin/logs').json()]
    assert 'admin.hide' in actions and 'admin.restore' in actions


def test_upload_checks_content_and_ownership_and_price_validation(client):
    login(client)
    bad = client.post('/api/v1/uploads', files={'file': ('x.jpg', b'<script>alert(1)</script>', 'image/jpeg')})
    assert bad.status_code == 422
    large = client.post('/api/v1/uploads', files={'file': ('x.jpg', b'x'*(6*1024*1024+1), 'image/jpeg')})
    assert large.status_code == 413
    url = photo(client)
    login(client, 'seller')
    assert publish(client, images=[url]).status_code == 422
    assert publish(client, price=-1).status_code == 422
    assert publish(client, price=2.999).status_code == 422
    assert publish(client, seller_id='demo-buyer').status_code == 422
    assert publish(client, images=[]).status_code == 201


def test_wanted_ownership_expiry_and_csrf(client, app):
    login(client)
    result = client.post('/api/v1/wanted/', json={'title': '求一盏台灯', 'description': '希望在燕园当面交易。', 'category': '宿舍生活与家电', 'budget': 80, 'campus': '燕园校本部'})
    assert result.status_code == 201
    wid = result.json()['id']
    login(client, 'seller')
    assert client.delete('/api/v1/wanted/' + wid).status_code == 404
    assert client.post('/api/v1/auth/logout', headers={'Origin': 'https://evil.example'}).status_code == 403
    login(client)
    assert client.delete('/api/v1/wanted/' + wid).status_code == 200
    assert wid not in {w['id'] for w in client.get('/api/v1/wanted/').json()}


def test_database_persists_on_restart(tmp_path):
    settings = Settings(database_url=f'sqlite:///{tmp_path / "persist.db"}', data_dir=tmp_path, demo_mode=True, ai_mode='local')
    with TestClient(create_app(settings)) as c:
        login(c)
        task_id = intent(c).json()['intent']['id']
    with TestClient(create_app(settings)) as c:
        login(c)
        assert c.get('/api/v1/items/').json()['total'] == 10
        assert c.get('/api/v1/intents/my').json()[0]['id'] == task_id
        assert len(c.get('/api/v1/notifications/').json()) == 1


def test_production_mode_has_no_demo_login_or_seed(tmp_path):
    settings = Settings(database_url=f'sqlite:///{tmp_path / "prod.db"}', data_dir=tmp_path, demo_mode=False, ai_mode='local')
    with TestClient(create_app(settings)) as c:
        assert c.post('/api/v1/auth/demo', json={'profile': 'admin'}).status_code == 503
        assert c.get('/api/v1/items/').json()['total'] == 0


def test_disabling_demo_mode_revokes_old_sessions_and_hides_seeded_data(tmp_path):
    from fastapi.testclient import TestClient
    from app.main import create_app
    database_url = f'sqlite:///{tmp_path / "switch.db"}'
    demo = Settings(database_url=database_url, data_dir=tmp_path, demo_mode=True, ai_mode='local')
    with TestClient(create_app(demo)) as client:
        login(client, 'admin')
        old_cookie = client.cookies.get('yandu_session')
        assert client.get('/api/v1/items/').json()['total'] > 0
    public = Settings(database_url=database_url, data_dir=tmp_path, demo_mode=False, ai_mode='local')
    with TestClient(create_app(public)) as client:
        client.cookies.set('yandu_session', old_cookie)
        assert client.get('/api/v1/auth/me').json()['user'] is None
        assert client.post('/api/v1/auth/demo', json={'profile': 'admin'}).status_code == 503
        assert client.get('/api/v1/items/').json()['total'] == 0
        assert client.get('/api/v1/items/sample-1').status_code == 404
        assert client.get('/api/v1/wanted/').json() == []
        with client.app.state.session_factory() as db:
            from app.models import LoginSession
            assert db.query(LoginSession).count() == 0


def test_production_settings_reject_unsafe_defaults(tmp_path):
    with pytest.raises(ValueError, match='PostgreSQL'):
        Settings(app_env='production', database_url=f'sqlite:///{tmp_path / "unsafe.db"}',
                 demo_mode=False, ai_mode='local')
    safe = dict(app_env='production', database_url='postgresql+psycopg://yandu:placeholder@postgres/yandu',
                demo_mode=False, session_cookie_secure=True, ai_mode='local',
                auth_secret='x' * 32, smtp_host='smtp.example.org', smtp_user='sender@example.org',
                smtp_password='placeholder', smtp_from='sender@example.org',
                origins=['https://market.example.org'])
    assert Settings(**safe).app_env == 'production'
    with pytest.raises(ValueError, match='HTTPS origin'):
        Settings(**{**safe, 'origins': ['http://market.example.org']})
    with pytest.raises(ValueError, match='DEMO_MODE=false'):
        Settings(**{**safe, 'demo_mode': True})


def test_secure_cookie_can_be_forced_behind_reverse_proxy(tmp_path):
    from fastapi.testclient import TestClient
    from app.main import create_app
    settings = Settings(database_url=f'sqlite:///{tmp_path / "cookie.db"}', data_dir=tmp_path,
                        demo_mode=True, session_cookie_secure=True, ai_mode='local')
    with TestClient(create_app(settings)) as client:
        response = client.post('/api/v1/auth/demo', json={'profile': 'buyer'})
        assert response.status_code == 200
        assert 'secure' in response.headers['set-cookie'].lower()


def test_remote_mode_requires_explicit_credentials():
    with pytest.raises(ValueError):
        Settings(ai_mode='remote', deepseek_key='', embedding_key='')
