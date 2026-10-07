#!/bin/sh
set -eu
umask 077

: "${PGHOST:?}"
: "${PGUSER:?}"
: "${PGDATABASE:?}"
: "${PGPASSWORD:?}"
BACKUP_RETENTION_DAYS=${BACKUP_RETENTION_DAYS:-14}
case "$BACKUP_RETENTION_DAYS" in
  ''|*[!0-9]*) echo 'BACKUP_RETENTION_DAYS must be a positive integer' >&2; exit 1 ;;
esac
[ "$BACKUP_RETENTION_DAYS" -ge 1 ] || { echo 'BACKUP_RETENTION_DAYS must be positive' >&2; exit 1; }
mkdir -p /backups

while :; do
  stamp=$(date -u +%Y%m%dT%H%M%SZ)
  target="/backups/yandu-${stamp}.dump"
  temporary="${target}.tmp"
  if pg_dump --format=custom --no-owner --no-privileges --file="$temporary"; then
    if pg_restore --list "$temporary" >/dev/null; then
      mv "$temporary" "$target"
      find /backups -maxdepth 1 -type f -name 'yandu-*.dump' -mtime "+${BACKUP_RETENTION_DAYS}" -delete
      echo "PostgreSQL backup complete: $(basename "$target")"
    else
      rm -f "$temporary"
      echo 'PostgreSQL archive validation failed' >&2
      exit 1
    fi
  else
    rm -f "$temporary"
    echo 'PostgreSQL backup failed' >&2
    exit 1
  fi
  sleep 86400
done
