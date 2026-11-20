-- REVIEW ONLY. NOT EXECUTED.
-- GAINT AgriNexa AI: restricted runtime access to agrinexa_uat_test.
-- Requires independent DBA review of schema, ownership, PUBLIC grants,
-- role memberships, table/sequence permissions, and database privileges.
-- This is a psql-oriented procedure, NOT an automated migration.
-- Never run against the application database agrinexa.
-- Note: PostgreSQL grants CONNECT to PUBLIC by default. The checks below
-- report effective access; they do not revoke PUBLIC access elsewhere.

\set ON_ERROR_STOP on

-- Stop before any role creation if connected to the wrong database,
-- the role already exists, or the migration history table is absent.
DO $guard$
BEGIN
    IF current_database() <> 'agrinexa_uat_test' THEN
        RAISE EXCEPTION 'Refusing runtime role procedure outside agrinexa_uat_test';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
        WHERE rolname = 'agrinexa_uat_runtime'
    ) THEN
        RAISE EXCEPTION 'agrinexa_uat_runtime already exists; stop and review manually';
    END IF;
    IF to_regclass('public.alembic_version') IS NULL THEN
        RAISE EXCEPTION 'Expected public.alembic_version is missing';
    END IF;
END
$guard$;

-- Create a new, initially non-login, non-privileged role.
-- Never modify an existing role automatically.
CREATE ROLE agrinexa_uat_runtime WITH
    NOLOGIN
    NOSUPERUSER
    NOCREATEDB
    NOCREATEROLE
    NOREPLICATION
    NOBYPASSRLS
    NOINHERIT;

-- Explicitly permit only this UAT database and the public schema.
-- NOTE: Other database CONNECT rights may still be inherited from PUBLIC.
GRANT CONNECT ON DATABASE agrinexa_uat_test TO agrinexa_uat_runtime;
GRANT USAGE ON SCHEMA public TO agrinexa_uat_runtime;

-- Read-only baseline. Add verified table-specific DML grants in a
-- separate reviewed change if the UAT runtime needs to write records.
GRANT SELECT ON ALL TABLES IN SCHEMA public TO agrinexa_uat_runtime;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO agrinexa_uat_runtime;
REVOKE INSERT, UPDATE, DELETE ON TABLE public.alembic_version
    FROM agrinexa_uat_runtime;

-- Review effective privileges, including those from PUBLIC.
SELECT has_database_privilege(
    'agrinexa_uat_runtime', 'agrinexa_uat_test', 'CONNECT'
) AS can_connect_uat;
SELECT has_schema_privilege(
    'agrinexa_uat_runtime', 'public', 'USAGE'
) AS can_use_public;
SELECT has_table_privilege(
    'agrinexa_uat_runtime', 'public.alembic_version', 'SELECT'
) AS can_read_revision;
SELECT c.oid::regclass AS sequence_name,
       has_sequence_privilege(
           'agrinexa_uat_runtime', c.oid, 'USAGE'
       ) AS can_use_sequence
FROM pg_catalog.pg_class AS c
JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind = 'S';

-- The following query MUST be reviewed for any true result.
-- A true result means effective CONNECT outside the intended UAT DB.
SELECT datname,
       has_database_privilege(
           'agrinexa_uat_runtime', datname, 'CONNECT'
       ) AS can_connect
FROM pg_catalog.pg_database
WHERE datname <> 'agrinexa_uat_test';

-- Do not enable LOGIN until an administrator has independently verified
-- no unexpected database access, role membership, or write permissions.
-- This procedure is review-only; do not execute without approval.
\password agrinexa_uat_runtime
ALTER ROLE agrinexa_uat_runtime LOGIN;
