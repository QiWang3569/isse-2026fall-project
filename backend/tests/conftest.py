import io
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import Settings
from app.main import create_app


@pytest.fixture(autouse=True)
def isolate_local_environment(monkeypatch):
    # Tests must not inherit credentials or provider settings from a developer's .env.
    for name in ('APP_ENV', 'SESSION_COOKIE_SECURE', 'AI_MODE', 'EMBEDDING_MODE', 'DEEPSEEK_API_KEY', 'DEEPSEEK_BASE_URL', 'DEEPSEEK_MODEL',
                 'EMBEDDING_API_KEY', 'EMBEDDING_BASE_URL', 'EMBEDDING_MODEL', 'MODEL_THINKING',
                 'MODEL_TIMEOUT_SECONDS', 'MATCH_MAX_ATTEMPTS', 'MATCH_THRESHOLD', 'DATABASE_URL',
                 'DEMO_MODE', 'ALLOWED_ORIGINS', 'AUTH_CODE_SECRET', 'SMTP_HOST',
                 'SMTP_PORT', 'SMTP_USER', 'SMTP_PASSWORD', 'SMTP_FROM'):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def app(tmp_path):
    return create_app(Settings(database_url=f'sqlite:///{tmp_path / "test.db"}', data_dir=tmp_path, demo_mode=True, ai_mode='local'))


@pytest.fixture
def client(app):
    with TestClient(app) as client:
        yield client


def login(client, profile='buyer'):
    response = client.post('/api/v1/auth/demo', json={'profile': profile})
    assert response.status_code == 200
    return response.json()['user']


def photo(client):
    stream = io.BytesIO()
    Image.new('RGB', (80, 80), '#88aa99').save(stream, 'PNG')
    result = client.post('/api/v1/uploads', files={'file': ('mouse.png', stream.getvalue(), 'image/png')})
    assert result.status_code == 201, result.text
    return result.json()['url']


def publish(client, **changes):
    payload = {'title': '安静的无线鼠标', 'description': '静音无线鼠标，功能正常，附接收器，万柳当面交易。',
               'category': '数码与影音', 'price': 200, 'campus': '万柳学区', 'condition_grade': '95新',
               'tags': ['静音', '鼠标'], 'images': [photo(client)]}
    payload.update(changes)
    return client.post('/api/v1/items/', json=payload)


def intent(client, query='蹲一个万柳附近 300 元以内的静音鼠标'):
    parsed = client.post('/api/v1/intents/parse', json={'raw_query': query})
    assert parsed.status_code == 200, parsed.text
    return client.post('/api/v1/intents/', json={'raw_query': query, 'parsed': parsed.json()['parsed']})
