#!/bin/sh
# Local/CI bootstrap only: creates the two application roles (spec D4, TEN-01/02).
# Grants and RLS arrive with M4; the app role is NOSUPERUSER NOBYPASSRLS from the start.
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    -v migrator_password="$SKIW_MIGRATOR_PASSWORD" \
    -v app_password="$SKIW_APP_PASSWORD" \
    -v db="$POSTGRES_DB" <<'SQL'
CREATE ROLE skiw_migrator LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE PASSWORD :'migrator_password';
CREATE ROLE skiw_app LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE PASSWORD :'app_password';
ALTER DATABASE :"db" OWNER TO skiw_migrator;
ALTER SCHEMA public OWNER TO skiw_migrator;
REVOKE ALL ON DATABASE :"db" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"db" TO skiw_app;
SQL
