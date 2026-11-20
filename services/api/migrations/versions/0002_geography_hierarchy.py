"""Add state/district/mandal master tables and optional village mandal linkage."""
from alembic import op
import sqlalchemy as sa

revision = "0002_geography_hierarchy"
down_revision = "0001_identity_geo"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("states",
        sa.Column("code", sa.String(100), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False))
    op.create_table("districts",
        sa.Column("code", sa.String(100), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("state_code", sa.String(100), sa.ForeignKey("states.code"), nullable=False))
    op.create_table("mandals",
        sa.Column("code", sa.String(100), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("district_code", sa.String(100), sa.ForeignKey("districts.code"), nullable=False))
    op.add_column("villages", sa.Column("mandal_code", sa.String(100), nullable=True))
    op.create_foreign_key("fk_villages_mandal", "villages", "mandals", ["mandal_code"], ["code"])
    op.create_index("ix_districts_state_code", "districts", ["state_code"])
    op.create_index("ix_mandals_district_code", "mandals", ["district_code"])
    op.create_index("ix_villages_mandal_code", "villages", ["mandal_code"])

def downgrade():
    op.drop_index("ix_villages_mandal_code", table_name="villages")
    op.drop_index("ix_mandals_district_code", table_name="mandals")
    op.drop_index("ix_districts_state_code", table_name="districts")
    op.drop_constraint("fk_villages_mandal", "villages", type_="foreignkey")
    op.drop_column("villages", "mandal_code")
    op.drop_table("mandals")
    op.drop_table("districts")
    op.drop_table("states")
