"""Initial users, villages and PostGIS parcel schema."""
from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry

revision = "0001_identity_geo"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.create_table("users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(30), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False))
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table("villages",
        sa.Column("code", sa.String(100), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("district_code", sa.String(100), nullable=False))
    op.create_table("parcels",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("external_id", sa.String(100), nullable=False, unique=True),
        sa.Column("village_code", sa.String(100), sa.ForeignKey("villages.code"), nullable=False),
        sa.Column("area_hectares", sa.Numeric(12, 4), nullable=False),
        sa.Column("geom", Geometry(geometry_type="MULTIPOLYGON", srid=4326, spatial_index=False), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("area_hectares > 0", name="ck_parcels_positive_area"))
    op.execute("CREATE INDEX ix_parcels_geom ON parcels USING GIST (geom)")

def downgrade():
    op.drop_index("ix_parcels_geom", table_name="parcels")
    op.drop_table("parcels")
    op.drop_table("villages")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
