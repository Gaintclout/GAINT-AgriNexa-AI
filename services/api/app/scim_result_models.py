"""Durable SCIM parcel summaries, fenced by their processing job."""
from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base

class ScimProcessingResult(Base):
    __tablename__ = "scim_processing_results"
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("scim_processing_jobs.id"), primary_key=True)
    summary: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc))
