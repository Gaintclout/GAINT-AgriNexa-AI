"""Add optional farmer ownership to parcels without changing existing records."""
from alembic import op
import sqlalchemy as sa

revision = "0007_farmer_parcel_ownership"
down_revision = "0006_field_verification"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("parcels", sa.Column("farmer_id", sa.String(36), nullable=True))
    op.create_foreign_key("fk_parcels_farmer", "parcels", "users", ["farmer_id"], ["id"])
    op.create_index("ix_parcels_farmer_id", "parcels", ["farmer_id"], unique=False)


def downgrade():
    op.drop_index("ix_parcels_farmer_id", table_name="parcels")
    op.drop_constraint("fk_parcels_farmer", "parcels", type_="foreignkey")
    op.drop_column("parcels", "farmer_id")
