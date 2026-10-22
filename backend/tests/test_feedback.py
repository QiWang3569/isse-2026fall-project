import io
from datetime import timedelta

import pytest
from PIL import Image
from sqlalchemy import select

from app.models import ActionLog, ChatMessage, Feedback, FeedbackAttachment, FeedbackReply, Upload, now
from app.chat_email import ChatEmailQueue
from app.database import prepare_database
from conftest import login, photo


def screenshot(client):
    stream = io.BytesIO()
    Image.new('RGB', (80, 60), '#354e3c').save(stream, 'PNG')
    return client.post('/api/v1/feedback-uploads', files={'file': ('feedback.png', stream.getvalue(), 'image/png')})


def submit(client, **changes):
    return client.post('/api/v1/feedback', json={
        'category': '功能异常', 'body': '点击收藏后没有反应，请帮忙查看', 'page_path': '/#market', **changes})


def review(client, feedback_id, status='IN_PROGRESS', body='已经收到，我们会跟进处理。'):
    return client.post(f'/api/v1/admin/feedback/{feedback_id}/reply', json={'status': status, 'body': body})


def test_feedback_roundtrip_notifications_audit_and_no_chat_email(client):
    login(client)
    result = submit(client)
    assert result.status_code == 201, result.text
    row = result.json()
    assert row['status'] == 'OPEN' and row['replies'] == []
    assert client.get('/api/v1/feedback').json()['total'] == 1
    assert client.get('/api/v1/feedback-notices').json()['count'] == 0
    login(client, 'admin')
    assert client.get('/api/v1/admin/feedback?status=OPEN').json()['total'] == 1
    assert review(client, row['id']).status_code == 200
    login(client)
    notices = client.get('/api/v1/feedback-notices').json()
    assert notices['count'] == 1 and notices['items'][0]['feedback_id'] == row['id']
    detail = client.get(f"/api/v1/feedback/{row['id']}").json()
    assert detail['replies'][0]['is_staff'] is True
    assert client.get('/api/v1/feedback-notices').json()['count'] == 1  # GET never marks as read.
    login(client, 'admin')
    assert review(client, row['id'], 'RESOLVED', '已修复，请刷新后再试。').status_code == 200
    login(client)
    assert client.post(f"/api/v1/feedback/{row['id']}/read", json={'notice_ids': detail['notice_ids']}).status_code == 200
    assert client.get('/api/v1/feedback-notices').json()['count'] == 1  # Newer reply was not yet seen.
    reply = client.post(f"/api/v1/feedback/{row['id']}/replies", json={'body': '刷新后仍然存在，请再看看。'})
    assert reply.status_code == 201 and reply.json()['status'] == 'OPEN'
    assert len(reply.json()['replies']) == 3
    login(client, 'admin')
    assert client.get('/api/v1/admin/feedback?status=OPEN').json()['total'] == 1
    assert review(client, row['id'], 'DECLINED', '').status_code == 422
    assert review(client, row['id'], 'DECLINED', '此功能目前不在计划内，已记录建议。').status_code == 200
    with client.app.state.session_factory() as db:
        assert len(db.scalars(select(ActionLog).where(ActionLog.target_id == row['id'])).all()) == 5
        assert db.query(ChatMessage).count() == 0  # Feedback never enters the chat email queue.
        assert db.query(ChatEmailQueue).count() == 0


def test_feedback_and_screenshots_are_private(client):
    assert client.get('/api/v1/feedback').status_code == 401
    assert submit(client).status_code == 401
    assert screenshot(client).status_code == 401
    login(client)
    image = screenshot(client).json()['url']
    assert client.get(image).status_code == 200
    login(client, 'admin')
    assert client.get(image).status_code == 404  # No access to another user's unsubmitted image.
    login(client)
    row = submit(client, images=[image]).json()
    assert row['images'] == [image]
    assert submit(client, images=[image]).status_code == 422
    login(client, 'seller')
    assert client.get('/api/v1/feedback').json()['items'] == []
    assert client.get(f"/api/v1/feedback/{row['id']}").status_code == 404
    assert client.post(f"/api/v1/feedback/{row['id']}/replies", json={'body': '其他用户的回复'}).status_code == 404
    assert client.post(f"/api/v1/feedback/{row['id']}/read", json={'notice_ids': []}).status_code == 404
    assert client.get(image).status_code == 404
    assert client.get('/uploads/' + image.rsplit('/', 1)[1]).status_code == 404
    assert client.get('/api/v1/admin/feedback').status_code == 403
    assert client.get(f"/api/v1/admin/feedback/{row['id']}").status_code == 403
    assert review(client, row['id']).status_code == 403
    assert submit(client, images=[image]).status_code == 422
    login(client, 'admin')
    assert client.get(f"/api/v1/admin/feedback/{row['id']}").status_code == 200
    response = client.get(image)
    assert response.status_code == 200 and 'no-store' in response.headers['cache-control']
    assert response.headers['content-type'] == 'image/jpeg'
    client.cookies.clear()
    assert client.get(image).status_code == 401


@pytest.mark.parametrize('changes', [
    {'body': '   '}, {'body': 'x' * 3001}, {'category': 'fake'},
    {'page_path': 'https://example.com'}, {'page_path': '//example.com'},
    {'page_path': '/?token=secret'}, {'page_path': '/\\example.com'},
    {'images': ['a'] * 4}, {'images': ['a', 'a']}, {'status': 'RESOLVED'},
])
def test_feedback_rejects_invalid_data(client, changes):
    login(client)
    assert submit(client, **changes).status_code == 422


def test_feedback_rejects_public_images_and_invalid_uploads(client):
    login(client)
    assert submit(client, images=[photo(client)]).status_code == 422
    assert client.post('/api/v1/feedback-uploads', files={'file': ('fake.jpg', b'not a photo', 'image/jpeg')}).status_code == 422
    assert client.post('/api/v1/feedback-uploads', files={'file': ('huge.jpg', b'x' * (6 * 1024 * 1024 + 1), 'image/jpeg')}).status_code == 413
    assert client.get('/api/v1/feedback-images/invalid.jpg').status_code == 404


def test_feedback_submission_and_reply_rate_limits(client):
    login(client)
    ids = [submit(client).json()['id'] for _ in range(5)]
    assert submit(client).status_code == 429
    with client.app.state.session_factory() as db:
        for row in db.scalars(select(Feedback)).all():
            row.created_at = now() - timedelta(hours=2)
        for _ in range(30):
            db.add(FeedbackReply(feedback_id=ids[0], author_id='demo-buyer', body='补充'))
        for i in range(20):
            path = f'/api/v1/feedback-images/limit-{i}.jpg'
            db.add(Upload(path=path, user_id='demo-buyer'))
            db.flush()
            db.add(FeedbackAttachment(path=path, user_id='demo-buyer'))
        db.commit()
    assert submit(client).status_code == 201
    assert client.post(f'/api/v1/feedback/{ids[0]}/replies', json={'body': '补充'}).status_code == 429
    assert screenshot(client).status_code == 429


def test_feedback_pagination_filters_and_restart_preserve_data(client):
    login(client)
    with client.app.state.session_factory() as db:
        for i in range(23):
            db.add(Feedback(user_id='demo-buyer', category='使用建议', body=f'测试反馈{i}', status='OPEN'))
        db.add(Feedback(user_id='demo-seller', category='使用建议', body='其他用户反馈', status='RESOLVED'))
        db.commit()
    for _ in range(2):
        prepare_database(client.app.state.engine)
    first = client.get('/api/v1/feedback?page=1').json()
    second = client.get('/api/v1/feedback?page=2').json()
    assert first['total'] == 23 and len(first['items']) == 20 and len(second['items']) == 3
    assert not {r['id'] for r in first['items']} & {r['id'] for r in second['items']}
    assert client.get('/api/v1/feedback?page=0').status_code == 422
    login(client, 'admin')
    assert client.get('/api/v1/admin/feedback?status=RESOLVED').json()['total'] == 1
    assert client.get('/api/v1/admin/feedback?status=bad').status_code == 422
