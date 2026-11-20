"""Persistent agent audit schema; no automatic migrations."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class AgentAuditRecord(Base):
    __tablename__ = "agent_audit_events"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    actor_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
    )

    actor_role: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    parcel_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
    )

    subject_id: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    correlation_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
    )

    operation: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )

    outcome: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    reason_code: Mapped[str] = mapped_column(
        String(60),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        CheckConstraint(
            "outcome IN ('allowed', 'denied')",
            name="ck_agent_audit_outcome",
        ),
        Index(
            "ix_agent_audit_actor_created",
            "actor_id",
            "created_at",
        ),
        Index(
            "ix_agent_audit_parcel_created",
            "parcel_id",
            "created_at",
        ),
        Index(
            "ix_agent_audit_correlation",
            "correlation_id",
        ),
    )
