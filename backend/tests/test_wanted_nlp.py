from conftest import login


def test_wanted_parse_requires_login(client):
    assert client.post('/api/v1/wanted/parse', json={'raw': '求一本离散数学教材'}).status_code == 401


def test_wanted_parse_rejects_short_input(client):
    login(client)
    assert client.post('/api/v1/wanted/parse', json={'raw': '书'}).status_code == 422


def test_wanted_parse_fills_structured_fields(client):
    login(client)
    response = client.post('/api/v1/wanted/parse', json={
        'raw': '求一台九成新的 iPad，预算 2000 元，燕园面交'
    })
    assert response.status_code == 200, response.text
    parsed = response.json()['parsed']
    assert parsed['title']
    assert parsed['description'] == '求一台九成新的 iPad，预算 2000 元，燕园面交'
    assert parsed['category'] == '数码与影音'
    assert float(parsed['budget']) == 2000.0
    assert parsed['campus'] == '燕园校本部'
    assert response.json()['mode'] == 'local'


def test_wanted_parse_result_can_publish(client):
    login(client)
    parsed = client.post('/api/v1/wanted/parse', json={'raw': '求购静音鼠标，万柳面交'}).json()['parsed']
    created = client.post('/api/v1/wanted/', json={
        'title': parsed['title'],
        'description': parsed['description'],
        'category': parsed['category'],
        'budget': parsed['budget'],
        'campus': parsed['campus'],
    })
    assert created.status_code == 201, created.text
    assert created.json()['title'] == parsed['title']
    assert created.json()['intent']['id']
