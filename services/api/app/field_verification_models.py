"""Field evidence persistence. Imported by Alembic env.py."""
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import DateTime, ForeignKey, Index, String, Float, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base


def now():
    return datetime.now(timezone.utc)


class FieldEvidence(Base):
    __tablename__ = 'field_evidence'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    verifier_id: Mapped[str] = mapped_column(ForeignKey('users.id'), nullable=False, index=True)
    parcel_id: Mapped[str] = mapped_column(ForeignKey('parcels.id'), nullable=False, index=True)
    client_record_id: Mapped[str] = mapped_column(String(100), nullable=False)
    observation: Mapped[str] = mapped_column(Text, nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default='submitted')
    photo_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    photo_content_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    photo_bytes: Mapped[int | None] = mapped_column(nullable=True)
    reviewer_id: Mapped[str | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=now)
    __table_args__ = (UniqueConstraint('verifier_id', 'client_record_id', name='uq_field_evidence_client_record'), Index('ix_field_evidence_status_created', 'status', 'created_at'))


class FieldEvidenceAudit(Base):
    __tablename__ = 'field_evidence_audit'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    evidence_id: Mapped[str] = mapped_column(ForeignKey('field_evidence.id'), nullable=False, index=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey('users.id'), nullable=False)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=now)
