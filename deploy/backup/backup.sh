#!/usr/bin/env bash
set -Eeuo pipefail

: "${BACKUP_DATABASE_URL:?BACKUP_DATABASE_URL is required}"
: "${BACKUP_PASSPHRASE_FILE:?BACKUP_PASSPHRASE_FILE is required}"

BACKUP_ROOT="${BACKUP_ROOT:-/backups}"
DAILY_KEEP="${BACKUP_DAILY_KEEP:-7}"
WEEKLY_KEEP="${BACKUP_WEEKLY_KEEP:-4}"
MONTHLY_KEEP="${BACKUP_MONTHLY_KEEP:-3}"

case "$BACKUP_ROOT" in
  /|""|/var|/etc|/usr|/home) echo "Unsafe BACKUP_ROOT" >&2; exit 2 ;;
esac
test -s "$BACKUP_PASSPHRASE_FILE" || { echo "Backup passphrase file is missing or empty" >&2; exit 2; }

umask 077
mkdir -p "$BACKUP_ROOT/daily" "$BACKUP_ROOT/weekly" "$BACKUP_ROOT/monthly"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
encrypted="$BACKUP_ROOT/daily/vinance-${timestamp}.dump.enc"
encrypted_tmp="$(mktemp "$BACKUP_ROOT/daily/.vinance-${timestamp}.XXXXXX.dump.enc")"
checksum_tmp="$(mktemp "$BACKUP_ROOT/daily/.vinance-${timestamp}.XXXXXX.sha256")"
trap 'rm -f -- "$encrypted_tmp" "$checksum_tmp"' EXIT

pg_dump --format=custom --no-owner --no-acl --dbname="$BACKUP_DATABASE_URL" \
  | openssl enc -aes-256-cbc -salt -pbkdf2 -iter 200000 \
      -pass "file:$BACKUP_PASSPHRASE_FILE" -out "$encrypted_tmp"
test -s "$encrypted_tmp" || { echo "Encrypted pg_dump is empty" >&2; exit 4; }
checksum="$(sha256sum "$encrypted_tmp" | cut -d' ' -f1)"
printf '%s  %s\n' "$checksum" "$(basename "$encrypted")" > "$checksum_tmp"
# Publish the sidecar first. A power loss can leave an unused sidecar, but never
# a discoverable backup artifact without its checksum.
mv "$checksum_tmp" "${encrypted}.sha256"
mv "$encrypted_tmp" "$encrypted"

if [ "$(date -u +%u)" = "7" ]; then
  ln "$encrypted" "$BACKUP_ROOT/weekly/$(basename "$encrypted")"
  cp "${encrypted}.sha256" "$BACKUP_ROOT/weekly/$(basename "${encrypted}.sha256")"
fi
if [ "$(date -u +%d)" = "01" ]; then
  ln "$encrypted" "$BACKUP_ROOT/monthly/$(basename "$encrypted")"
  cp "${encrypted}.sha256" "$BACKUP_ROOT/monthly/$(basename "${encrypted}.sha256")"
fi

prune_bucket() {
  local bucket="$1" keep="$2" count=0 path
  while IFS= read -r path; do
    count=$((count + 1))
    if [ "$count" -gt "$keep" ]; then
      rm -f -- "$path" "${path}.sha256"
    fi
  done < <(find "$bucket" -maxdepth 1 -type f -name 'vinance-*.dump.enc' -printf '%T@ %p\n' | sort -rn | cut -d' ' -f2-)
}

prune_bucket "$BACKUP_ROOT/daily" "$DAILY_KEEP"
prune_bucket "$BACKUP_ROOT/weekly" "$WEEKLY_KEEP"
prune_bucket "$BACKUP_ROOT/monthly" "$MONTHLY_KEEP"

echo "backup_status=ok file=$(basename "$encrypted") checksum=$checksum"
