
"""Isolated PostgreSQL audit-trigger behavior tests.

Requires AGRINEXA_AGENT_AUDIT_TEST_DATABASE_URL pointing to the dedicated,
disposable PostgreSQL audit database on local port 55432.

These tests exercise temporary trigger behavior, not Alembic migrations.
No connection is attempted unless explicitly configured.
"""

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError, DBAPIError


TEST_ENV = "AGRINEXA_AGENT_AUDIT_TEST_DATABASE_URL"
TEST_DATABASE = "agrinexa_agent_audit_test"
TEST_HOST = "127.0.0.1"
TEST_PORT = 55432


@pytest.fixture(scope="module")
def audit_engine():
    url = os.environ.get(TEST_ENV)
    if not url:
        pytest.skip("Dedicated agent audit test database not configured")

    try:
        parsed = make_url(url)
    except ArgumentError as exc:
        pytest.fail(f"Invalid audit test database URL: {exc}")

    if parsed.get_backend_name() != "postgresql":
        pytest.fail("Audit integration tests require PostgreSQL")
    if parsed.database != TEST_DATABASE:
        pytest.fail("Refusing unexpected audit database name")
    if parsed.host != TEST_HOST or parsed.port != TEST_PORT:
        pytest.fail("Audit tests require 127.0.0.1:55432")

    engine = create_engine(
        parsed,
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args={"connect_timeout": 3},
    )
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def protected_table(audit_engine):
    """Create temporary audit objects in a rolled-back transaction."""
    with audit_engine.connect() as connection:
        transaction = connection.begin()
        try:
            identity = connection.execute(
                text("SELECT current_database(), inet_server_port()")
            ).one()
            assert identity == (TEST_DATABASE, TEST_PORT)

            connection.execute(text("""
                CREATE TEMP TABLE agent_audit_guard_test (
                    id integer PRIMARY KEY,
                    event_name text NOT NULL
                ) ON COMMIT DROP
            """))
            connection.execute(text("""
                INSERT INTO agent_audit_guard_test
                VALUES (1, 'original')
            """))
            connection.execute(text("""
                CREATE FUNCTION pg_temp.reject_audit_change()
                RETURNS trigger
                LANGUAGE plpgsql
                AS $$
                BEGIN
                    RAISE EXCEPTION
                        'audit modification prohibited'
                        USING ERRCODE = '42501';
                END;
                $$
            """))
            connection.execute(text("""
                CREATE TRIGGER audit_guard_rows
                BEFORE UPDATE OR DELETE
                ON agent_audit_guard_test
                FOR EACH ROW
                EXECUTE FUNCTION pg_temp.reject_audit_change()
            """))
            connection.execute(text("""
                CREATE TRIGGER audit_guard_truncate
                BEFORE TRUNCATE
                ON agent_audit_guard_test
                FOR EACH STATEMENT
                EXECUTE FUNCTION pg_temp.reject_audit_change()
            """))
            yield connection
        finally:
            if transaction.is_active:
                transaction.rollback()


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE agent_audit_guard_test SET event_name='changed'",
        "DELETE FROM agent_audit_guard_test",
        "TRUNCATE agent_audit_guard_test",
    ],
)
def test_audit_mutation_rejected(protected_table, statement):
    # A SAVEPOINT isolates the expected PostgreSQL error.
    with pytest.raises(DBAPIError):
        with protected_table.begin_nested():
            protected_table.execute(text(statement))

    result = protected_table.execute(text("""
        SELECT event_name
        FROM agent_audit_guard_test
        WHERE id = 1
    """)).scalar_one()
    assert result == "original"


def test_audit_insert_allowed(protected_table):
    protected_table.execute(text("""
        INSERT INTO agent_audit_guard_test
        VALUES (2, 'new event')
    """))
    result = protected_table.execute(text("""
        SELECT count(*)
        FROM agent_audit_guard_test
    """)).scalar_one()
    assert result == 2
