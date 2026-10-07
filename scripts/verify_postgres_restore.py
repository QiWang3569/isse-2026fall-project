"""Restore the latest PostgreSQL dump into a temporary database, then remove it."""

import argparse
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BACKUPS = ROOT / 'data' / 'backups' / 'postgres'


def run(compose_file: Path, *args: str, input_file=None) -> str:
    command = ['docker', 'compose', '-f', str(compose_file), 'exec', '-T', 'postgres', *args]
    result = subprocess.run(command, cwd=ROOT, stdin=input_file, capture_output=True, check=True)
    return result.stdout.decode().strip()


def verify(archive: Path, compose_file: Path):
    if not archive.is_file() or archive.stat().st_size == 0:
        raise ValueError('Backup archive is missing or empty')
    temporary_db = 'yandu_restore_' + datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')
    user = run(compose_file, 'sh', '-c', 'printf %s "$POSTGRES_USER"')
    created = False
    try:
        run(compose_file, 'createdb', '-U', user, temporary_db)
        created = True
        with archive.open('rb') as stream:
            run(compose_file, 'pg_restore', '--exit-on-error', '--no-owner', '--no-privileges',
                '-U', user, '-d', temporary_db, input_file=stream)
        result = run(compose_file, 'psql', '-U', user, '-d', temporary_db, '-At', '-c',
                     "SELECT (SELECT count(*) FROM users), (SELECT count(*) FROM items), "
                     "(SELECT count(*) FROM users WHERE role = 'admin' AND id NOT LIKE 'demo-%'), "
                     "(SELECT extversion FROM pg_extension WHERE extname = 'vector')")
        users, items, real_admins, vector_version = result.split('|')
        print(f'Restore verified: users={users}, items={items}, real_admins={real_admins}, pgvector={vector_version}')
    finally:
        if created:
            run(compose_file, 'dropdb', '-U', user, '--if-exists', '--force', temporary_db)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--compose-file', type=Path, default=ROOT / 'compose.yaml')
    args = parser.parse_args()
    archives = sorted(DEFAULT_BACKUPS.glob('yandu-*.dump'))
    archive = args.archive or (archives[-1] if archives else None)
    if archive is None:
        parser.error('No PostgreSQL backup found')
    verify(archive, args.compose_file)


if __name__ == '__main__':
    main()
