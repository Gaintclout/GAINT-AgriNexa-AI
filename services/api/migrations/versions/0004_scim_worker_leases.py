"""Add durable SCIM worker lease metadata without enabling execution."""
from alembic import op
import sqlalchemy as sa

revision = "0004_scim_worker_leases"
down_revision = "0003_scim_jobs"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("scim_processing_jobs", sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("scim_processing_jobs", sa.Column("lease_owner", sa.String(128), nullable=True))
    op.add_column("scim_processing_jobs", sa.Column("lease_token", sa.String(36), nullable=True))
    op.add_column("scim_processing_jobs", sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint("ck_scim_job_attempt_count", "scim_processing_jobs",
                               "attempt_count >= 0 AND attempt_count <= 3")
    op.create_check_constraint("ck_scim_job_lease_consistency", "scim_processing_jobs",
                               "(lease_owner IS NULL AND lease_token IS NULL AND lease_expires_at IS NULL) OR "
                               "(lease_owner IS NOT NULL AND lease_token IS NOT NULL AND lease_expires_at IS NOT NULL)")

def downgrade():
    op.drop_constraint("ck_scim_job_lease_consistency", "scim_processing_jobs", type_="check")
    op.drop_constraint("ck_scim_job_attempt_count", "scim_processing_jobs", type_="check")
    op.drop_column("scim_processing_jobs", "lease_expires_at")
    op.drop_column("scim_processing_jobs", "lease_token")
    op.drop_column("scim_processing_jobs", "lease_owner")
    op.drop_column("scim_processing_jobs", "attempt_count")
