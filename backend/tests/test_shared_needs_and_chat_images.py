import io
from datetime import timedelta

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from app.config import Settings
from app.main import create_app
from app.models import Base, ChatMessage, Intent, Item, User, Wanted, now
from app.retention import prune_chat
from conftest import intent, login, photo, publish


def my_wanted(client, wanted_id):
    return next(w for w in client.get('/api/v1/wanted/?mine=true').json() if w['id'] == wanted_id)

def test_wanted_and_intent_share_edits_matches_and_lifecycle(client):
    login(client)
    created = client.post('/api/v1/wanted/', json={
        'title': '求购静音鼠标', 'description': '万柳面交', 'category': '数码与影音', 'budget': 300, 'campus': '万柳学区'
    })
    assert created.status_code == 201, created.text
    wanted = created.json()
    task = wanted['intent']['id']
    assert wanted['intent']['wanted_id'] == wanted['id']
    assert wanted['intent']['match_count'] == 1
    assert client.get('/api/v1/intents/my').json()[0]['id'] == task

    edited = client.patch(f"/api/v1/wanted/{wanted['id']}", json={'budget': 100, 'campus': '燕园校本部'})
    assert edited.status_code == 200
    assert (edited.json()['intent']['max_price'], edited.json()['intent']['campus']) == (100, '燕园校本部')
    assert client.get(f'/api/v1/notifications/?intent_id={task}').json() == []
    parsed = {'keywords': ['鼠标', '静音'], 'category': '数码与影音', 'max_price': 300, 'campus': '万柳学区'}
    edited = client.patch(f'/api/v1/intents/{task}/details', json={'raw_query': '万柳300以内的静音鼠标', 'parsed': parsed})
    assert edited.status_code == 200
    wanted = my_wanted(client, wanted['id'])
    assert (wanted['budget'], wanted['campus'], wanted['description']) == (300, '万柳学区', '万柳300以内的静音鼠标')
    assert wanted['intent']['match_count'] == 1
    assert client.patch(f'/api/v1/intents/{task}', json={'action': 'pause'}).status_code == 200
    assert my_wanted(client, wanted['id'])['status'] == 'PAUSED'
    assert wanted['id'] not in {w['id'] for w in client.get('/api/v1/wanted/').json()}
    assert client.patch(f'/api/v1/intents/{task}', json={'action': 'resume'}).status_code == 200
    assert my_wanted(client, wanted['id'])['status'] == 'ACTIVE'
    assert client.delete(f"/api/v1/wanted/{wanted['id']}").status_code == 200
    assert my_wanted(client, wanted['id'])['intent']['status'] == 'COMPLETED'
    assert client.post(f"/api/v1/wanted/{wanted['id']}/renew").json()['intent']['id'] == task
    assert client.post(f'/api/v1/intents/{task}/complete', json={}).status_code == 200
    assert my_wanted(client, wanted['id'])['status'] == 'COMPLETED'

def test_private_intent_is_only_published_on_request_and_cannot_be_duplicated_or_stolen(client):
    login(client)
    private = intent(client).json()['intent']
    assert private['wanted_id'] is None
    payload = {'title': '求购静音鼠标', 'category': private['category'], 'budget': private['max_price'],
               'campus': private['campus'], 'description': private['raw_query'], 'intent_id': private['id']}
    login(client, 'seller')
    assert client.post('/api/v1/wanted/', json=payload).status_code == 404
    assert client.patch(f"/api/v1/intents/{private['id']}/details", json={'raw_query': '鼠标', 'parsed': {'keywords': ['鼠标']}}).status_code == 404
    login(client)
    published = client.post('/api/v1/wanted/', json=payload)
    assert published.status_code == 201, published.text
    assert published.json()['intent']['id'] == private['id']
    assert published.json()['intent']['match_count'] == private['match_count']
    assert len(client.get('/api/v1/intents/my').json()) == 1
    assert client.post('/api/v1/wanted/', json=payload).status_code == 409
    login(client, 'seller')
    public = next(w for w in client.get('/api/v1/wanted/').json() if w['id'] == published.json()['id'])
    assert public['intent'] is None

def test_unlimited_budget_and_optional_details(client):
    login(client)
    wanted = client.post('/api/v1/wanted/', json={'title': '求购鼠标'})
    assert wanted.status_code == 201, wanted.text
    assert wanted.json()['budget'] is None and wanted.json()['category'] is None
    assert wanted.json()['intent']['max_price'] is None

def test_legacy_database_migration_preserves_rows_and_backfills_needs(tmp_path):
    url = f'sqlite:///{tmp_path / "legacy.db"}'
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(User(id='real-buyer', nickname='校内同学', campus='万柳学区'))
        db.add(Item(id='old-item', seller_id='real-buyer', title='旧商品', description='仍然可以使用',
                    category='数码与影音', price_cents=100, campus='万柳学区', status='EXPIRED'))
        db.add(Intent(id='old-task', buyer_id='real-buyer', raw_query='鼠标', keywords=['鼠标'], status='EXPIRED'))
        db.commit()
    with engine.begin() as conn:
        for table in ('items', 'buyer_intents'):
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN expires_at TIMESTAMP NOT NULL DEFAULT '2000-01-01'"))
        conn.execute(text('DROP INDEX idx_intents_active'))
        conn.execute(text('CREATE INDEX idx_intents_active ON buyer_intents (status, expires_at)'))
        conn.execute(text('DROP TABLE wanted_posts'))
        conn.execute(text('''CREATE TABLE wanted_posts (
            id VARCHAR(36) PRIMARY KEY, buyer_id VARCHAR(36) NOT NULL REFERENCES users(id),
            title VARCHAR(120) NOT NULL, description TEXT NOT NULL, category VARCHAR(30) NOT NULL,
            budget_cents INTEGER NOT NULL, campus VARCHAR(30) NOT NULL, status VARCHAR(20) NOT NULL,
            created_at TIMESTAMP NOT NULL, expires_at TIMESTAMP NOT NULL)'''))
        conn.execute(text("INSERT INTO wanted_posts VALUES ('old-wanted', 'real-buyer', '求购鼠标', '万柳面交', '数码与影音', 30000, '万柳学区', 'EXPIRED', '2000-01-01', '2000-01-08')"))
    engine.dispose()
    settings = Settings(database_url=url, data_dir=tmp_path, demo_mode=False, ai_mode='local')
    for _ in range(2):
        with TestClient(create_app(settings)) as client:
            with client.app.state.session_factory() as db:
                assert db.get(Item, 'old-item').status == 'ACTIVE'
                assert db.get(Intent, 'old-task').status == 'ACTIVE'
                wanted = db.get(Wanted, 'old-wanted')
                assert wanted.title == '求购鼠标' and wanted.status == 'ACTIVE'
                assert wanted.intent_id and db.get(Intent, wanted.intent_id).max_price_cents == 30000
                assert db.query(Intent).count() == 2
            columns = inspect(client.app.state.engine).get_columns('wanted_posts')
            assert not any(c['name'] == 'expires_at' for c in columns)
            assert all(c['nullable'] for c in columns if c['name'] in {'category', 'budget_cents'})
            assert client.get('/api/v1/items/').json()['total'] == 1

def test_long_private_need_can_be_published_and_edited_without_duplicating_text(client):
    login(client)
    raw = '求购鼠标' + '，具体要求可以商量' * 240
    task = client.post('/api/v1/intents/', json={'raw_query': raw, 'parsed': {'keywords': ['鼠标']}}).json()['intent']
    published = client.post('/api/v1/wanted/', json={'title': raw[:120], 'description': raw, 'intent_id': task['id']})
    assert published.status_code == 201, published.text
    assert published.json()['intent']['raw_query'] == raw
    updated = client.patch(f"/api/v1/intents/{task['id']}/details", json={'raw_query': raw, 'parsed': {'keywords': ['鼠标']}})
    assert updated.status_code == 200
    wanted = my_wanted(client, published.json()['id'])
    assert len(wanted['description']) > 2000
    response = client.patch(f"/api/v1/wanted/{wanted['id']}", json={'title': wanted['title'], 'description': wanted['description'], 'budget': 100})
    assert response.status_code == 200, response.text
    assert response.json()['intent']['raw_query'] == raw

def test_publishing_a_paused_private_intent_resumes_the_same_task(client):
    login(client)
    task = intent(client).json()['intent']
    client.patch(f"/api/v1/intents/{task['id']}", json={'action': 'pause'})
    published = client.post('/api/v1/wanted/', json={'title': '求购静音鼠标', 'description': task['raw_query'],
                           'category': task['category'], 'budget': task['max_price'], 'campus': task['campus'], 'intent_id': task['id']})
    assert published.status_code == 201, published.text
    assert published.json()['status'] == published.json()['intent']['status'] == 'ACTIVE'
    assert published.json()['intent']['id'] == task['id']
    assert published.json()['intent']['match_count'] == task['match_count']
