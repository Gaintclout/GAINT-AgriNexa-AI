"""Durable SCIM job metadata; no automatic migration or worker execution."""
from datetime import datetime, timezone
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base
from .models import uid

class ScimProcessingJob(Base):
    __tablename__ = "scim_processing_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    parcel_id: Mapped[str] = mapped_column(String(36), ForeignKey("parcels.id"), nullable=False, index=True)
    scene_id: Mapped[str] = mapped_column(String(200), nullable=False)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="planned")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    lease_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_token: Mapped[str | None] = mapped_column(String(36), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (
        CheckConstraint("attempt_count >= 0 AND attempt_count <= 3", name="ck_scim_job_attempt_count"),
        CheckConstraint("(lease_owner IS NULL AND lease_token IS NULL AND lease_expires_at IS NULL) OR (lease_owner IS NOT NULL AND lease_token IS NOT NULL AND lease_expires_at IS NOT NULL)", name="ck_scim_job_lease_consistency"),
        UniqueConstraint("parcel_id", "scene_id", "provider", name="uq_scim_job_parcel_scene_provider"),
        CheckConstraint("status IN ('planned','queued','running','succeeded','failed','cancelled')", name="ck_scim_job_status"),
    )
