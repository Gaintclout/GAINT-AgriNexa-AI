"""Field verification evidence and audit.

IMPORTANT: Confirm down_revision matches revision in 0005_scim_results.py.
"""
from alembic import op
import sqlalchemy as sa

revision = '0006_field_verification'
down_revision = '0005_scim_results'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('field_evidence',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('verifier_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('parcel_id', sa.String(36), sa.ForeignKey('parcels.id'), nullable=False),
        sa.Column('client_record_id', sa.String(100), nullable=False),
        sa.Column('observation', sa.Text(), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('captured_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(30), nullable=False),
        sa.Column('photo_sha256', sa.String(64), nullable=True),
        sa.Column('photo_content_type', sa.String(30), nullable=True),
        sa.Column('photo_bytes', sa.Integer(), nullable=True),
        sa.Column('reviewer_id', sa.String(36), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('review_note', sa.Text(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('verifier_id', 'client_record_id', name='uq_field_evidence_client_record'),
        sa.CheckConstraint('latitude >= -90 AND latitude <= 90', name='ck_field_evidence_latitude'),
        sa.CheckConstraint('longitude >= -180 AND longitude <= 180', name='ck_field_evidence_longitude'),
    )
    op.create_index('ix_field_evidence_verifier_id', 'field_evidence', ['verifier_id'])
    op.create_index('ix_field_evidence_parcel_id', 'field_evidence', ['parcel_id'])
    op.create_index('ix_field_evidence_status_created', 'field_evidence', ['status', 'created_at'])
    op.create_table('field_evidence_audit',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('evidence_id', sa.String(36), sa.ForeignKey('field_evidence.id'), nullable=False),
        sa.Column('actor_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('action', sa.String(30), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_field_evidence_audit_evidence_id', 'field_evidence_audit', ['evidence_id'])


def downgrade():
    op.drop_index('ix_field_evidence_audit_evidence_id', table_name='field_evidence_audit')
    op.drop_table('field_evidence_audit')
    op.drop_index('ix_field_evidence_status_created', table_name='field_evidence')
    op.drop_index('ix_field_evidence_parcel_id', table_name='field_evidence')
    op.drop_index('ix_field_evidence_verifier_id', table_name='field_evidence')
    op.drop_table('field_evidence')
