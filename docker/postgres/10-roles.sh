#!/bin/sh
# Local/CI bootstrap only: the closed role set from infra/host/db/roles.sql, the same file that
# bootstrap-db applies on the hosts (spec D4, §8.4 H6), then the two local login passwords from
# .env. psql reads them with \getenv, so they are not in its argv. skiw_readonly and skiw_backup
# get no password locally, so they cannot log in. Grants and RLS arrive with M4.
set -eu
psql -X -q -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    -v db="$POSTGRES_DB" -f /skiw/roles.sql
psql -X -q -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
\getenv migrator_password SKIW_MIGRATOR_PASSWORD
\getenv app_password SKIW_APP_PASSWORD
ALTER ROLE skiw_migrator PASSWORD :'migrator_password';
ALTER ROLE skiw_app PASSWORD :'app_password';
SQL
