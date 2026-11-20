-- REVIEW ONLY. NOT EXECUTED.
-- GAINT AgriNexa AI: isolated disposable PostGIS live-test runner.
-- Execute manually in psql only after independent DBA review.
-- Required database marker: agrinexa-disposable-live-tests.
-- Stop if disposable test database contains application records.

\set ON_ERROR_STOP on

DO $guard$
DECLARE
    marker text;
    app_rows bigint;
BEGIN
    IF current_database() <> 'agrinexa_test' THEN
        RAISE EXCEPTION 'Refusing runner role procedure outside agrinexa_test';
    END IF;
    SELECT shobj_description(oid, 'pg_database') INTO marker
    FROM pg_catalog.pg_database WHERE datname = current_database();
    IF marker IS DISTINCT FROM 'agrinexa-disposable-live-tests' THEN
        RAISE EXCEPTION 'Disposable database marker is missing or incorrect';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM public.alembic_version
                   WHERE version_num = '0007_farmer_parcel_ownership') THEN
        RAISE EXCEPTION 'Required migration is not present';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_extension WHERE extname = 'postgis') THEN
        RAISE EXCEPTION 'PostGIS is not installed';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'agrinexa_uat_test_runner') THEN
        RAISE EXCEPTION 'Runner role already exists; stop for review';
    END IF;
    -- Inspect actual tables and confirm absence of real application records
    -- before approving any write-capable runner role.
END
$guard$;

CREATE ROLE agrinexa_uat_test_runner NOLOGIN NOINHERIT;
GRANT CONNECT ON DATABASE agrinexa_test TO agrinexa_uat_test_runner;
GRANT USAGE ON SCHEMA public TO agrinexa_uat_test_runner;
GRANT SELECT ON TABLE public.alembic_version TO agrinexa_uat_test_runner;

-- Fixture-scoped permissions for known test tables. Verify table inventory first.
GRANT SELECT, INSERT, DELETE ON TABLE public.states TO agrinexa_uat_test_runner;
-- Review and enumerate the specific other test tables requiring UPDATE;
-- avoid schema-wide write permissions. Example syntax only:
-- GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.test_fixture_table TO agrinexa_uat_test_runner;

-- Confirm PostGIS function EXECUTE rights with actual installed signatures.
SELECT has_function_privilege('agrinexa_uat_test_runner', 'st_asgeojson(geometry)', 'EXECUTE');
-- st_geomfromgeojson, st_geomfromtext, st_intersects, st_isvalid,
-- st_makeenvelope, st_multi, st_setsrid must also be checked by signature.

-- Detect unintended access or role membership.
SELECT pg_has_role('agrinexa_uat_runtime', 'agrinexa_uat_test_runner', 'MEMBER');
SELECT pg_has_role('agrinexa_uat_test_runner', 'agrinexa_uat_runtime', 'MEMBER');
SELECT has_database_privilege('agrinexa_uat_runtime', 'agrinexa', 'CONNECT');
SELECT has_database_privilege('agrinexa_uat_test_runner', 'agrinexa', 'CONNECT');
SELECT has_database_privilege('agrinexa_uat_runtime', 'agrinexa_test', 'CONNECT');
SELECT has_database_privilege('agrinexa_uat_test_runner', 'agrinexa_uat_test', 'CONNECT');

-- Interactive password must be set before login is enabled.
\password agrinexa_uat_test_runner
ALTER ROLE agrinexa_uat_test_runner LOGIN;
