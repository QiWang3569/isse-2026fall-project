from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.models import Intent, Wanted, now
from app.wanted_watch import WantedWatch
from conftest import intent, login


def wanted(client, **changes):
    payload = dict(title='求购静音鼠标', description='需要静音鼠标，用于自习室学习',
                   category='数码与影音', budget=300, campus='万柳学区')
    payload.update(changes)
    return client.post('/api/v1/wanted/', json=payload)


def test_wanted_watch_opt_in_copies_conditions_and_matches(client, app):
    login(client)
    response = wanted(client, enable_watch=True, watch_validity_days=30, validity_days=0)
    assert response.status_code == 201, response.text
    post = response.json()
    task = next(t for t in client.get('/api/v1/intents/my').json() if t['id'] == post['linked_intent_id'])
    assert task['validity_days'] == 30
    assert (task['category'], task['max_price'], task['campus']) == ('数码与影音', 300, '万柳学区')
    assert '鼠标' in task['keywords'] and '静音' in task['keywords']
    assert post['expires_at'] is None
    assert 'sample-1' in {n['item']['id'] for n in client.get('/api/v1/notifications/').json()}
    with app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(WantedWatch)) == 1


def test_existing_wanted_can_link_once_without_restarting_task(client, app):
    login(client)
    post = wanted(client).json()
    assert post['linked_intent_id'] is None
    first = client.post(f"/api/v1/wanted/{post['id']}/watch", json={'validity_days': 7})
    assert first.status_code == 200, first.text
    task_id = first.json()['linked_intent_id']
    client.patch(f'/api/v1/intents/{task_id}', json={'action': 'pause'})
    again = client.post(f"/api/v1/wanted/{post['id']}/watch", json={'validity_days': 30})
    assert again.json()['linked_intent_id'] == task_id
    assert again.json()['linked_intent_status'] == 'PAUSED'
    with app.state.session_factory() as db:
        assert db.get(Intent, task_id).validity_days == 7
        assert db.scalar(select(func.count()).select_from(WantedWatch)) == 1


def test_link_is_private_and_other_user_cannot_create_or_stop_it(client, app):
    login(client)
    post = wanted(client, enable_watch=True).json()
    login(client, 'seller')
    public = next(p for p in client.get('/api/v1/wanted/').json() if p['id'] == post['id'])
    assert public['linked_intent_id'] is None and public['linked_intent_status'] is None
    assert client.post(f"/api/v1/wanted/{post['id']}/watch", json={}).status_code == 404
    assert client.delete(f"/api/v1/wanted/{post['id']}?stop_watch=true").status_code == 404
    with app.state.session_factory() as db:
        assert db.get(Intent, post['linked_intent_id']).status == 'ACTIVE'


def test_watch_quota_failure_does_not_publish_half_a_wanted(client, app):
    login(client)
    for _ in range(5):
        assert intent(client).status_code == 201
    with app.state.session_factory() as db:
        before = db.scalar(select(func.count()).select_from(Wanted))
    assert wanted(client, enable_watch=True).status_code == 409
    with app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Wanted)) == before
        assert db.scalar(select(func.count()).select_from(WantedWatch)) == 0
    post = wanted(client).json()
    assert client.post(f"/api/v1/wanted/{post['id']}/watch", json={}).status_code == 409
    assert client.get('/api/v1/wanted/', params={'mine': True}).status_code == 200


@pytest.mark.parametrize('stop_watch', [False, True])
def test_close_wanted_can_keep_or_end_linked_watch(client, app, stop_watch):
    login(client)
    post = wanted(client, enable_watch=True).json()
    url = f"/api/v1/wanted/{post['id']}?stop_watch={str(stop_watch).lower()}"
    assert client.delete(url).status_code == 200
    assert client.delete(url).status_code == 200
    with app.state.session_factory() as db:
        assert db.get(Wanted, post['id']).status == 'COMPLETED'
        assert db.get(Intent, post['linked_intent_id']).status == ('COMPLETED' if stop_watch else 'ACTIVE')


@pytest.mark.parametrize('state', ['EXPIRED', 'COMPLETED'])
def test_inactive_wanted_cannot_create_watch(client, app, state):
    login(client)
    post = wanted(client).json()
    with app.state.session_factory() as db:
        row = db.get(Wanted, post['id'])
        row.status = state
        if state == 'EXPIRED':
            row.expires_at = now() - timedelta(seconds=1)
        db.commit()
    assert client.post(f"/api/v1/wanted/{post['id']}/watch", json={}).status_code == 409


def test_edit_wanted_keeps_watch_conditions_independent(client, app):
    login(client)
    post = wanted(client, enable_watch=True).json()
    assert client.patch(f"/api/v1/wanted/{post['id']}", json={'budget': 100}).status_code == 200
    with app.state.session_factory() as db:
        assert db.get(Wanted, post['id']).budget_cents == 10000
        assert db.get(Intent, post['linked_intent_id']).max_price_cents == 30000


def test_watch_duration_and_switch_validation(client):
    login(client)
    assert wanted(client, enable_watch=True, watch_validity_days=0).status_code == 422
    assert wanted(client, enable_watch=True, watch_validity_days=True).status_code == 422
    post = wanted(client).json()
    assert client.post(f"/api/v1/wanted/{post['id']}/watch", json={'validity_days': 365}).status_code == 422


@pytest.mark.parametrize('description,keywords', [
    ('希望柔软一些，最好静音', ['瑜伽垫']),
    ('要求静音，适合宿舍使用', ['瑜伽垫', '静音']),
])
def test_uncommon_product_name_is_preserved_without_turning_preferences_into_requirements(client, app, description, keywords):
    login(client)
    post = wanted(client, title='求购瑜伽垫', description=description,
                  category='校园出行与运动', enable_watch=True).json()
    with app.state.session_factory() as db:
        task = db.get(Intent, post['linked_intent_id'])
        assert task.keywords == keywords
