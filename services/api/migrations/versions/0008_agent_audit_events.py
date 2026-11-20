"""Create dedicated agent audit event storage.

Revision ID: 0008_agent_audit_events
Revises: 0007_farmer_parcel_ownership
"""

from alembic import op
import sqlalchemy as sa


revision = "0008_agent_audit_events"
down_revision = "0007_farmer_parcel_ownership"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "agent_audit_events",
        sa.Column(
            "id",
            sa.String(36),
            primary_key=True,
        ),
        sa.Column(
            "actor_id",
            sa.String(36),
            nullable=False,
        ),
        sa.Column(
            "actor_role",
            sa.String(30),
            nullable=False,
        ),
        sa.Column(
            "parcel_id",
            sa.String(36),
            nullable=False,
        ),
        sa.Column(
            "operation",
            sa.String(40),
            nullable=False,
        ),
        sa.Column(
            "outcome",
            sa.String(20),
            nullable=False,
        ),
        sa.Column(
            "reason_code",
            sa.String(60),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.CheckConstraint(
            "outcome IN ('allowed', 'denied')",
            name="ck_agent_audit_outcome",
        ),
    )

    op.create_index(
        "ix_agent_audit_actor_created",
        "agent_audit_events",
        ["actor_id", "created_at"],
    )

    op.create_index(
        "ix_agent_audit_parcel_created",
        "agent_audit_events",
        ["parcel_id", "created_at"],
    )


def downgrade():
    # Audit history must not be silently destroyed.
    raise RuntimeError(
        "Agent audit table downgrade requires a "
        "separately approved data-retention procedure."
    )
