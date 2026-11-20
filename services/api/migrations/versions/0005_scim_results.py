"""Add durable SCIM processing results; migration is not automatic."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0005_scim_results"
down_revision = "0004_scim_worker_leases"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "scim_processing_results",
        sa.Column("job_id", sa.String(36),
                  sa.ForeignKey("scim_processing_jobs.id"), primary_key=True),
        sa.Column("summary", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

def downgrade():
    op.drop_table("scim_processing_results")
