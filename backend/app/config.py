import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / '.env')


@dataclass
class Settings:
    app_env: str = field(default_factory=lambda: os.getenv('APP_ENV', 'local'))
    database_url: str = field(default_factory=lambda: os.getenv('DATABASE_URL', f'sqlite:///{ROOT / "data/yandu.db"}'))
    data_dir: Path = field(default_factory=lambda: ROOT / 'data')
    demo_mode: bool = field(default_factory=lambda: os.getenv('DEMO_MODE', 'true').lower() == 'true')
    session_cookie_secure: bool = field(default_factory=lambda: os.getenv('SESSION_COOKIE_SECURE', 'false').lower() == 'true')
    ai_mode: str = field(default_factory=lambda: os.getenv('AI_MODE', 'local'))
    embedding_mode: str | None = field(default_factory=lambda: os.getenv('EMBEDDING_MODE'))
    model_timeout: float = field(default_factory=lambda: float(os.getenv('MODEL_TIMEOUT_SECONDS', '20')))
    match_attempts: int = field(default_factory=lambda: int(os.getenv('MATCH_MAX_ATTEMPTS', '3')))
    threshold: float = field(default_factory=lambda: float(os.getenv('MATCH_THRESHOLD', '0.82')))
    deepseek_key: str = field(default_factory=lambda: os.getenv('DEEPSEEK_API_KEY', ''))
    deepseek_url: str = field(default_factory=lambda: os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com'))
    deepseek_model: str = field(default_factory=lambda: os.getenv('DEEPSEEK_MODEL', 'deepseek-chat'))
    model_thinking: str | None = field(default_factory=lambda: os.getenv('MODEL_THINKING'))
    embedding_key: str = field(default_factory=lambda: os.getenv('EMBEDDING_API_KEY', ''))
    embedding_url: str = field(default_factory=lambda: os.getenv('EMBEDDING_BASE_URL', 'https://api.openai.com/v1'))
    embedding_model: str = field(default_factory=lambda: os.getenv('EMBEDDING_MODEL', 'text-embedding-3-small'))
    origins: list[str] = field(default_factory=lambda: os.getenv('ALLOWED_ORIGINS', 'http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:8000,http://localhost:8000').split(','))
    auth_secret: str = field(default_factory=lambda: os.getenv('AUTH_CODE_SECRET', ''))
    smtp_host: str = field(default_factory=lambda: os.getenv('SMTP_HOST', ''))
    smtp_port: int = field(default_factory=lambda: int(os.getenv('SMTP_PORT', '465')))
    smtp_user: str = field(default_factory=lambda: os.getenv('SMTP_USER', ''))
    smtp_password: str = field(default_factory=lambda: os.getenv('SMTP_PASSWORD', ''))
    smtp_from: str = field(default_factory=lambda: os.getenv('SMTP_FROM', ''))
    chat_retention_days: int = field(default_factory=lambda: int(os.getenv('CHAT_RETENTION_DAYS', '180')))

    def __post_init__(self):
        if self.app_env not in {'local', 'production'}:
            raise ValueError('APP_ENV must be local or production')
        if self.ai_mode not in {'local', 'remote'}:
            raise ValueError('AI_MODE must be local or remote')
        if self.embedding_mode is None:
            self.embedding_mode = 'remote' if self.ai_mode == 'remote' and self.embedding_key else 'local'
        if self.embedding_mode not in {'local', 'remote'}:
            raise ValueError('EMBEDDING_MODE must be local or remote')
        if self.model_thinking not in {None, 'enabled', 'disabled'}:
            raise ValueError('MODEL_THINKING must be enabled or disabled when set')
        if self.ai_mode == 'remote' and not self.deepseek_key:
            raise ValueError('Remote AI mode requires DEEPSEEK_API_KEY')
        if self.embedding_mode == 'remote' and not self.embedding_key:
            raise ValueError('Remote embedding mode requires EMBEDDING_API_KEY')
        if not 1 <= self.model_timeout <= 120 or not 1 <= self.match_attempts <= 5:
            raise ValueError('Model timeout must be 1–120 seconds; match attempts must be 1–5')
        if not 0 <= self.threshold <= 1:
            raise ValueError('MATCH_THRESHOLD must be between 0 and 1')
        if not 30 <= self.chat_retention_days <= 3650:
            raise ValueError('CHAT_RETENTION_DAYS must be between 30 and 3650')
        if self.app_env == 'production':
            if not self.database_url.startswith('postgresql') or self.demo_mode:
                raise ValueError('Production requires PostgreSQL and DEMO_MODE=false')
            if not self.session_cookie_secure or not self.email_auth_ready or not self.smtp_user or not self.smtp_password:
                raise ValueError('Production requires secure cookies and configured email verification')
            if len(self.origins) != 1 or urlparse(self.origins[0]).scheme != 'https' or not urlparse(self.origins[0]).hostname:
                raise ValueError('Production requires one HTTPS origin')

    @property
    def email_auth_ready(self):
        return len(self.auth_secret) >= 32 and bool(self.smtp_host and self.smtp_from)
