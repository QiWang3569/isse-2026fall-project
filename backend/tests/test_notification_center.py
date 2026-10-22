from datetime import timedelta

from sqlalchemy import create_engine, select, text

from app.migrations import upgrade_buyer_agent
from app.models import (Announcement, AnnouncementRead, Base, ChatMessage, Feedback,
                        FeedbackNotice, Intent, Notification, SaleFeedback, now)
from conftest import login


def test_announcement_feed_paginates_and_keeps_reads_private(client, app):
    with app.state.session_factory() as db:
        db.add_all(Announcement(id=f'notice-{i:02}', title=f'公告 {i}', body='详细正文',
                               created_at=now() + timedelta(seconds=i)) for i in range(57))
        db.add(Announcement(id='inactive', title='下线公告', body='不可见', active=False))
        db.commit()
    guest = client.get('/api/v1/announcements/feed').json()
    assert len(guest['items']) == 20 and guest['total'] >= 57
    assert all(a['is_read'] is None for a in guest['items'])
    assert client.get('/api/v1/announcements/feed?unread_only=true').status_code == 401
    login(client)
    total = client.get('/api/v1/notification-summary').json()['announcements']
    seen = set()
    for page in range(1, (total + 19) // 20 + 1):
        batch = client.get(f'/api/v1/announcements/feed?page={page}').json()['items']
        assert not seen.intersection(a['id'] for a in batch)
        seen.update(a['id'] for a in batch)
    assert len(seen) == total and 'inactive' not in seen
    # The unread feed shrinks after each acknowledgement, making every old entry reachable.
    while batch := client.get('/api/v1/announcements/feed?unread_only=true').json()['items']:
        ids = [a['id'] for a in batch]
        assert client.post('/api/v1/announcements/mark-read', json={'ids': ids}).status_code == 200
    assert client.get('/api/v1/notification-summary').json()['announcements'] == 0
    assert client.get('/api/v1/announcements/feed').json()['total'] == total
    login(client, 'seller')
    assert client.get('/api/v1/notification-summary').json()['announcements'] == total
    assert all(not a['is_read'] for a in client.get('/api/v1/announcements/feed').json()['items'])


def test_summary_counts_all_matches_and_chat_messages_not_list_lengths(client, app):
    login(client)
    chat = client.post('/api/v1/items/sample-1/conversations', json={'body': '咨询'}).json()
    conversation_id = chat['conversation']['id']
    with app.state.session_factory() as db:
        for i in range(125):
            task = Intent(id=f'task-{i}', buyer_id='demo-buyer', raw_query='鼠标', keywords=['鼠标'],
                          category='数码与影音', campus='不限校区', embedding_model='local-keyword')
            db.add(task)
            db.flush()
            db.add(Notification(buyer_id='demo-buyer', intent_id=task.id, item_id='sample-1', score=1, reason='匹配'))
            db.add(ChatMessage(conversation_id=conversation_id, sender_id='demo-seller', body=f'回复 {i}'))
        feedback = Feedback(user_id='demo-buyer', category='使用建议', body='建议完善通知')
        db.add(feedback)
        db.flush()
        db.add(FeedbackNotice(user_id='demo-buyer', feedback_id=feedback.id, body='已回复'))
        db.commit()
    summary = client.get('/api/v1/notification-summary').json()
    assert summary['matches'] == 125 and summary['chat'] == 125 and summary['feedback'] == 1
    assert summary['total'] == 251 + summary['announcements']
    notices = client.get('/api/v1/notifications/?unread_only=true').json()
    assert len(notices) == 100
    client.patch(f"/api/v1/notifications/{notices[0]['id']}/read")
    next_batch = client.get('/api/v1/notifications/?unread_only=true').json()
    assert len(next_batch) == 100 and all(n['id'] != notices[0]['id'] for n in next_batch)
    assert client.get('/api/v1/notification-summary').json()['matches'] == 124
    login(client, 'admin')
    assert client.get('/api/v1/notification-summary').json()['chat'] == 0


def test_chat_read_acknowledges_only_fetched_messages(client):
    login(client)
    first = client.post('/api/v1/items/sample-1/conversations', json={'body': '第一条'}).json()
    cid = first['conversation']['id']
    second = client.post(f'/api/v1/conversations/{cid}/messages', json={'body': '稍后到达'}).json()
    login(client, 'seller')
    assert client.post(f'/api/v1/conversations/{cid}/read').status_code == 422
    assert client.post(f'/api/v1/conversations/{cid}/read', json={'ids': [first['message']['id'], 'missing']}).status_code == 200
    assert client.get('/api/v1/notification-summary').json()['chat'] == 1
    assert client.post(f'/api/v1/conversations/{cid}/read', json={'ids': [first['message']['id']]}).status_code == 200
    assert client.get('/api/v1/notification-summary').json()['chat'] == 1
    login(client, 'admin')
    assert client.post(f'/api/v1/conversations/{cid}/read', json={'ids': [second['id']]}).status_code == 404


def test_sale_feedback_read_is_not_resolution(client, app):
    login(client)
    response = client.post('/api/v1/items/sample-1/sale-feedback')
    assert response.status_code == 201
    fid = response.json()['id']
    assert client.post(f'/api/v1/sale-feedback/{fid}/read').status_code == 404
    login(client, 'seller')
    summary = client.get('/api/v1/notification-summary').json()
    assert summary['sale_feedback'] == summary['pending_sale_feedback'] == 1
    assert client.post(f'/api/v1/sale-feedback/{fid}/read').status_code == 200
    assert client.post(f'/api/v1/sale-feedback/{fid}/read').status_code == 200
    summary = client.get('/api/v1/notification-summary').json()
    assert summary['sale_feedback'] == 0 and summary['pending_sale_feedback'] == 1
    assert client.get('/api/v1/sale-feedback/my').json()[0]['is_read'] is True
    with app.state.session_factory() as db:
        assert db.get(SaleFeedback, fid).status == 'OPEN'
    client.post(f'/api/v1/items/sample-1/sale-feedback/{fid}/review', json={'action': 'decline'})
    assert client.get('/api/v1/notification-summary').json()['pending_sale_feedback'] == 0


def test_legacy_sale_feedback_migration_preserves_rows_and_read_state(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "legacy.db"}')
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text('ALTER TABLE sale_feedback DROP COLUMN read_at'))
        conn.execute(text("INSERT INTO sale_feedback (id, reporter_id, item_id, status, created_at) VALUES ('old', 'u', 'i', 'OPEN', CURRENT_TIMESTAMP)"))
    upgrade_buyer_agent(engine)
    with engine.begin() as conn:
        assert conn.execute(text("SELECT read_at FROM sale_feedback WHERE id='old'")).scalar() is None
        conn.execute(text("UPDATE sale_feedback SET read_at='2026-10-23 00:00:00' WHERE id='old'"))
    upgrade_buyer_agent(engine)
    with engine.connect() as conn:
        row = conn.execute(text("SELECT status, read_at FROM sale_feedback WHERE id='old'")).one()
        assert row.status == 'OPEN' and row.read_at == '2026-10-23 00:00:00'
    engine.dispose()
