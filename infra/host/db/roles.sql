-- The closed role set (spec D4, §8.4 H6; TEN-01, TEN-02, TEN-10). Idempotent: creates a missing
-- role, then sets every attribute, so a second run changes nothing. It holds no password:
-- bootstrap-db sets those from /etc/skiw/secrets (hosts), docker/postgres/10-roles.sh from .env
-- (local, CI). Run as the superuser `postgres` with psql variable `db` = the application database.
\set ON_ERROR_STOP on
BEGIN;

SELECT format('CREATE ROLE %I', name)
FROM unnest(ARRAY['skiw_migrator', 'skiw_app', 'skiw_readonly', 'skiw_backup',
                  'skiw_tenant_guard', 'skiw_auth_lookup']) AS name
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = name)
\gexec

-- Owns the schema; only `migrate` uses it (TEN-01).
ALTER ROLE skiw_migrator LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION;
-- The only role of web and worker: no bypass, no CREATE, member of no role (TEN-02).
ALTER ROLE skiw_app LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION;
-- Reporting and break-glass, socket-only once pg_hba.conf lands (M1e-2); its grants arrive with its first use.
ALTER ROLE skiw_readonly LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION;
-- Only the `backup` ops service (H6); the network limit is pg_hba.conf (M1e-2).
ALTER ROLE skiw_backup LOGIN NOSUPERUSER BYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION
    CONNECTION LIMIT 2;
ALTER ROLE skiw_backup SET default_transaction_read_only = on;
GRANT pg_read_all_data TO skiw_backup;
-- NOLOGIN function owners (D18, §4.1): only skiw_auth_lookup bypasses RLS, for the pre-tenant lookups.
ALTER ROLE skiw_tenant_guard NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION;
ALTER ROLE skiw_auth_lookup NOLOGIN NOSUPERUSER BYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION;

ALTER DATABASE :"db" OWNER TO skiw_migrator;
ALTER SCHEMA public OWNER TO skiw_migrator;
REVOKE ALL ON DATABASE :"db" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"db" TO skiw_app, skiw_readonly, skiw_backup;

COMMIT;
