"""Protect agent audit history against UPDATE and DELETE.

Revision ID: 0009_agent_audit_append_only
Revises: 0008_agent_audit_events

This migration must not be applied automatically.
"""

from alembic import op

revision = "0009_agent_audit_append_only"
down_revision = "0008_agent_audit_events"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE OR REPLACE FUNCTION
        reject_agent_audit_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION
                'agent audit history is append-only'
                USING ERRCODE = '42501';
        END;
        $$;
    """)

    op.execute("""
        CREATE TRIGGER trg_agent_audit_append_only
        BEFORE UPDATE OR DELETE
        ON agent_audit_events
        FOR EACH ROW
        EXECUTE FUNCTION reject_agent_audit_mutation();
    """)


def downgrade():
    raise RuntimeError(
        "Removing agent audit protection requires "
        "explicit security and data-retention approval."
    )
