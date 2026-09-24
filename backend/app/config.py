import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / '.env')


@dataclass
class Settings:
    database_url: str = field(default_factory=lambda: os.getenv('DATABASE_URL', f'sqlite:///{ROOT / "data/yandu.db"}'))
    data_dir: Path = field(default_factory=lambda: ROOT / 'data')
    demo_mode: bool = field(default_factory=lambda: os.getenv('DEMO_MODE', 'true').lower() == 'true')
    ai_mode: str = field(default_factory=lambda: os.getenv('AI_MODE', 'local'))
    threshold: float = field(default_factory=lambda: float(os.getenv('MATCH_THRESHOLD', '0.82')))
    deepseek_key: str = field(default_factory=lambda: os.getenv('DEEPSEEK_API_KEY', ''))
    deepseek_url: str = field(default_factory=lambda: os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com'))
    deepseek_model: str = field(default_factory=lambda: os.getenv('DEEPSEEK_MODEL', 'deepseek-chat'))
    embedding_key: str = field(default_factory=lambda: os.getenv('EMBEDDING_API_KEY', ''))
    embedding_url: str = field(default_factory=lambda: os.getenv('EMBEDDING_BASE_URL', 'https://api.openai.com/v1'))
    embedding_model: str = field(default_factory=lambda: os.getenv('EMBEDDING_MODEL', 'text-embedding-3-small'))
    origins: list[str] = field(default_factory=lambda: os.getenv('ALLOWED_ORIGINS', 'http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:8000,http://localhost:8000').split(','))

    def __post_init__(self):
        if self.ai_mode not in {'local', 'remote'}:
            raise ValueError('AI_MODE must be local or remote')
        if self.ai_mode == 'remote' and not (self.deepseek_key and self.embedding_key):
            raise ValueError('Remote mode requires DeepSeek and embedding credentials')
        if not 0 <= self.threshold <= 1:
            raise ValueError('MATCH_THRESHOLD must be between 0 and 1')
