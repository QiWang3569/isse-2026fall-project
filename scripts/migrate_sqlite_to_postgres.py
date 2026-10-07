"""Copy a consistent SQLite snapshot into an empty PostgreSQL database.

Stop the application before running this command so no writes are missed.
The snapshot remains in data/backups for rollback. No source rows are deleted.
"""

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import MetaData, create_engine, func, inspect, select
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))

from app.config import Settings  # noqa: E402
from app.database import prepare_database  # noqa: E402
from app.models import Base  # noqa: E402


def snapshot_sqlite(source: Path) -> Path:
    if not source.is_file():
        raise ValueError(f'SQLite database does not exist: {source}')
    backups = ROOT / 'data' / 'backups'
    backups.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
    backup = backups / f'{source.stem}-{stamp}.db'
    backup.touch(mode=0o600, exist_ok=False)
    try:
        with sqlite3.connect(f'file:{source.resolve()}?mode=ro', uri=True) as original:
            with sqlite3.connect(backup) as copy:
                original.backup(copy)
                if copy.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise RuntimeError('SQLite snapshot failed integrity check')
    except BaseException:
        backup.unlink(missing_ok=True)
        raise
    return backup


def migrate(source: Path, target_url: str) -> tuple[Path, dict[str, int]]:
    if make_url(target_url).get_backend_name() != 'postgresql':
        raise ValueError('DATABASE_URL must point to PostgreSQL')
    target_engine = create_engine(target_url, pool_pre_ping=True)
    source_engine = None
    try:
        with target_engine.connect() as postgres:
            existing = set(inspect(postgres).get_table_names())
            occupied = [table.name for table in Base.metadata.sorted_tables
                        if table.name in existing and postgres.scalar(select(func.count()).select_from(table))]
            if occupied:
                raise ValueError('PostgreSQL target contains project data; import requires empty tables')
        backup = snapshot_sqlite(source)
        source_engine = create_engine(f'sqlite:///{backup}')
        prepare_database(target_engine)
        source_tables = set(inspect(source_engine).get_table_names())
        source_metadata = MetaData()
        source_metadata.reflect(bind=source_engine)
        counts = {}
        with source_engine.connect() as sqlite, target_engine.begin() as postgres:
            occupied = [table.name for table in Base.metadata.sorted_tables
                        if postgres.scalar(select(func.count()).select_from(table))]
            if occupied:
                raise ValueError('PostgreSQL target contains project data; import requires empty tables')
            for target_table in Base.metadata.sorted_tables:
                if target_table.name not in source_tables:
                    continue
                source_table = source_metadata.tables[target_table.name]
                names = set(target_table.columns.keys())
                rows = [dict(row) for row in sqlite.execute(select(source_table)).mappings()]
                for row in rows:
                    row_keys = set(row)
                    if not row_keys <= names:
                        raise ValueError(f'{target_table.name} has columns absent from the current model')
                    if target_table.name in {'items', 'buyer_intents'}:
                        vector = row.get('embedding')
                        if vector is not None and (not isinstance(vector, list) or len(vector) != 1536):
                            raise ValueError(f'{target_table.name} contains a non-1536-dimensional vector')
                if rows:
                    postgres.execute(target_table.insert(), rows)
                actual = postgres.scalar(select(func.count()).select_from(target_table))
                if actual != len(rows):
                    raise RuntimeError(f'Row count mismatch in {target_table.name}')
                counts[target_table.name] = actual
        return backup, counts
    finally:
        if source_engine is not None:
            source_engine.dispose()
        target_engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'data' / 'yandu.db')
    parser.add_argument('--apply', action='store_true', help='required to import data')
    args = parser.parse_args()
    if not args.apply:
        parser.error('pass --apply after stopping the application and confirming the target is empty')
    backup, counts = migrate(args.source, Settings().database_url)
    print(f'SQLite backup: {backup}')
    print('Copied rows: ' + ', '.join(f'{name}={count}' for name, count in counts.items()))


if __name__ == '__main__':
    main()
