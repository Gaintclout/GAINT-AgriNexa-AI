"""Offline safety contracts for the audit migration integration harness."""

import ast
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url

TESTS = Path(__file__).resolve().parent
MIGRATIONS = TESTS.parent / "migrations" / "versions"

EXPECTED_DB = "agrinexa_agent_audit_test"
EXPECTED_PORT = 55432


def validate_audit_test_url(raw_url):
    url = make_url(raw_url)

    if url.get_backend_name() != "postgresql":
        raise ValueError("PostgreSQL required")

    if url.database != EXPECTED_DB:
        raise ValueError("Unexpected database")

    if url.host != "127.0.0.1":
        raise ValueError("Loopback IPv4 required")

    if url.port != EXPECTED_PORT:
        raise ValueError("Unexpected port")

    return True


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://tester@127.0.0.1:55432/agrinexa_agent_audit_test",
    ],
)
def test_expected_disposable_url(url):
    assert validate_audit_test_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://tester@127.0.0.1:5432/agrinexa_agent_audit_test",
        "postgresql+psycopg://tester@localhost:55432/agrinexa_agent_audit_test",
        "postgresql+psycopg://tester@127.0.0.1:55432/agrinexa",
        "postgresql+psycopg://tester@127.0.0.1:55432/agrinexa_test",
        "sqlite:///audit.db",
    ],
)
def test_unsafe_database_urls_rejected(url):
    with pytest.raises(ValueError):
        validate_audit_test_url(url)


def test_live_harness_uses_explicit_database_opt_in():
    source = (
        TESTS / "test_agent_audit_migrations_live.py"
    ).read_text()

    assert "AGRINEXA_AGENT_AUDIT_TEST_DATABASE_URL" in source
    assert "127.0.0.1" in source
    assert "55432" in source
    assert "transaction.rollback()" in source


@pytest.mark.parametrize(
    "filename",
    [
        "0008_agent_audit_events.py",
        "0009_agent_audit_append_only.py",
        "0010_agent_audit_truncate_guard.py",
        "0012_agent_audit_governance.py",
    ],
)
def test_audit_migration_syntax(filename):
    ast.parse((MIGRATIONS / filename).read_text())


def test_audit_migrations_do_not_change_existing_tables():
    sources = "\n".join(
        (MIGRATIONS / filename).read_text().lower()
        for filename in (
            "0008_agent_audit_events.py",
            "0009_agent_audit_append_only.py",
            "0010_agent_audit_truncate_guard.py",
            "0012_agent_audit_governance.py",
        )
    )

    assert "drop table" not in sources
    assert "alter table users" not in sources
    assert "alter table parcels" not in sources
