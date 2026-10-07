from conftest import login, photo


def test_imported_items_remain_private_until_owner_reviews_and_publishes(client):
    login(client, 'seller')
    response = client.post('/api/v1/item-drafts/import', json={
        'text': '出罗技静音鼠标 50 元，万柳面交\n\n出九成新高数教材 20 元，燕园面交'
    })
    assert response.status_code == 201, response.text
    drafts = response.json()
    assert len(drafts) == 2
    assert drafts[0]['price'] == 50
    assert drafts[0]['images'] == []
    assert len(client.get('/api/v1/item-drafts/').json()) == 2
    assert client.get('/api/v1/items/', params={'q': '罗技静音鼠标'}).json()['total'] == 0

    draft_id = drafts[0]['id']
    login(client, 'buyer')
    assert client.get('/api/v1/item-drafts/').json() == []
    assert client.patch(f'/api/v1/item-drafts/{draft_id}', json={'title': '别人的商品'}).status_code == 404
    buyer_image = photo(client)

    login(client, 'seller')
    assert client.patch(f'/api/v1/item-drafts/{draft_id}', json={'images': [buyer_image]}).status_code == 422
    assert client.post(f'/api/v1/item-drafts/{draft_id}/publish', json={
        'title': '罗技静音鼠标', 'description': '九成新静音鼠标，万柳面交。',
        'category': '数码与影音', 'price': 50, 'campus': '万柳学区',
        'condition_grade': '9成新', 'tags': [], 'images': [],
    }).status_code == 422
    assert len(client.get('/api/v1/item-drafts/').json()) == 2

    image = photo(client)
    saved = client.patch(f'/api/v1/item-drafts/{draft_id}', json={
        'title': '罗技静音鼠标', 'description': '九成新静音鼠标，万柳面交。',
        'category': '数码与影音', 'price': 50, 'campus': '万柳学区',
        'condition_grade': '9成新', 'tags': ['静音'], 'images': [image],
    })
    assert saved.status_code == 200, saved.text
    assert saved.json()['images'] == [image]
    published = client.post(f'/api/v1/item-drafts/{draft_id}/publish', json={
        key: saved.json()[key] for key in
        ('title', 'description', 'category', 'price', 'campus', 'condition_grade', 'tags', 'images')
    })
    assert published.status_code == 201, published.text
    assert published.json()['status'] == 'ACTIVE'
    assert len(client.get('/api/v1/item-drafts/').json()) == 1
    assert client.get('/api/v1/items/', params={'q': '罗技静音鼠标'}).json()['total'] == 1
    assert client.post(f'/api/v1/item-drafts/{draft_id}/publish', json={
        key: saved.json()[key] for key in
        ('title', 'description', 'category', 'price', 'campus', 'condition_grade', 'tags', 'images')
    }).status_code == 404

    remaining = drafts[1]['id']
    assert client.delete(f'/api/v1/item-drafts/{remaining}').status_code == 204
    assert client.get('/api/v1/item-drafts/').json() == []


def test_import_checks_line_limit_and_preserves_existing_drafts_on_error(client):
    login(client, 'seller')
    too_many = '\n'.join(f'商品描述第 {n} 件' for n in range(11))
    assert client.post('/api/v1/item-drafts/import', json={'text': too_many}).status_code == 422
    short_line = client.post('/api/v1/item-drafts/import', json={
        'text': '一件九成新的书\n坏'
    })
    assert short_line.status_code == 422
    assert '第 2 件' in short_line.json()['detail']
    assert client.get('/api/v1/item-drafts/').json() == []
