#!/bin/bash
set -e

IFS=',' read -ra DBS <<< "$POSTGRES_MULTIPLE_DATABASES"

for db in "${DBS[@]}"; do
  echo "Creating database: $db"
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<EOF
SELECT 'CREATE DATABASE $db'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$db')\gexec
GRANT ALL PRIVILEGES ON DATABASE $db TO $POSTGRES_USER;
EOF
done
