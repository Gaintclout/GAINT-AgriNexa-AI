"""M15 persistent refresh sessions; explicit migration only."""
from alembic import op
import sqlalchemy as sa
revision = "0011_persistent_auth_sessions"
down_revision = "0010_agent_audit_truncate_guard"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "auth_refresh_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_auth_refresh_sessions_user_id", "auth_refresh_sessions", ["user_id"])
    op.create_index("ix_auth_refresh_sessions_expires_at", "auth_refresh_sessions", ["expires_at"])

def downgrade():
    raise RuntimeError("M15 session table rollback requires explicit security approval")
