"""Contract tests for append-only agent audit migration."""

import ast
from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "versions"
    / "0009_agent_audit_append_only.py"
)


def source():
    return MIGRATION.read_text()


def test_migration_python_syntax():
    ast.parse(source())


def test_revision_chain():
    tree = ast.parse(source())
    assignments = {}

    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    if target.id in {
                        "revision",
                        "down_revision",
                    }:
                        assignments[target.id] = ast.literal_eval(
                            node.value
                        )

    assert assignments["revision"] == (
        "0009_agent_audit_append_only"
    )
    assert assignments["down_revision"] == (
        "0008_agent_audit_events"
    )


def test_update_and_delete_blocked():
    sql = source().upper()

    assert "BEFORE UPDATE OR DELETE" in sql
    assert "AGENT_AUDIT_EVENTS" in sql
    assert "RAISE EXCEPTION" in sql


def test_trigger_is_row_level():
    assert "FOR EACH ROW" in source().upper()


def test_downgrade_requires_approval():
    assert "raise RuntimeError(" in source()


def test_no_schema_drop():
    sql = source().upper()

    assert "DROP TABLE" not in sql
    assert "TRUNCATE" not in sql
