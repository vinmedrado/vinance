#!/usr/bin/env bash
set -Eeuo pipefail

path="${1:-/}"
used_percent="$(df -P "$path" | awk 'NR==2 {gsub(/%/, "", $5); print $5}')"
test -n "$used_percent" || { echo "disk_status=unknown path=$path"; exit 3; }
free_percent=$((100 - used_percent))

if [ "$free_percent" -lt 10 ]; then
  echo "disk_status=critical path=$path free_percent=$free_percent"
  exit 2
fi
if [ "$free_percent" -lt 20 ]; then
  echo "disk_status=warning path=$path free_percent=$free_percent"
  exit 1
fi
echo "disk_status=ok path=$path free_percent=$free_percent"
