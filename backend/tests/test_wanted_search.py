from datetime import timedelta

from conftest import login
from app.models import Wanted, now


def add_wanted(app, **changes):
    values = dict(buyer_id='demo-buyer', title='求购二手教材',
                  description='想找一本课程需要的教材', category='教材与书籍',
                  budget_cents=5000, campus='燕园校本部')
    values.update(changes)
    with app.state.session_factory() as db:
        post = Wanted(**values)
        db.add(post)
        db.commit()
        return post.id


def search_ids(client, query):
    response = client.get('/api/v1/wanted/', params={'q': query})
    assert response.status_code == 200, response.text
    return {post['id'] for post in response.json()}


def test_search_title_description_case_and_literal_wildcards(client, app):
    title = add_wanted(app, title='求购 ThinkPad 电脑')
    description = add_wanted(app, description='想找一台 THINKPAD 用来写代码')
    literal = add_wanted(app, title='求购 100%_正版教材')
    add_wanted(app, title='求购 100 分教材')

    assert search_ids(client, '  thinkpad  ') == {title, description}
    assert search_ids(client, '%_') == {literal}
    assert search_ids(client, '不存在的物品') == set()
    assert search_ids(client, '') == search_ids(client, '   ')
    assert client.get('/api/v1/wanted/', params={'q': 'a' * 101}).status_code == 422


def test_search_filters_before_result_limit_and_hides_inactive(client, app):
    oldest = add_wanted(app, title='求购限量版画册', created_at=now() - timedelta(days=1))
    with app.state.session_factory() as db:
        for _ in range(101):
            db.add(Wanted(buyer_id='demo-buyer', title='其他同学求购鼠标',
                          description='普通无线鼠标即可', category='数码与影音',
                          budget_cents=5000, campus='燕园校本部'))
        db.commit()
    add_wanted(app, title='求购限量版画册', status='CLOSED')
    add_wanted(app, title='求购限量版画册', expires_at=now() - timedelta(seconds=1))

    assert oldest not in search_ids(client, '')
    assert search_ids(client, '限量版画册') == {oldest}


def test_search_preserves_my_wanted_access_rules(client, app):
    own = add_wanted(app, title='求购旧版词典', status='CLOSED')
    add_wanted(app, title='求购旧版词典', buyer_id='demo-seller')
    assert client.get('/api/v1/wanted/', params={'mine': 'true', 'q': '词典'}).status_code == 401
    login(client)
    response = client.get('/api/v1/wanted/', params={'mine': 'true', 'q': '词典'})
    assert response.status_code == 200
    assert {post['id'] for post in response.json()} == {own}
