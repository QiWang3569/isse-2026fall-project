import json
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.models import Item, ItemDraft
from conftest import login, photo
from test_vision import ANSWER, provider


def candidate(**changes):
    return {'raw': '照片中的高等数学教材，待核对。', 'title': '高等数学教材', 'description': '封面可见高等数学书名。',
            'category': '课程资料与书籍', 'price': None, 'campus': '燕园校本部', 'condition_grade': '95新',
            'tags': ['教材'], 'images': [], **changes}


def import_payload(*items):
    return {'request_id': str(uuid4()), 'items': list(items) or [candidate()]}


def publish_payload(drafts):
    return {'request_id': str(uuid4()), 'drafts': [{'id': draft['id'], 'updated_at': draft['updated_at']} for draft in drafts]}


def count_items(app):
    with app.state.session_factory() as db:
        return db.scalar(select(func.count()).select_from(Item))


def test_reviewed_import_private_idempotent_and_no_automatic_cover(client, app):
    login(client, 'seller')
    before = count_items(app)
    payload = import_payload(candidate(), candidate(title='线性代数教材'))
    first = client.post('/api/v1/item-drafts/import-vision', json=payload)
    assert first.status_code == 201, first.text
    assert len(first.json()) == 2
    assert all(row['images'] == [] and row['price'] is None for row in first.json())
    replay = client.post('/api/v1/item-drafts/import-vision', json=payload)
    assert {row['id'] for row in replay.json()} == {row['id'] for row in first.json()}
    assert len(client.get('/api/v1/item-drafts/').json()) == 2
    assert count_items(app) == before
    payload['items'][0]['title'] = '不同内容'
    assert client.post('/api/v1/item-drafts/import-vision', json=payload).status_code == 409
    login(client, 'buyer')
    assert client.get('/api/v1/item-drafts/').json() == []


def test_import_auth_origin_and_foreign_photos(client):
    payload = import_payload()
    assert client.post('/api/v1/item-drafts/import-vision', json=payload).status_code == 401
    login(client)
    foreign = photo(client)
    login(client, 'seller')
    assert client.post('/api/v1/item-drafts/import-vision', json=payload,
                       headers={'origin': 'https://untrusted.example'}).status_code == 403
    assert client.post('/api/v1/item-drafts/import-vision', json=import_payload(candidate(images=[foreign]))).status_code == 422
    assert client.get('/api/v1/item-drafts/').json() == []


@pytest.mark.parametrize('items', [[], [candidate()] * 11, [candidate(price=-1)], [candidate(category='不存在')],
                                [candidate(campus='不存在')], [candidate(condition_grade='不存在')],
                                [candidate(tags=['x' * 31])], [candidate(images=None)], [candidate(raw=None)]])
def test_import_validates_all_fields(client, items):
    login(client)
    assert client.post('/api/v1/item-drafts/import-vision', json={'request_id': str(uuid4()), 'items': items}).status_code == 422
    assert client.get('/api/v1/item-drafts/').json() == []


def test_import_capacity_atomic(client):
    login(client)
    for _ in range(5):
        assert client.post('/api/v1/item-drafts/import-vision', json=import_payload(*[candidate()] * 10)).status_code == 201
    assert client.post('/api/v1/item-drafts/import-vision', json=import_payload()).status_code == 409
    assert len(client.get('/api/v1/item-drafts/').json()) == 50


def test_batch_publish_atomic_and_retries_never_duplicate(client, app):
    login(client, 'seller')
    before = count_items(app)
    imported = import_payload(candidate(price=15), candidate(title='线性代数教材', price=25, campus='万柳学区'))
    rows = client.post('/api/v1/item-drafts/import-vision', json=imported).json()
    payload = publish_payload(rows)
    result = client.post('/api/v1/item-drafts/publish-batch', json=payload)
    assert result.status_code == 201, result.text
    assert len(result.json()) == 2
    assert {item['price'] for item in result.json()} == {15, 25}
    assert client.get('/api/v1/item-drafts/').json() == []
    repeated = client.post('/api/v1/item-drafts/publish-batch', json=payload)
    assert repeated.status_code == 201
    assert {item['id'] for item in repeated.json()} == {item['id'] for item in result.json()}
    assert count_items(app) == before + 2
    # Even retrying an old import after its drafts were published cannot recreate them.
    assert client.post('/api/v1/item-drafts/import-vision', json=imported).json() == []
    assert client.get('/api/v1/item-drafts/').json() == []


def test_missing_price_prevents_entire_batch(client, app):
    login(client)
    before = count_items(app)
    rows = client.post('/api/v1/item-drafts/import-vision', json=import_payload(candidate(price=10), candidate())).json()
    result = client.post('/api/v1/item-drafts/publish-batch', json=publish_payload(rows))
    assert result.status_code == 422
    assert '第 2 件' in result.json()['detail']
    assert count_items(app) == before and len(client.get('/api/v1/item-drafts/').json()) == 2


def test_publish_auth_duplicates_and_owner(client, app):
    assert client.post('/api/v1/item-drafts/publish-batch', json=publish_payload([{'id': 'x', 'updated_at': '2026-10-23T12:00:00Z'}])).status_code == 401
    login(client, 'seller')
    before = count_items(app)
    rows = client.post('/api/v1/item-drafts/import-vision', json=import_payload(candidate(price=10))).json()
    assert client.post('/api/v1/item-drafts/publish-batch', json=publish_payload(rows * 2)).status_code == 422
    assert client.post('/api/v1/item-drafts/publish-batch', json=publish_payload(rows),
                       headers={'origin': 'https://untrusted.example'}).status_code == 403
    login(client, 'buyer')
    assert client.post('/api/v1/item-drafts/publish-batch', json=publish_payload(rows)).status_code == 409
    assert count_items(app) == before


def test_stale_draft_rejected_before_publication(client, app):
    login(client)
    before = count_items(app)
    rows = client.post('/api/v1/item-drafts/import-vision', json=import_payload(candidate(price=10))).json()
    client.patch(f"/api/v1/item-drafts/{rows[0]['id']}", json={'price': 20})
    assert client.post('/api/v1/item-drafts/publish-batch', json=publish_payload(rows)).status_code == 409
    assert count_items(app) == before


def test_edit_during_embedding_rechecked_and_preserved(client, app, monkeypatch):
    login(client)
    before = count_items(app)
    rows = client.post('/api/v1/item-drafts/import-vision', json=import_payload(candidate(price=10))).json()
    from app.models import now

    def change_draft(*args):
        with app.state.session_factory() as db:
            row = db.get(ItemDraft, rows[0]['id'])
            row.price_cents = 9900
            row.updated_at = now()
            db.commit()
        return [0.0] * 24
    monkeypatch.setattr('app.draft_batches.embed', change_draft)
    assert client.post('/api/v1/item-drafts/publish-batch', json=publish_payload(rows)).status_code == 409
    assert client.get('/api/v1/item-drafts/').json()[0]['price'] == 99
    assert count_items(app) == before


def test_enqueue_failure_rolls_back_all_items(client, app, monkeypatch):
    login(client)
    before = count_items(app)
    rows = client.post('/api/v1/item-drafts/import-vision', json=import_payload(candidate(price=10), candidate(price=20))).json()
    calls = []

    def fail_second(*args):
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError('simulated queue failure')
        return []
    monkeypatch.setattr(app.state.matching, 'enqueue_item', fail_second)
    with pytest.raises(RuntimeError, match='simulated queue failure'):
        client.post('/api/v1/item-drafts/publish-batch', json=publish_payload(rows))
    assert count_items(app) == before
    assert len(client.get('/api/v1/item-drafts/').json()) == 2


def batch_answer(**changes):
    item = {key: value for key, value in ANSWER.items() if key != 'status'}
    return {'status': 'ready', 'items': [{**item, 'photo_indices': [1]}], 'uncertainties': [], **changes}


def reply(provider, answer):
    provider[1].append((200, {'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(answer)}}]}))


def test_batch_vision_separate_cache_shared_limits_and_no_writes(client, app, provider):
    login(client)
    before = count_items(app)
    payload = {'images': [photo(client)]}
    assert client.post('/api/v1/items/vision-draft', json=payload).status_code == 200
    reply(provider, batch_answer())
    result = client.post('/api/v1/items/vision-batch', json=payload)
    assert result.status_code == 200, result.text
    assert result.json()['items'][0]['photo_indices'] == [1]
    assert client.post('/api/v1/items/vision-batch', json=payload).json() == result.json()
    assert len(provider[0]) == 2
    assert count_items(app) == before and client.get('/api/v1/item-drafts/').json() == []
    app.state.settings.vision_hourly_limit = 2
    assert client.post('/api/v1/items/vision-batch', json={**payload, 'note': 'new'}).status_code == 429
    login(client, 'seller')
    assert client.post('/api/v1/items/vision-batch', json=payload).status_code == 404


@pytest.mark.parametrize('change', [{'photo_indices': [2]}, {'photo_indices': [0]}, {'price': 10}, {'category': '未知'}])
def test_batch_model_invalid_fields_rejected(client, provider, change):
    login(client)
    answer = batch_answer()
    answer['items'][0].update(change)
    reply(provider, answer)
    assert client.post('/api/v1/items/vision-batch', json={'images': [photo(client)]}).status_code == 502


def test_batch_model_excess_or_empty_results(client, provider):
    login(client)
    payload = {'images': [photo(client)]}
    answer = batch_answer()
    answer['items'] *= 11
    reply(provider, answer)
    assert client.post('/api/v1/items/vision-batch', json=payload).status_code == 502
    reply(provider, batch_answer(items=[]))
    result = client.post('/api/v1/items/vision-batch', json=payload)
    assert result.status_code == 200 and result.json()['status'] == 'unclear'
    assert result.json()['items'] == []


def test_batch_vision_disabled(client):
    login(client)
    assert client.post('/api/v1/items/vision-batch', json={'images': [photo(client)]}).status_code == 503
