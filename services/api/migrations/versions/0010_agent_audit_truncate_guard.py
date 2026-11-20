"""Reject TRUNCATE of agent audit history.

Revision ID: 0010_agent_audit_truncate_guard
Revises: 0009_agent_audit_append_only

This migration must not be applied automatically.
"""

from alembic import op

revision = "0010_agent_audit_truncate_guard"
down_revision = "0009_agent_audit_append_only"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE OR REPLACE FUNCTION
        reject_agent_audit_truncate()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION
                'agent audit history cannot be truncated'
                USING ERRCODE = '42501';
        END;
        $$;
    """)

    op.execute("""
        CREATE TRIGGER trg_agent_audit_no_truncate
        BEFORE TRUNCATE
        ON agent_audit_events
        FOR EACH STATEMENT
        EXECUTE FUNCTION reject_agent_audit_truncate();
    """)


def downgrade():
    raise RuntimeError(
        "Removing agent audit TRUNCATE protection requires "
        "explicit security and data-retention approval."
    )
