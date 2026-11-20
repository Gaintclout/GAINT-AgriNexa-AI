"""Contract tests for the agent audit TRUNCATE guard."""

import ast
from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "versions"
    / "0010_agent_audit_truncate_guard.py"
)


def source():
    return MIGRATION.read_text()


def test_migration_syntax():
    ast.parse(source())


def test_revision_chain():
    tree = ast.parse(source())
    values = {}

    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    if target.id in {"revision", "down_revision"}:
                        values[target.id] = ast.literal_eval(node.value)

    assert values["revision"] == "0010_agent_audit_truncate_guard"
    assert values["down_revision"] == "0009_agent_audit_append_only"


def test_truncate_guard_present():
    sql = source().upper()

    assert "BEFORE TRUNCATE" in sql
    assert "AGENT_AUDIT_EVENTS" in sql
    assert "RAISE EXCEPTION" in sql


def test_statement_level_trigger():
    assert "FOR EACH STATEMENT" in source().upper()


def test_downgrade_requires_approval():
    assert "raise RuntimeError(" in source()


def test_no_destructive_downgrade():
    sql = source().upper()

    assert "OP.DROP_TABLE(" not in sql
    assert "OP.DROP_COLUMN(" not in sql
