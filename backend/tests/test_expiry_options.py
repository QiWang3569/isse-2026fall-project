from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.database import prepare_database
from app.models import Conversation, Intent, Item, ItemDraft, Wanted, now
from app.schemas import ExpiryUpdate, IntentChange, IntentCreate, ItemCreate, ItemDraftUpdate, WantedCreate
from app.services import seed
from conftest import intent, login


ITEM = {'title': '安静的无线鼠标', 'description': '静音无线鼠标，功能正常，万柳当面交易。',
        'category': '数码与影音', 'price': 100, 'campus': '万柳学区', 'tags': ['静音', '鼠标']}
WANTED = {'title': '求购无线鼠标', 'description': '需要静音无线鼠标，万柳当面交易。',
          'category': '数码与影音', 'budget': 200, 'campus': '万柳学区'}


def assert_deadline(data, days):
    assert data['validity_days'] == days
    if days == 0:
        assert data['expires_at'] is None
    else:
        deadline = datetime.fromisoformat(data['expires_at'].removesuffix('Z'))
        assert abs((deadline - now()).total_seconds() - days * 86400) < 10


def set_past(app, model, row_id):
    with app.state.session_factory() as db:
        db.get(model, row_id).expires_at = now() - timedelta(days=1)
        db.commit()


def my_wanted(client, row_id):
    return next(w for w in client.get('/api/v1/wanted/', params={'mine': True}).json() if w['id'] == row_id)


def deal(client, conversation_id, action):
    result = client.post(f'/api/v1/conversations/{conversation_id}/deal', json={'action': action})
    assert result.status_code == 200, result.text
    return result.json()


@pytest.mark.parametrize('days', [0, 7, 14, 30])
def test_listing_presets_and_public_expiry(client, app, days):
    login(client, 'seller')
    response = client.post('/api/v1/items/', json={**ITEM, 'validity_days': days})
    assert response.status_code == 201, response.text
    item = response.json()
    assert_deadline(item, days)
    wanted_response = client.post('/api/v1/wanted/', json={**WANTED, 'validity_days': days})
    assert wanted_response.status_code == 201, wanted_response.text
    wanted_id = wanted_response.json()['id']
    assert_deadline(my_wanted(client, wanted_id), days)
    set_past(app, Item, item['id'])
    set_past(app, Wanted, wanted_id)
    visible_items = {i['id'] for i in client.get('/api/v1/items/').json()['items']}
    visible_wanted = {w['id'] for w in client.get('/api/v1/wanted/').json()}
    assert (item['id'] in visible_items) == (days == 0)
    assert (wanted_id in visible_wanted) == (days == 0)
    assert client.get(f"/api/v1/items/{item['id']}").json()['status'] == ('ACTIVE' if days == 0 else 'EXPIRED')


def test_permanent_item_can_match_search_and_start_chat(client, app):
    login(client, 'seller')
    item_id = client.post('/api/v1/items/', json={**ITEM, 'validity_days': 0}).json()['id']
    set_past(app, Item, item_id)
    login(client)
    match = intent(client)
    assert item_id in {item['id'] for item in match.json()['matches']}
    notice = next(n for n in client.get('/api/v1/notifications/').json() if n['item']['id'] == item_id)
    assert notice['available'] and notice['item']['expires_at'] is None
    result = client.post('/api/v1/items/smart-search', json={'query': '万柳静音鼠标 300 元以内'})
    assert item_id in {item['id'] for item in result.json()['items']}
    assert client.post(f'/api/v1/items/{item_id}/conversations', json={'body': '想购买这件商品'}).status_code == 201


def test_item_edit_renew_and_relist_preserve_selected_lifetime(client, app):
    login(client, 'seller')
    item = client.post('/api/v1/items/', json={**ITEM, 'validity_days': 30}).json()
    item_id = item['id']
    edited = client.patch(f'/api/v1/items/{item_id}', json={'title': '无线静音鼠标出售'}).json()
    assert edited['expires_at'] == item['expires_at'] and edited['validity_days'] == 30
    set_past(app, Item, item_id)
    renewed = client.post(f'/api/v1/items/{item_id}/renew')
    assert renewed.status_code == 200, renewed.text
    assert_deadline(renewed.json(), 30)
    assert renewed.json()['status'] == 'ACTIVE'
    set_past(app, Item, item_id)
    changed = client.patch(f'/api/v1/items/{item_id}', json={'validity_days': 7})
    assert changed.status_code == 200 and changed.json()['status'] == 'ACTIVE'
    assert_deadline(changed.json(), 7)
    assert client.patch(f'/api/v1/items/{item_id}/status', json={'status': 'SOLD'}).status_code == 200
    relisted = client.patch(f'/api/v1/items/{item_id}/status', json={'status': 'ACTIVE'})
    assert_deadline(relisted.json(), 7)
    login(client, 'buyer')
    assert client.post(f'/api/v1/items/{item_id}/renew', json={'validity_days': 0}).status_code == 403


@pytest.mark.parametrize('days,action', [(7, 'cancel'), (0, 'cancel'), (7, 'sold')])
def test_elapsed_deadline_keeps_reserved_trade_until_explicit_action(client, app, days, action):
    login(client, 'seller')
    item_id = client.post('/api/v1/items/', json={**ITEM, 'validity_days': days}).json()['id']
    login(client)
    conversation_id = client.post(f'/api/v1/items/{item_id}/conversations', json={'body': '请为我预留'}).json()['conversation']['id']
    deal(client, conversation_id, 'request')
    login(client, 'seller')
    deal(client, conversation_id, 'reserve')
    set_past(app, Item, item_id)
    assert client.get(f'/api/v1/items/{item_id}').json()['status'] == 'RESERVED'
    assert client.post(f'/api/v1/items/{item_id}/renew').status_code == 409
    with app.state.session_factory() as db:
        assert db.get(Conversation, conversation_id).deal_status == 'RESERVED'
    if action == 'sold':
        deal(client, conversation_id, 'sold')
        login(client)
        assert deal(client, conversation_id, 'confirm')['deal_status'] == 'CONFIRMED'
        login(client, 'seller')
        assert client.post(f'/api/v1/items/{item_id}/renew').status_code == 409
        copied = client.post(f'/api/v1/items/{item_id}/duplicate').json()
        assert copied['validity_days'] == days
    else:
        login(client)
        deal(client, conversation_id, 'cancel')
        expected = 'ACTIVE' if days == 0 else 'EXPIRED'
        assert client.get(f'/api/v1/items/{item_id}').json()['status'] == expected


def test_draft_lifetime_survives_save_and_starts_at_publication(client, app):
    login(client, 'seller')
    draft_id = client.post('/api/v1/item-drafts/import', json={'text': '出九成新静音鼠标，50 元，万柳面交'}).json()[0]['id']
    saved = client.patch(f'/api/v1/item-drafts/{draft_id}', json={'validity_days': 30}).json()
    assert saved['validity_days'] == 30
    with app.state.session_factory() as db:
        db.get(ItemDraft, draft_id).created_at = now() - timedelta(days=35)
        db.commit()
    published = client.post(f'/api/v1/item-drafts/{draft_id}/publish', json=ITEM)
    assert published.status_code == 201, published.text
    assert_deadline(published.json(), 30)
    assert published.json()['status'] == 'ACTIVE'


def test_wanted_edits_and_renewals_keep_lifetime_and_do_not_reopen_closed_posts(client, app):
    login(client)
    wanted_id = client.post('/api/v1/wanted/', json={**WANTED, 'validity_days': 30}).json()['id']
    original = my_wanted(client, wanted_id)
    assert client.patch(f'/api/v1/wanted/{wanted_id}', json={'budget': 150}).status_code == 200
    assert my_wanted(client, wanted_id)['expires_at'] == original['expires_at']
    set_past(app, Wanted, wanted_id)
    assert client.post(f'/api/v1/wanted/{wanted_id}/renew').status_code == 200
    assert_deadline(my_wanted(client, wanted_id), 30)
    set_past(app, Wanted, wanted_id)
    assert client.patch(f'/api/v1/wanted/{wanted_id}', json={'validity_days': 0}).status_code == 200
    assert my_wanted(client, wanted_id)['status'] == 'ACTIVE'
    assert_deadline(my_wanted(client, wanted_id), 0)
    assert client.delete(f'/api/v1/wanted/{wanted_id}').status_code == 200
    assert client.patch(f'/api/v1/wanted/{wanted_id}', json={'validity_days': 7}).status_code == 200
    assert my_wanted(client, wanted_id)['status'] == 'COMPLETED'
    login(client, 'seller')
    assert client.post(f'/api/v1/wanted/{wanted_id}/renew').status_code == 404


def test_intent_presets_saved_renewal_and_expired_resume(client, app):
    login(client)
    response = client.post('/api/v1/intents/', json={'raw_query': '静音鼠标', 'parsed': {'keywords': ['鼠标']}, 'validity_days': 30})
    assert response.status_code == 201, response.text
    task = response.json()['intent']
    assert_deadline(task, 30)
    set_past(app, Intent, task['id'])
    assert client.patch(f"/api/v1/intents/{task['id']}", json={'action': 'resume'}).status_code == 409
    renewed = client.patch(f"/api/v1/intents/{task['id']}", json={'action': 'renew'}).json()
    assert_deadline(renewed, 30)
    changed = client.patch(f"/api/v1/intents/{task['id']}", json={'action': 'renew', 'validity_days': 7}).json()
    assert_deadline(changed, 7)
    assert client.patch(f"/api/v1/intents/{task['id']}", json={'action': 'pause', 'validity_days': 14}).status_code == 422


@pytest.mark.parametrize('invalid', [None, False, True, '7', 7.0, -1, 1, 365])
def test_duration_inputs_are_strict_and_reject_null(invalid):
    for schema, payload in ((ItemCreate, ITEM), (WantedCreate, WANTED),
                            (ItemDraftUpdate, {}), (ExpiryUpdate, {}),
                            (IntentCreate, {'raw_query': '鼠标', 'parsed': {'keywords': ['鼠标']}}),
                            (IntentChange, {'action': 'renew'})):
        with pytest.raises(ValidationError):
            schema.model_validate({**payload, 'validity_days': invalid})
    with pytest.raises(ValidationError):
        IntentChange.model_validate({'action': 'renew', 'validity_days': 0})


def test_legacy_expiry_migration_is_additive_and_idempotent(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "legacy-expiry.db"}')
    prepare_database(engine)
    deadline = now() + timedelta(days=3)
    with Session(engine) as db:
        seed(db)
        db.get(Item, 'sample-1').expires_at = deadline
        db.add(Intent(id='legacy-intent', buyer_id='demo-buyer', raw_query='鼠标', keywords=['鼠标'], expires_at=deadline))
        db.add(Wanted(id='legacy-wanted', buyer_id='demo-buyer', title='求购鼠标', description='静音鼠标',
                      category='数码与影音', budget_cents=5000, campus='万柳学区', expires_at=deadline))
        db.add(ItemDraft(id='legacy-draft', seller_id='demo-seller', raw='一只闲置鼠标'))
        db.commit()
    with engine.begin() as connection:
        for table in ('items', 'item_drafts', 'buyer_intents', 'wanted_posts'):
            connection.execute(text(f'ALTER TABLE {table} DROP COLUMN validity_days'))
    for _ in range(2):
        prepare_database(engine)
        with Session(engine) as db:
            for model, row_id, days in ((Item, 'sample-1', 14), (Intent, 'legacy-intent', 14), (Wanted, 'legacy-wanted', 7)):
                record = db.get(model, row_id)
                assert record.validity_days == days
                assert record.expires_at == deadline
            assert db.get(ItemDraft, 'legacy-draft').validity_days == 14
    engine.dispose()
