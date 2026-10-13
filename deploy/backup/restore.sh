#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  echo "usage: RESTORE_DATABASE_URL=... restore.sh --backup FILE --passphrase-file FILE" >&2
  exit 2
}

target_url="${RESTORE_DATABASE_URL:-}"
backup_file=""
passphrase_file=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --backup) backup_file="${2:-}"; shift 2 ;;
    --passphrase-file) passphrase_file="${2:-}"; shift 2 ;;
    *) usage ;;
  esac
done

test -n "$target_url" && test -f "$backup_file" && test -s "$passphrase_file" || usage
if [ -n "${DATABASE_URL:-}" ] && [ "$target_url" = "$DATABASE_URL" ]; then
  echo "Refusing to restore into DATABASE_URL" >&2
  exit 3
fi

target_name="$(psql "$target_url" -Atv ON_ERROR_STOP=1 -c 'SELECT current_database()')"
if [ -n "${CANONICAL_DATABASE_NAME:-}" ] && [ "$target_name" = "$CANONICAL_DATABASE_NAME" ]; then
  echo "Refusing to restore into canonical database" >&2
  exit 3
fi
user_tables="$(psql "$target_url" -Atv ON_ERROR_STOP=1 -c "SELECT count(*) FROM pg_tables WHERE schemaname NOT IN ('pg_catalog','information_schema')")"
if [ "$user_tables" != "0" ]; then
  echo "Target database must be empty" >&2
  exit 4
fi

checksum_file="${backup_file}.sha256"
test -s "$checksum_file" || { echo "Checksum file missing" >&2; exit 5; }
(cd "$(dirname "$backup_file")" && sha256sum -c "$(basename "$checksum_file")")

raw="$(mktemp /tmp/vinance-restore.XXXXXX.dump)"
trap 'rm -f -- "$raw"' EXIT
openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
  -pass "file:$passphrase_file" -in "$backup_file" -out "$raw"
test -s "$raw" || { echo "Decryption produced an empty file" >&2; exit 6; }
pg_restore --exit-on-error --no-owner --no-acl --dbname="$target_url" "$raw"
echo "restore_status=ok database=$target_name"
