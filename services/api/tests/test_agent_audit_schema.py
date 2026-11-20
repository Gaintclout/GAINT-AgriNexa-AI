"""Agent audit persistence schema contract tests."""

import ast
from pathlib import Path

from sqlalchemy import CheckConstraint, Index

from app.agent_audit_models import AgentAuditRecord
from app.database import Base


ROOT = Path(__file__).resolve().parents[1]

MIGRATION = (
    ROOT
    / "migrations"
    / "versions"
    / "0008_agent_audit_events.py"
)


def test_model_registered_in_metadata():
    assert "agent_audit_events" in Base.metadata.tables


def test_audit_table_has_expected_columns():
    table = AgentAuditRecord.__table__

    expected = {
        "id",
        "actor_id",
        "actor_role",
        "parcel_id",
            "subject_id",
            "correlation_id",
        "operation",
        "outcome",
        "reason_code",
        "created_at",
    }

    assert set(table.columns.keys()) == expected


def test_only_backward_compatible_subject_columns_are_nullable():
    table = AgentAuditRecord.__table__

    nullable = {column.name for column in table.columns if column.nullable}
    assert nullable == {"parcel_id", "subject_id", "correlation_id"}


def test_audit_timestamp_is_timezone_aware():
    column = AgentAuditRecord.__table__.c.created_at

    assert column.type.timezone is True


def test_outcome_constraint_present():
    constraints = [
        constraint
        for constraint in AgentAuditRecord.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    ]

    assert any(
        constraint.name == "ck_agent_audit_outcome"
        for constraint in constraints
    )


def test_required_indexes_present():
    indexes = {
        index.name
        for index in AgentAuditRecord.__table__.indexes
        if isinstance(index, Index)
    }

    assert "ix_agent_audit_actor_created" in indexes
    assert "ix_agent_audit_parcel_created" in indexes
    assert "ix_agent_audit_correlation" in indexes


def test_migration_revision_chain():
    tree = ast.parse(MIGRATION.read_text())

    values = {}

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue

        for target in node.targets:
            if isinstance(target, ast.Name):
                if target.id in {"revision", "down_revision"}:
                    values[target.id] = ast.literal_eval(node.value)

    assert values["revision"] == "0008_agent_audit_events"
    assert values["down_revision"] == "0007_farmer_parcel_ownership"


def test_migration_does_not_automatically_execute():
    source = MIGRATION.read_text()

    assert "def upgrade():" in source
    assert "def downgrade():" in source
    assert "op.create_table(" in source
    assert "op.execute(" not in source


def test_downgrade_requires_explicit_review():
    source = MIGRATION.read_text()

    assert "raise RuntimeError(" in source
    assert "data-retention procedure" in source
