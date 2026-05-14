#!/usr/bin/env bash
set -euo pipefail

test -f .env.production || cp .env.production.example .env.production
./scripts/deploy/check_production.sh
docker compose -f docker-compose.production.yml up -d --build
