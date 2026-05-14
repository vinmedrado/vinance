#!/usr/bin/env bash
set -euo pipefail

echo "== FinanceOS production config check =="
test -f .env.production || { echo "Missing .env.production. Copy .env.production.example first."; exit 1; }
docker compose -f docker-compose.production.yml config >/tmp/financeos-compose-config.yml
echo "Compose config OK"
echo "Run: docker compose -f docker-compose.production.yml up -d --build"
