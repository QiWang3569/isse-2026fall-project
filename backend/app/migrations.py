"""Additive, idempotent upgrade for the existing 0.1 SQLite/PostgreSQL database."""
from sqlalchemy import inspect, text


def upgrade_buyer_agent(engine):
    additions = {
        'buyer_intents': {'excluded_keywords': "JSON NOT NULL DEFAULT '[]'",
                         'preferences': "JSON NOT NULL DEFAULT '[]'"},
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
