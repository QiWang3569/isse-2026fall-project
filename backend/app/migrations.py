"""Additive, idempotent upgrade for the existing 0.1 SQLite/PostgreSQL database."""
from sqlalchemy import inspect, text


def upgrade_buyer_agent(engine):
    additions = {
        'users': {'email': 'VARCHAR(254)', 'password_hash': 'VARCHAR(255)',
                  'email_notifications': 'BOOLEAN NOT NULL DEFAULT FALSE',
                  'bio': "VARCHAR(160) NOT NULL DEFAULT ''",
                  'avatar_color': "VARCHAR(20) NOT NULL DEFAULT 'sage'"},
        'buyer_intents': {'excluded_keywords': "JSON NOT NULL DEFAULT '[]'",
                         'preferences': "JSON NOT NULL DEFAULT '[]'",
                         'completed_item_id': 'VARCHAR(36)',
                         'validity_days': 'INTEGER NOT NULL DEFAULT 14'},
        'items': {'validity_days': 'INTEGER NOT NULL DEFAULT 14'},
        'item_drafts': {'validity_days': 'INTEGER NOT NULL DEFAULT 14'},
        'wanted_posts': {'validity_days': 'INTEGER NOT NULL DEFAULT 7'},
        'conversations': {'deal_status': "VARCHAR(20) NOT NULL DEFAULT 'NONE'"},
        'chat_messages': {'hidden_at': 'TIMESTAMP'},
        'match_notifications': {'verdict': "VARCHAR(20) NOT NULL DEFAULT 'MATCH'",
                                'questions': "JSON NOT NULL DEFAULT '[]'",
                                'evidence': "JSON NOT NULL DEFAULT '[]'",
                                'review_mode': "VARCHAR(20) NOT NULL DEFAULT 'local'"},
    }
    with engine.begin() as conn:
        inspector = inspect(conn)
        for table, fields in additions.items():
            existing = {c['name'] for c in inspector.get_columns(table)}
            for name, ddl in fields.items():
                if name not in existing:
                    conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {name} {ddl}'))
        conn.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email ON users (email)'))
