"""Exercise follow-up features against an isolated, disposable pgvector container.

Requires Docker, a local pgvector/pgvector:pg16 image, and backend dependencies.
Creates its own database in tmpfs, binds a random loopback port, uses synthetic
data and a stub mail sender, and removes only its own container in finally.
No production database URL, backup, SMTP credentials, or volumes are used.
"""
import json
import secrets
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from threading import Barrier, Event
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, inspect, select, text, update
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app import chat_email, main as app_main
from app.chat_email import ChatEmailQueue, ChatEmailReceipt, process_chat_email_batch
from app.config import Settings
from app.database import prepare_database
from app.models import ChatMessage, Conversation, Intent, Item, ItemDraft, User, Wanted, now
from app.services import seed
from app.wanted_watch import WantedWatch


IMAGE = 'pgvector/pgvector:pg16'
WANTED = {'title': '求购静音鼠标', 'description': '需要静音鼠标，用于自习室学习',
          'category': '数码与影音', 'budget': 300, 'campus': '万柳学区'}
ITEM = {'title': '长期出售静音鼠标', 'description': '静音无线鼠标，功能正常，万柳面交。',
        'category': '数码与影音', 'price': 100, 'campus': '万柳学区', 'validity_days': 0}


def docker(*args):
    return subprocess.run(['docker', *args], check=True, capture_output=True, text=True, timeout=60).stdout.strip()


def request(client, method, path, expected=200, **kwargs):
    response = getattr(client, method)(path, **kwargs)
    assert response.status_code == expected, (path, response.status_code, response.text)
    return response.json()


def login(client, profile='buyer'):
    request(client, 'post', '/api/v1/auth/demo', json={'profile': profile})


def legacy_upgrade(engine, factory):
    prepare_database(engine)
    deadline = now() + timedelta(days=3)
    with factory.begin() as db:
        seed(db)
    with factory.begin() as db:
        db.get(Item, 'sample-1').expires_at = deadline
        db.add(Intent(id='legacy-intent', buyer_id='demo-buyer', raw_query='鼠标',
                      keywords=['鼠标'], status='PAUSED', expires_at=deadline))
        db.add(Wanted(id='legacy-wanted', buyer_id='demo-buyer', title='旧求购鼠标', description='求购静音鼠标',
                      category='数码与影音', budget_cents=5000, campus='万柳学区', expires_at=deadline))
        db.add(ItemDraft(id='legacy-draft', seller_id='demo-seller', raw='旧草稿静音鼠标'))
    # Remove only columns and tables in this newly created disposable database.
    with engine.begin() as connection:
        for table in ('chat_email_receipts', 'chat_email_queue', 'wanted_watches'):
            connection.execute(text(f'DROP TABLE {table}'))
        for table in ('items', 'item_drafts', 'buyer_intents', 'wanted_posts'):
            connection.execute(text(f'ALTER TABLE {table} DROP COLUMN validity_days'))
        connection.execute(text('ALTER TABLE users DROP COLUMN email_notifications'))
    for _ in range(2):
        prepare_database(engine)
        with factory() as db:
            for model, identity, days in ((Item, 'sample-1', 14), (Intent, 'legacy-intent', 14),
                                          (Wanted, 'legacy-wanted', 7)):
                row = db.get(model, identity)
                assert row.expires_at == deadline and row.validity_days == days
            assert db.get(ItemDraft, 'legacy-draft').validity_days == 14
            assert db.get(User, 'demo-buyer').email_notifications is False
        assert {'wanted_watches', 'chat_email_queue', 'chat_email_receipts'} <= set(inspect(engine).get_table_names())


def wanted_and_lifetime_checks(first, second, factory):
    login(first, 'seller')
    item = request(first, 'post', '/api/v1/items/', 201, json=ITEM)
    assert item['expires_at'] is None
    with factory.begin() as db:
        db.get(Item, item['id']).expires_at = now() - timedelta(days=10)
    rows = request(first, 'get', '/api/v1/items/', params={'q': '长期出售静音鼠标'})['items']
    assert any(row['id'] == item['id'] and row['status'] == 'ACTIVE' for row in rows)

    login(first)
    login(second)
    post = request(first, 'post', '/api/v1/wanted/', 201, json=WANTED)
    barrier = Barrier(2)
    original_embed = app_main.embed

    def synchronized_embed(*args, **kwargs):
        barrier.wait(timeout=10)
        return original_embed(*args, **kwargs)

    # Distinct app instances have independent Python locks. PostgreSQL must
    # serialize the same user/wanted pair and return the existing association.
    with patch.object(app_main, 'embed', synchronized_embed), ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(request, client, 'post', f"/api/v1/wanted/{post['id']}/watch",
                               json={'validity_days': 30}) for client in (first, second)]
        results = [future.result(timeout=20) for future in futures]
    task_id = results[0]['linked_intent_id']
    assert task_id and task_id == results[1]['linked_intent_id']
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(WantedWatch).where(WantedWatch.wanted_id == post['id'])) == 1
        task = db.get(Intent, task_id)
        assert task.validity_days == 30 and task.max_price_cents == 30000
    for _ in range(4):
        request(first, 'post', '/api/v1/intents/', 201,
                json={'raw_query': '静音鼠标', 'parsed': {'keywords': ['鼠标']}})
    with factory() as db:
        before = db.scalar(select(func.count()).select_from(Wanted))
    request(first, 'post', '/api/v1/wanted/', 409, json={**WANTED, 'enable_watch': True})
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Wanted)) == before
    duplicate = request(first, 'post', f"/api/v1/wanted/{post['id']}/watch")
    assert duplicate['linked_intent_id'] == task_id
    request(first, 'delete', f"/api/v1/wanted/{post['id']}?stop_watch=true")
    with factory() as db:
        assert db.get(Wanted, post['id']).status == 'COMPLETED'
        assert db.get(Intent, task_id).status == 'COMPLETED'
    return item['id']


def locked_sale_check(client, app, engine, factory):
    login(client)
    conversation = request(client, 'post', '/api/v1/items/sample-1/conversations', 201,
                           json={'body': '测试并发预订'})['conversation']['id']
    path = f'/api/v1/conversations/{conversation}/deal'
    request(client, 'post', path, json={'action': 'request'})
    login(client, 'seller')
    request(client, 'post', path, json={'action': 'reserve'})
    login(client)
    entering_lock = Event()

    def observe_stale_conversation(execution):
        if not execution.is_select or execution.statement._for_update_arg is None:
            return
        if Item not in [column.get('entity') for column in execution.statement.column_descriptions]:
            return
        loaded = [row for row in execution.session.identity_map.values()
                  if isinstance(row, Conversation) and row.id == conversation]
        if loaded:
            assert loaded[0].deal_status == 'RESERVED'
            entering_lock.set()

    with engine.connect() as seller_connection:
        transaction = seller_connection.begin()
        seller_pid = seller_connection.scalar(text('SELECT pg_backend_pid()'))
        seller_connection.execute(select(Item.id).where(Item.id == 'sample-1').with_for_update())
        event.listen(app.state.session_factory.class_, 'do_orm_execute', observe_stale_conversation)
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(client.post, path, json={'action': 'cancel'})
                try:
                    assert entering_lock.wait(timeout=10), 'Buyer did not reach the item row lock'
                    blocked = False
                    for _ in range(100):
                        with engine.connect() as observer:
                            blocked = bool(observer.scalar(text(
                                'SELECT EXISTS (SELECT 1 FROM pg_stat_activity '
                                "WHERE datname = current_database() AND wait_event_type = 'Lock' "
                                'AND :seller = ANY(pg_blocking_pids(pid)))'), {'seller': seller_pid}))
                        if blocked:
                            break
                        time.sleep(0.05)
                    assert blocked, 'Did not observe an actual PostgreSQL row-lock wait'
                    seller_connection.execute(update(Item).where(Item.id == 'sample-1').values(status='SOLD'))
                    seller_connection.execute(update(Conversation).where(Conversation.id == conversation).values(deal_status='SOLD'))
                    transaction.commit()
                finally:
                    if transaction.is_active:
                        transaction.rollback()
                response = future.result(timeout=10)
                assert response.status_code == 409, response.text
        finally:
            event.remove(app.state.session_factory.class_, 'do_orm_execute', observe_stale_conversation)
            if transaction.is_active:
                transaction.rollback()
    with factory() as db:
        assert db.get(Item, 'sample-1').status == 'SOLD'
        assert db.get(Conversation, conversation).deal_status == 'SOLD'
    assert request(client, 'post', path, json={'action': 'confirm'})['deal_status'] == 'CONFIRMED'


def mail_checks(engine, factory, settings):
    instant = now()
    with factory.begin() as db:
        db.add_all([User(id='qa-buyer', nickname='测试买家', campus='万柳学区', email='qa-buyer@pku.edu.cn'),
                    User(id='qa-seller', nickname='测试卖家', campus='万柳学区',
                         email='qa-seller@pku.edu.cn', email_notifications=True)])
        db.flush()
        db.add(Item(id='qa-item', seller_id='qa-seller', title='测试商品', category='数码与影音',
                    campus='万柳学区', price_cents=1000))
        db.flush()
        db.add(Conversation(id='qa-conversation', item_id='qa-item', buyer_id='qa-buyer', seller_id='qa-seller'))
        db.flush()
        db.add_all([ChatMessage(id=f'qa-message-{index}', conversation_id='qa-conversation', sender_id='qa-buyer',
                               body='仅在隔离数据库中使用的测试消息', created_at=instant - timedelta(minutes=6))
                    for index in range(2)])
    configured = replace(settings, chat_email_enabled=True, public_app_url='https://yandu.example',
                         smtp_host='unused.invalid', smtp_from='qa@example.org')
    with patch.object(chat_email, 'send_chat_email', side_effect=RuntimeError('simulated SMTP outage')):
        assert process_chat_email_batch(factory, configured, at=instant) == 0
    with factory() as db:
        queue = db.get(ChatEmailQueue, ('qa-conversation', 'qa-seller'))
        assert queue.attempts == 1 and queue.lease_token is None
    sent = []

    def capture(_, message):
        assert engine.pool.checkedout() == 0, 'Mail sender held a database transaction'
        sent.append(message)

    with patch.object(chat_email, 'send_chat_email', capture):
        assert process_chat_email_batch(factory, configured, at=instant + timedelta(seconds=31)) == 1
        assert process_chat_email_batch(factory, configured, at=instant + timedelta(days=1)) == 0
    assert len(sent) == 1 and '2 条未读消息' in sent[0]['Subject']
    assert 'https://yandu.example/#messages/qa-conversation' in sent[0].get_content()
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(ChatEmailReceipt)) == 2


def main():
    docker('image', 'inspect', IMAGE)
    name = 'yandu-followup-verify-' + uuid4().hex[:12]
    password = secrets.token_hex(24)
    container_id = None
    engine = None
    checks = []
    try:
        container_id = docker('run', '-d', '--name', name, '--label', 'yandu.verification=followup',
                              '--tmpfs', '/var/lib/postgresql/data:rw', '-p', '127.0.0.1::5432',
                              '-e', 'POSTGRES_DB=yandu_followup_verify', '-e', 'POSTGRES_USER=yandu_verify',
                              '-e', 'POSTGRES_PASSWORD=' + password, IMAGE)
        port = int(docker('port', container_id, '5432/tcp').rsplit(':', 1)[1])
        url = f'postgresql+psycopg://yandu_verify:{password}@127.0.0.1:{port}/yandu_followup_verify'
        engine = create_engine(url, pool_pre_ping=True, connect_args={'connect_timeout': 3})
        for attempt in range(60):
            try:
                with engine.connect() as connection:
                    version = connection.scalar(text('SHOW server_version'))
                break
            except Exception:
                if attempt == 59:
                    raise RuntimeError('Isolated PostgreSQL did not become ready') from None
                time.sleep(0.5)
        factory = sessionmaker(engine, expire_on_commit=False)
        legacy_upgrade(engine, factory)
        checks.append('legacy_schema_upgrade_idempotent_preserves_data')
        with tempfile.TemporaryDirectory(prefix='yandu-pg-verify-') as directory:
            settings = Settings(app_env='local', database_url=url, data_dir=Path(directory), demo_mode=True,
                                ai_mode='local', embedding_mode='local', session_cookie_secure=False,
                                chat_email_enabled=False, public_app_url='', smtp_host='', smtp_from='',
                                origins=['http://testserver'])
            app = app_main.create_app(settings)
            with TestClient(app) as first, TestClient(app_main.create_app(settings)) as second:
                permanent_id = wanted_and_lifetime_checks(first, second, factory)
                checks.extend(['permanent_item_public_filter', 'wanted_watch_concurrent_idempotency',
                               'wanted_watch_quota_atomic_rollback', 'wanted_close_stops_linked_watch'])
                locked_sale_check(first, app, engine, factory)
                checks.append('postgres_row_lock_stale_cancel_cannot_overwrite_sale')
            mail_checks(engine, factory, settings)
            checks.append('postgres_mail_batch_merge_retry_receipts_no_live_smtp')
            with TestClient(app_main.create_app(settings)) as restarted:
                login(restarted)
                assert request(restarted, 'get', f'/api/v1/items/{permanent_id}')['expires_at'] is None
                with factory() as db:
                    assert db.get(ItemDraft, 'legacy-draft') is not None
                    assert db.scalar(select(func.count()).select_from(ChatEmailReceipt)) == 2
            checks.append('restart_preserves_feature_and_legacy_data')
        print(json.dumps({'status': 'passed', 'postgresql': version, 'checks': checks,
                          'smtp': 'stub only', 'storage': 'isolated tmpfs'}, ensure_ascii=False), flush=True)
    finally:
        if engine:
            engine.dispose()
        if container_id:
            docker('rm', '-f', '-v', container_id)
            print(json.dumps({'cleanup': 'removed own container', 'name': name}), flush=True)


if __name__ == '__main__':
    main()
