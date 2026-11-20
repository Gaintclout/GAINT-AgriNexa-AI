"""Create SCIM processing job records. Migration is not run automatically."""
from alembic import op
import sqlalchemy as sa

revision = "0003_scim_jobs"
down_revision = "0002_geography_hierarchy"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "scim_processing_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("parcel_id", sa.String(36), sa.ForeignKey("parcels.id"), nullable=False),
        sa.Column("scene_id", sa.String(200), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("parcel_id", "scene_id", "provider", name="uq_scim_job_parcel_scene_provider"),
        sa.CheckConstraint("status IN ('planned','queued','running','succeeded','failed','cancelled')", name="ck_scim_job_status"),
    )
    op.create_index("ix_scim_processing_jobs_parcel_id", "scim_processing_jobs", ["parcel_id"])

def downgrade():
    op.drop_index("ix_scim_processing_jobs_parcel_id", table_name="scim_processing_jobs")
    op.drop_table("scim_processing_jobs")
