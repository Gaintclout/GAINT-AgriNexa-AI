"""Structured internal agent audit events; no persistence."""

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict

from .security import Principal


class AgentAuditEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp: datetime
    actor_id: str
    actor_role: str
    parcel_id: str | None = None
    subject_id: str | None = None
    correlation_id: str
    operation: Literal[
        "INTAKE_PROFILE",
        "ESCALATION_REVIEW",
        "LEARNING_REVIEW",
    ]
    outcome: Literal["allowed", "denied"]
    reason_code: str


def build_audit_event(
    principal: Principal,
    parcel_id: str,
    *,
    allowed: bool,
    reason_code: str,
    correlation_id: str | None = None,
) -> AgentAuditEvent:
    """Construct a minimal event without logging sensitive payloads."""

    return AgentAuditEvent(
        timestamp=datetime.now(timezone.utc),
        actor_id=principal.subject,
        actor_role=principal.role.value,
        parcel_id=parcel_id,
        correlation_id=correlation_id or str(uuid4()),
        operation="INTAKE_PROFILE",
        outcome="allowed" if allowed else "denied",
        reason_code=reason_code,
    )


def build_review_audit_event(
    principal: Principal,
    subject_id: str,
    operation: Literal["ESCALATION_REVIEW", "LEARNING_REVIEW"],
    *,
    correlation_id: str,
) -> AgentAuditEvent:
    """Build a minimal review audit without persisting request content."""

    return AgentAuditEvent(
        timestamp=datetime.now(timezone.utc),
        actor_id=principal.subject,
        actor_role=principal.role.value,
        subject_id=subject_id,
        correlation_id=correlation_id,
        operation=operation,
        outcome="allowed",
        reason_code="AUTHORIZED",
    )
