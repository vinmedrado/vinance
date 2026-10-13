#!/usr/bin/env bash
set -Eeuo pipefail

: "${DRILL_TARGET_DATABASE_URL:?DRILL_TARGET_DATABASE_URL is required}"
/usr/local/bin/backup.sh
backup_file="$(find "${BACKUP_ROOT:-/backups}/daily" -maxdepth 1 -type f -name 'vinance-*.dump.enc' -printf '%T@ %p\n' | sort -rn | head -n 1 | cut -d' ' -f2-)"
test -n "$backup_file" || { echo "No backup artifact was produced" >&2; exit 7; }
RESTORE_DATABASE_URL="$DRILL_TARGET_DATABASE_URL" /usr/local/bin/restore.sh \
  --backup "$backup_file" \
  --passphrase-file "$BACKUP_PASSPHRASE_FILE"

source_tables="$(psql "$BACKUP_DATABASE_URL" -Atv ON_ERROR_STOP=1 -c "SELECT count(*) FROM pg_tables WHERE schemaname='public'")"
target_tables="$(psql "$DRILL_TARGET_DATABASE_URL" -Atv ON_ERROR_STOP=1 -c "SELECT count(*) FROM pg_tables WHERE schemaname='public'")"
source_users="$(psql "$BACKUP_DATABASE_URL" -Atv ON_ERROR_STOP=1 -c 'SELECT count(*) FROM users')"
target_users="$(psql "$DRILL_TARGET_DATABASE_URL" -Atv ON_ERROR_STOP=1 -c 'SELECT count(*) FROM users')"
source_revision="$(psql "$BACKUP_DATABASE_URL" -Atv ON_ERROR_STOP=1 -c 'SELECT version_num FROM alembic_version')"
target_revision="$(psql "$DRILL_TARGET_DATABASE_URL" -Atv ON_ERROR_STOP=1 -c 'SELECT version_num FROM alembic_version')"
source_constraints="$(psql "$BACKUP_DATABASE_URL" -Atv ON_ERROR_STOP=1 -c "SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname='public'")"
target_constraints="$(psql "$DRILL_TARGET_DATABASE_URL" -Atv ON_ERROR_STOP=1 -c "SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname='public'")"
test "$source_tables" = "$target_tables"
test "$source_users" = "$target_users"
test "$source_revision" = "$target_revision"
test "$source_constraints" = "$target_constraints"
echo "restore_drill_status=ok tables=$target_tables users=$target_users revision=$target_revision constraints=$target_constraints"
