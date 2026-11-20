"""Extend agent audit governance and correlation.

Revision ID: 0012_agent_audit_governance
Revises: 0011_persistent_auth_sessions
"""

from alembic import op
import sqlalchemy as sa


revision = "0012_agent_audit_governance"
down_revision = "0011_persistent_auth_sessions"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "agent_audit_events",
        sa.Column("subject_id", sa.String(150), nullable=True),
    )
    op.add_column(
        "agent_audit_events",
        sa.Column("correlation_id", sa.String(36), nullable=True),
    )
    op.alter_column(
        "agent_audit_events",
        "parcel_id",
        existing_type=sa.String(36),
        nullable=True,
    )
    op.create_index(
        "ix_agent_audit_correlation",
        "agent_audit_events",
        ["correlation_id"],
    )


def downgrade():
    raise RuntimeError(
        "Removing audit governance columns requires explicit security "
        "and data-retention approval."
    )


def downgrade():
    raise RuntimeError(
        "Agent audit governance rollback requires explicit security "
        "and data-retention approval."
    )
    op.create_index(
        "ix_agent_audit_correlation",
        "agent_audit_events",
        ["correlation_id"],
    )


def downgrade():
    raise RuntimeError(
        "Agent audit governance rollback requires explicit security "
        "and data-retention approval."
    )
