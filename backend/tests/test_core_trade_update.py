import pytest
from sqlalchemy import create_engine, event, select, update

from app.models import ChatMessage, Conversation, Item, ItemDraft
from conftest import intent, login, photo, publish


def start_conversation(client, profile='buyer', item_id='sample-1'):
    login(client, profile)
    response = client.post(f'/api/v1/items/{item_id}/conversations', json={'body': '希望当面交易'})
    assert response.status_code == 201, response.text
    return response.json()['conversation']['id']


def deal(client, conversation_id, action, expected=200):
    response = client.post(f'/api/v1/conversations/{conversation_id}/deal', json={'action': action})
    assert response.status_code == expected, response.text
    return response.json()


def sold_conversation(client, item_id='sample-1'):
    conversation_id = start_conversation(client, item_id=item_id)
    deal(client, conversation_id, 'request')
    login(client, 'seller')
    deal(client, conversation_id, 'reserve')
    deal(client, conversation_id, 'sold')
    return conversation_id


def test_optional_images_publish_edit_and_draft_publish(client):
    login(client, 'seller')
    result = publish(client, images=[])
    assert result.status_code == 201, result.text
    item_id = result.json()['id']
    assert result.json()['images'] == []
    images = [photo(client) for _ in range(3)]
    result = client.patch(f'/api/v1/items/{item_id}', json={'images': images})
    assert result.status_code == 200 and result.json()['images'] == images
    assert client.patch(f'/api/v1/items/{item_id}', json={'images': None}).status_code == 422
    assert client.get(f'/api/v1/items/{item_id}').json()['images'] == images
    result = client.patch(f'/api/v1/items/{item_id}', json={'images': []})
    assert result.status_code == 200 and result.json()['images'] == []
    assert client.patch(f'/api/v1/items/{item_id}', json={'images': images + [images[0]]}).status_code == 422
    assert publish(client, images=images + [images[0]]).status_code == 422

    imported = client.post('/api/v1/item-drafts/import', json={'text': '出九成新高数教材 20 元，燕园面交'})
    assert imported.status_code == 201, imported.text
    draft_id = imported.json()[0]['id']
    assert client.patch(f'/api/v1/item-drafts/{draft_id}', json={'images': images}).status_code == 200
    assert client.patch(f'/api/v1/item-drafts/{draft_id}', json={'images': []}).status_code == 200
    payload = {key: result.json()[key] for key in
               ('title', 'description', 'category', 'price', 'campus', 'condition_grade', 'tags', 'images')}
    published = client.post(f'/api/v1/item-drafts/{draft_id}/publish', json=payload)
    assert published.status_code == 201, published.text
    assert published.json()['images'] == []
    assert client.get('/api/v1/item-drafts/').json() == []


def test_optional_images_do_not_allow_using_another_users_uploads(client):
    login(client, 'seller')
    item_id = publish(client, images=[]).json()['id']
    draft_id = client.post('/api/v1/item-drafts/import', json={'text': '出九成新高数教材 20 元，燕园面交'}).json()[0]['id']
    login(client, 'buyer')
    other_image = photo(client)
    login(client, 'seller')
    assert client.patch(f'/api/v1/items/{item_id}', json={'images': [other_image]}).status_code == 422
    assert client.patch(f'/api/v1/item-drafts/{draft_id}', json={'images': [other_image]}).status_code == 422
    assert publish(client, images=[other_image]).status_code == 422
    assert client.get(f'/api/v1/items/{item_id}').json()['images'] == []


@pytest.mark.parametrize('hidden_status', ['BANNED', 'WITHDRAWN'])
def test_hidden_items_are_excluded_from_public_lists_favorites_and_details(client, app, hidden_status):
    login(client, 'buyer')
    assert client.post('/api/v1/items/sample-1/favorite').status_code == 200
    with app.state.session_factory() as db:
        db.get(Item, 'sample-1').status = hidden_status
        db.commit()
    for profile in ('buyer', 'seller', 'admin', None):
        if profile:
            login(client, profile)
        else:
            assert client.post('/api/v1/auth/logout').status_code == 200
        for on_sale in ('true', 'false'):
            response = client.get('/api/v1/items/', params={'on_sale': on_sale})
            assert response.status_code == 200
            assert 'sample-1' not in {item['id'] for item in response.json()['items']}
        response = client.get('/api/v1/items/sample-1')
        assert response.status_code == (200 if profile in {'seller', 'admin'} else 404)
    login(client, 'buyer')
    favorites = client.get('/api/v1/items/', params={'favorites': 'true', 'on_sale': 'false'})
    assert favorites.status_code == 200 and favorites.json()['total'] == 0
    assert client.post('/api/v1/items/sample-1/favorite').status_code == 404
    login(client, 'seller')
    mine = client.get('/api/v1/items/', params={'mine': 'true', 'on_sale': 'false'})
    assert any(item['id'] == 'sample-1' and item['status'] == hidden_status for item in mine.json()['items'])


def test_withdraw_is_owner_only_idempotent_and_preserves_conversation(client, app):
    assert client.delete('/api/v1/items/sample-1').status_code == 401
    conversation_id = start_conversation(client)
    assert client.delete('/api/v1/items/sample-1').status_code == 403
    login(client, 'admin')
    assert client.delete('/api/v1/items/sample-1').status_code == 403
    login(client, 'seller')
    for _ in range(2):
        response = client.delete('/api/v1/items/sample-1')
        assert response.status_code == 200, response.text
        assert response.json()['status'] == 'WITHDRAWN'
    assert client.patch('/api/v1/items/sample-1', json={'title': '重新发布'}).status_code == 409
    assert client.patch('/api/v1/items/sample-1/status', json={'status': 'ACTIVE'}).status_code == 409
    with app.state.session_factory() as db:
        assert db.get(Item, 'sample-1').status == 'WITHDRAWN'
        assert db.get(Conversation, conversation_id) is not None
        assert db.scalar(select(ChatMessage).where(ChatMessage.conversation_id == conversation_id)) is not None
    login(client, 'buyer')
    conversations = client.get('/api/v1/conversations').json()
    assert conversations[0]['id'] == conversation_id
    assert conversations[0]['item_status'] == 'WITHDRAWN'
    assert conversations[0]['item_image'] is None
    assert client.get(f'/api/v1/conversations/{conversation_id}/messages').status_code == 200
    assert client.post(f'/api/v1/conversations/{conversation_id}/messages', json={'body': '已了解撤回情况'}).status_code == 201
    assert client.get('/api/v1/items/sample-1').status_code == 404
    assert client.post('/api/v1/items/sample-1/conversations', json={'body': '新的咨询'}).status_code in {404, 409}


@pytest.mark.parametrize('state', ['REQUESTED', 'RESERVED', 'SOLD'])
def test_withdraw_refuses_unresolved_deals_without_modifying_state(client, app, state):
    conversation_id = start_conversation(client)
    deal(client, conversation_id, 'request')
    login(client, 'seller')
    if state in {'RESERVED', 'SOLD'}:
        deal(client, conversation_id, 'reserve')
    if state == 'SOLD':
        deal(client, conversation_id, 'sold')
    before = client.get('/api/v1/items/sample-1').json()['status']
    assert client.delete('/api/v1/items/sample-1').status_code == 409
    with app.state.session_factory() as db:
        assert db.get(Item, 'sample-1').status == before
        assert db.get(Conversation, conversation_id).deal_status == state


@pytest.mark.parametrize('hidden_status', ['BANNED', 'WITHDRAWN'])
def test_hidden_match_notifications_remove_item_details_and_matching_evidence(client, app, hidden_status):
    login(client, 'buyer')
    assert intent(client).status_code == 201
    notices = client.get('/api/v1/notifications/').json()
    original = notices[0]
    item_id = original['item']['id']
    with app.state.session_factory() as db:
        db.get(Item, item_id).status = hidden_status
        db.commit()
    notification = next(row for row in client.get('/api/v1/notifications/').json() if row['id'] == original['id'])
    assert notification['item']['id'] == item_id
    assert notification['item']['status'] == hidden_status
    assert notification['item']['title'] != original['item']['title']
    for field in ('description', 'category', 'campus'):
        assert notification['item'][field] == ''
    assert notification['item']['price'] == 0
    assert notification['item']['images'] == notification['item']['tags'] == []
    assert notification['item']['seller']['id'] == ''
    assert not notification['available']
    assert notification['questions'] == notification['evidence'] == []
    assert notification['reason'] == '商品已停止展示'


@pytest.mark.parametrize('confirmed', [False, True])
def test_sold_transaction_cannot_be_relisted_and_buyer_can_still_confirm(client, app, confirmed):
    conversation_id = sold_conversation(client)
    if confirmed:
        login(client, 'buyer')
        deal(client, conversation_id, 'confirm')
        login(client, 'seller')
    for requested_status in ('ACTIVE', 'RESERVED'):
        assert client.patch('/api/v1/items/sample-1/status', json={'status': requested_status}).status_code == 409
    with app.state.session_factory() as db:
        assert db.get(Item, 'sample-1').status == 'SOLD'
        assert db.get(Conversation, conversation_id).deal_status == ('CONFIRMED' if confirmed else 'SOLD')
    if not confirmed:
        login(client, 'buyer')
        assert deal(client, conversation_id, 'confirm')['deal_status'] == 'CONFIRMED'


def test_mistaken_sale_without_transaction_can_be_relisted(client):
    login(client, 'seller')
    assert client.patch('/api/v1/items/sample-1/status', json={'status': 'SOLD'}).status_code == 200
    result = client.patch('/api/v1/items/sample-1/status', json={'status': 'ACTIVE'})
    assert result.status_code == 200 and result.json()['status'] == 'ACTIVE'


def test_duplicate_completed_sale_creates_private_draft_and_preserves_original(client, app):
    login(client, 'seller')
    original = publish(client).json()
    item_id = original['id']
    conversation_id = sold_conversation(client, item_id)
    path = f'/api/v1/items/{item_id}/duplicate'
    assert client.post(path).status_code == 409
    login(client, 'buyer')
    deal(client, conversation_id, 'confirm')
    assert client.post(path).status_code == 403
    login(client, 'seller')
    original = client.get(f'/api/v1/items/{item_id}').json()
    response = client.post(path)
    assert response.status_code == 201, response.text
    draft = response.json()
    assert draft['id'] != original['id']
    for field in ('title', 'description', 'category', 'price', 'campus', 'condition_grade', 'tags', 'images'):
        assert draft[field] == original[field]
    assert client.get(f"/api/v1/items/{draft['id']}").status_code == 404
    assert any(row['id'] == draft['id'] for row in client.get('/api/v1/item-drafts/').json())
    with app.state.session_factory() as db:
        assert db.get(ItemDraft, draft['id']).seller_id == 'demo-seller'
        assert db.get(Item, item_id).status == 'SOLD'
        assert db.get(Conversation, conversation_id).deal_status == 'CONFIRMED'
    login(client, 'buyer')
    assert client.get('/api/v1/item-drafts/').json() == []
    login(client, 'seller')
    payload = {key: draft[key] for key in
               ('title', 'description', 'category', 'price', 'campus', 'condition_grade', 'tags', 'images')}
    published = client.post(f"/api/v1/item-drafts/{draft['id']}/publish", json=payload)
    assert published.status_code == 201, published.text
    assert published.json()['id'] != item_id
    assert published.json()['status'] == 'ACTIVE'
    assert published.json()['images'] == original['images']
    assert client.get(f'/api/v1/items/{item_id}').json()['status'] == 'SOLD'
    with app.state.session_factory() as db:
        assert db.get(Conversation, conversation_id).item_id == item_id
        assert db.get(Conversation, conversation_id).deal_status == 'CONFIRMED'


def test_duplicate_requires_confirmed_sale(client):
    login(client, 'seller')
    assert client.post('/api/v1/items/sample-1/duplicate').status_code == 409
    assert client.patch('/api/v1/items/sample-1/status', json={'status': 'SOLD'}).status_code == 200
    assert client.post('/api/v1/items/sample-1/duplicate').status_code == 409


@pytest.mark.parametrize('sale_route', ['conversation', 'item_status'])
def test_sale_rejects_other_buyers_and_notifies_both_conversations(client, app, sale_route):
    first_id = start_conversation(client)
    deal(client, first_id, 'request')
    second_id = start_conversation(client, 'admin')
    deal(client, second_id, 'request')
    second_before = client.get(f'/api/v1/conversations/{second_id}/messages').json()['messages']
    login(client, 'seller')
    deal(client, first_id, 'reserve')
    first_before = client.get(f'/api/v1/conversations/{first_id}/messages').json()['messages']
    if sale_route == 'conversation':
        deal(client, first_id, 'sold')
    else:
        assert client.patch('/api/v1/items/sample-1/status', json={'status': 'SOLD'}).status_code == 200
    with app.state.session_factory() as db:
        assert db.get(Conversation, first_id).deal_status == 'SOLD'
        assert db.get(Conversation, second_id).deal_status == 'DECLINED'
    first_after = client.get(f'/api/v1/conversations/{first_id}/messages').json()['messages']
    second_after = client.get(f'/api/v1/conversations/{second_id}/messages').json()['messages']
    assert len(first_after) == len(first_before) + 1
    assert len(second_after) == len(second_before) + 1
    assert first_after[-1]['sender_id'] == second_after[-1]['sender_id'] == 'demo-seller'
    assert first_after[-1]['body'] != second_after[-1]['body']
    # Retrying a completed action must not emit duplicate notices.
    if sale_route == 'conversation':
        deal(client, first_id, 'sold', expected=409)
    else:
        assert client.patch('/api/v1/items/sample-1/status', json={'status': 'SOLD'}).status_code == 200
    assert client.get(f'/api/v1/conversations/{first_id}/messages').json()['messages'] == first_after
    assert client.get(f'/api/v1/conversations/{second_id}/messages').json()['messages'] == second_after
    login(client, 'buyer')
    assert deal(client, first_id, 'confirm')['deal_status'] == 'CONFIRMED'


def test_stale_buyer_actions_cannot_release_another_buyers_reservation(client, app):
    first_id = start_conversation(client)
    deal(client, first_id, 'request')
    second_id = start_conversation(client, 'admin')
    deal(client, second_id, 'request')
    login(client, 'seller')
    deal(client, first_id, 'reserve')
    deal(client, second_id, 'reserve', expected=409)
    login(client, 'admin')
    assert deal(client, second_id, 'cancel')['item_status'] == 'RESERVED'
    login(client, 'buyer')
    deal(client, first_id, 'cancel')
    login(client, 'admin')
    deal(client, second_id, 'request')
    login(client, 'seller')
    deal(client, second_id, 'reserve')
    login(client, 'buyer')
    deal(client, first_id, 'cancel', expected=409)
    with app.state.session_factory() as db:
        assert db.get(Item, 'sample-1').status == 'RESERVED'
        assert db.get(Conversation, second_id).deal_status == 'RESERVED'


def test_cancel_does_not_reactivate_moderator_hidden_reserved_item(client, app):
    conversation_id = start_conversation(client)
    deal(client, conversation_id, 'request')
    login(client, 'seller')
    deal(client, conversation_id, 'reserve')
    with app.state.session_factory() as db:
        db.get(Item, 'sample-1').status = 'BANNED'
        db.commit()
    login(client, 'buyer')
    result = client.post(f'/api/v1/conversations/{conversation_id}/deal', json={'action': 'cancel'})
    assert result.status_code in {200, 409}
    with app.state.session_factory() as db:
        assert db.get(Item, 'sample-1').status == 'BANNED'


def test_cancel_rechecks_deal_after_another_connection_commits_sale(client, app):
    conversation_id = start_conversation(client)
    deal(client, conversation_id, 'request')
    login(client, 'seller')
    deal(client, conversation_id, 'reserve')
    login(client, 'buyer')
    before = client.get(f'/api/v1/conversations/{conversation_id}/messages').json()['messages']
    writer = create_engine(str(app.state.engine.url))
    interleaved = False

    def commit_sale_before_item_lock(execution):
        nonlocal interleaved
        if interleaved or not execution.is_select:
            return
        entities = [column.get('entity') for column in execution.statement.column_descriptions]
        if Item not in entities:
            return
        # The request has read RESERVED. A second worker commits while this request
        # waits to acquire the item's lock; its Session still holds that older deal.
        loaded_deals = [row for row in execution.session.identity_map.values()
                        if isinstance(row, Conversation) and row.id == conversation_id]
        assert len(loaded_deals) == 1 and loaded_deals[0].deal_status == 'RESERVED'
        with writer.begin() as connection:
            connection.execute(update(Item).where(Item.id == 'sample-1').values(status='SOLD'))
            connection.execute(update(Conversation).where(Conversation.id == conversation_id)
                               .values(deal_status='SOLD'))
        interleaved = True

    session_class = app.state.session_factory.class_
    event.listen(session_class, 'do_orm_execute', commit_sale_before_item_lock)
    try:
        response = client.post(f'/api/v1/conversations/{conversation_id}/deal', json={'action': 'cancel'})
    finally:
        event.remove(session_class, 'do_orm_execute', commit_sale_before_item_lock)
        writer.dispose()
    assert interleaved
    assert response.status_code == 409, response.text
    assert client.get(f'/api/v1/conversations/{conversation_id}/messages').json()['messages'] == before
    with app.state.session_factory() as db:
        assert db.get(Item, 'sample-1').status == 'SOLD'
        assert db.get(Conversation, conversation_id).deal_status == 'SOLD'
    assert deal(client, conversation_id, 'confirm')['deal_status'] == 'CONFIRMED'


def test_seller_can_cancel_a_reserved_deal_and_reopen_item(client, app):
    conversation_id = start_conversation(client)
    deal(client, conversation_id, 'request')
    login(client, 'seller')
    deal(client, conversation_id, 'reserve')
    result = deal(client, conversation_id, 'cancel')
    assert result['deal_status'] == 'CANCELED'
    assert result['item_status'] == 'ACTIVE'
    with app.state.session_factory() as db:
        assert db.get(Item, 'sample-1').status == 'ACTIVE'
    # The buyer can request again after the seller cancels the reservation.
    login(client, 'buyer')
    assert deal(client, conversation_id, 'request')['deal_status'] == 'REQUESTED'


def test_seller_cannot_cancel_before_reserving(client):
    conversation_id = start_conversation(client)
    deal(client, conversation_id, 'request')
    login(client, 'seller')
    response = client.post(f'/api/v1/conversations/{conversation_id}/deal', json={'action': 'cancel'})
    assert response.status_code == 403
