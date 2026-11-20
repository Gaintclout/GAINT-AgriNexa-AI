"""Real audit migration tests on a disposable local PostgreSQL instance.

No database access unless explicitly configured.
The test schema and all its objects are transaction-scoped.
"""

import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError


TEST_ENV = "AGRINEXA_AGENT_AUDIT_TEST_DATABASE_URL"
TEST_DATABASE = "agrinexa_agent_audit_test"
TEST_PORT = 55432

MIGRATION_DIR = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "versions"
)

MIGRATIONS = (
    "0008_agent_audit_events.py",
    "0009_agent_audit_append_only.py",
    "0010_agent_audit_truncate_guard.py",
    "0012_agent_audit_governance.py",
)


def load_migration(filename):
    path = MIGRATION_DIR / filename
    spec = importlib.util.spec_from_file_location(
        "audit_test_" + filename.removesuffix(".py"),
        path,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def audit_engine():
    url = os.getenv(TEST_ENV)

    if not url:
        pytest.skip("Dedicated audit test database not configured")

    parsed = make_url(url)

    if parsed.get_backend_name() != "postgresql":
        pytest.fail("PostgreSQL required")

    if parsed.database != TEST_DATABASE:
        pytest.fail("Unexpected database name")

    if parsed.port != TEST_PORT:
        pytest.fail("Unexpected PostgreSQL port")

    if parsed.host != "127.0.0.1":
        pytest.fail("Only IPv4 loopback is allowed")

    engine = create_engine(
        url,
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args={"connect_timeout": 3},
    )

    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def audit_database(audit_engine):
    schema = "audit_test_" + uuid4().hex[:12]

    with audit_engine.connect() as connection:
        transaction = connection.begin()

        try:
            identity = connection.execute(text("""
                SELECT current_database(),
                       inet_server_port()
            """)).one()

            assert identity[0] == TEST_DATABASE
            assert identity[1] == TEST_PORT

            connection.execute(
                text(f'CREATE SCHEMA "{schema}"')
            )

            connection.execute(
                text(f'SET LOCAL search_path TO "{schema}"')
            )

            current_schema = connection.execute(
                text("SELECT current_schema()")
            ).scalar_one()

            assert current_schema == schema

            context = MigrationContext.configure(
                connection,
                opts={
                    "version_table_schema": schema,
                    "transactional_ddl": True,
                },
            )

            for filename in MIGRATIONS:
                migration = load_migration(filename)

                with Operations.context(context):
                    migration.upgrade()

            table_schema = connection.execute(text("""
                SELECT table_schema
                FROM information_schema.tables
                WHERE table_name = 'agent_audit_events'
                  AND table_schema = :schema
            """), {"schema": schema}).scalar_one()

            assert table_schema == schema

            yield connection

        finally:
            transaction.rollback()


def test_actual_audit_migration_schema(audit_database):
    count = audit_database.execute(text("""
        SELECT count(*)
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'agent_audit_events'
    """)).scalar_one()

    assert count == 10


def test_governance_columns_and_existing_guard_survive(audit_database):
    columns = dict(audit_database.execute(text("""
        SELECT column_name, is_nullable
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'agent_audit_events'
          AND column_name IN ('parcel_id', 'subject_id', 'correlation_id')
    """)).all())
    assert columns == {
        "parcel_id": "YES",
        "subject_id": "YES",
        "correlation_id": "YES",
    }

    audit_database.execute(text("""
        INSERT INTO agent_audit_events (
            id, actor_id, actor_role, parcel_id, subject_id,
            correlation_id, operation, outcome, reason_code, created_at
        ) VALUES (
            'review-event', 'actor-1', 'admin', NULL, 'CASE-18',
            '00000000-0000-4000-8000-000000000018',
            'ESCALATION_REVIEW', 'allowed', 'AUTHORIZED', CURRENT_TIMESTAMP
        )
    """))
    assert audit_database.execute(text("""
        SELECT subject_id FROM agent_audit_events WHERE id='review-event'
    """)).scalar_one() == "CASE-18"


def test_actual_audit_insert(audit_database):
    audit_database.execute(text("""
        INSERT INTO agent_audit_events (
            id, actor_id, actor_role, parcel_id,
            operation, outcome, reason_code, created_at
        )
        VALUES (
            'event-1', 'actor-1', 'farmer', 'parcel-1',
            'INTAKE_PROFILE', 'allowed',
            'AUTHORIZED', CURRENT_TIMESTAMP
        )
    """))

    result = audit_database.execute(text("""
        SELECT outcome FROM agent_audit_events
        WHERE id = 'event-1'
    """)).scalar_one()

    assert result == "allowed"


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE agent_audit_events SET outcome='denied'",
        "DELETE FROM agent_audit_events",
        "TRUNCATE agent_audit_events",
    ],
)
def test_actual_audit_mutations_rejected(
    audit_database,
    statement,
):
    audit_database.execute(text("""
        INSERT INTO agent_audit_events (
            id, actor_id, actor_role, parcel_id,
            operation, outcome, reason_code, created_at
        )
        VALUES (
            'event-2', 'actor-2', 'farmer', 'parcel-2',
            'INTAKE_PROFILE', 'allowed',
            'AUTHORIZED', CURRENT_TIMESTAMP
        )
    """))

    with pytest.raises(DBAPIError):
        with audit_database.begin_nested():
            audit_database.execute(text(statement))

    count = audit_database.execute(text("""
        SELECT count(*)
        FROM agent_audit_events
        WHERE id = 'event-2'
    """)).scalar_one()

    assert count == 1
