from conftest import login, photo, publish


def test_nine_photos_for_create_edit_and_drafts(client):
    login(client, 'seller')
    images = [photo(client) for _ in range(10)]
    created = publish(client, images=images[:9])
    assert created.status_code == 201, created.text
    item_id = created.json()['id']
    assert created.json()['images'] == images[:9]
    assert publish(client, images=images).status_code == 422
    assert client.patch(f'/api/v1/items/{item_id}', json={'images': images}).status_code == 422
    edited = client.patch(f'/api/v1/items/{item_id}', json={'images': images[1:]})
    assert edited.status_code == 200 and edited.json()['images'] == images[1:]
    draft = client.post('/api/v1/item-drafts/import', json={'text': '静音鼠标50元，万柳面交'}).json()[0]
    path = f"/api/v1/item-drafts/{draft['id']}"
    assert client.patch(path, json={'images': images}).status_code == 422
    assert client.patch(path, json={'images': images[:9]}).status_code == 200
    payload = {key: created.json()[key] for key in
               ('title', 'description', 'category', 'price', 'campus', 'condition_grade', 'tags', 'images')}
    assert client.post(path + '/publish', json={**payload, 'images': images}).status_code == 422
    assert client.post(path + '/publish', json=payload).json()['images'] == images[:9]


def test_public_announcements_mark_only_displayed_ids(client):
    login(client, 'admin')
    ids = [client.post('/api/v1/admin/announcements', json={
        'title': f'测试公告 {i}', 'body': '用于验证公告按实际展示标记已读。'
    }).json()['id'] for i in range(4)]
    client.post('/api/v1/auth/logout')
    assert set(ids).issubset({a['id'] for a in client.get('/api/v1/announcements').json()})
    assert client.post('/api/v1/announcements/mark-read', json={'ids': ids[:3]}).status_code == 401
    login(client)
    unread = client.get('/api/v1/announcements/unread').json()['count']
    assert client.post('/api/v1/announcements/mark-read').status_code == 422
    assert client.post('/api/v1/announcements/mark-read', json={'ids': ids[:3]}).status_code == 200
    assert client.get('/api/v1/announcements/unread').json()['count'] == unread - 3
    # Repeated acknowledgements and unknown IDs must not consume other notices.
    client.post('/api/v1/announcements/mark-read', json={'ids': ids[:3] + ['missing']})
    assert client.get('/api/v1/announcements/unread').json()['count'] == unread - 3
    login(client, 'admin')
    newest = client.post('/api/v1/admin/announcements', json={'title': '刚发布的公告', 'body': '该公告不应被之前的请求标记已读。'}).json()['id']
    login(client)
    client.post('/api/v1/announcements/mark-read', json={'ids': [ids[-1]]})
    assert client.get('/api/v1/announcements/unread').json()['count'] == unread - 3
    client.post('/api/v1/announcements/mark-read', json={'ids': [newest]})
    assert client.get('/api/v1/announcements/unread').json()['count'] == unread - 4
