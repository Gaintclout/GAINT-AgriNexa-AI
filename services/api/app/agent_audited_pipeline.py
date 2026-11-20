"""Audited internal pipeline with explicit event delivery.

No API exposure, persistence, or agent execution.
"""

from collections.abc import Callable
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .agent_audit import AgentAuditEvent, build_audit_event
from .agent_pipeline import (
    PipelineRequest,
    PipelineResult,
    prepare_parcel_profile,
)
from .security import Principal


AuditSink = Callable[[AgentAuditEvent], None]


def run_audited_pipeline(
    db: Session,
    principal: Principal,
    request: PipelineRequest,
    audit_sink: AuditSink,
) -> PipelineResult:
    """Require audit delivery before returning an authorized result."""

    correlation_id = str(uuid4())

    try:
        result = prepare_parcel_profile(db, principal, request)
    except HTTPException as exc:
        event = build_audit_event(
            principal,
            request.parcel_id,
            allowed=False,
            reason_code=f"HTTP_{exc.status_code}",
            correlation_id=correlation_id,
        )
        audit_sink(event)
        raise

    event = build_audit_event(
        principal,
        request.parcel_id,
        allowed=True,
        reason_code="AUTHORIZED",
        correlation_id=correlation_id,
    )

    audit_sink(event)
    if hasattr(result, "model_copy"):
        return result.model_copy(update={"correlation_id": correlation_id})
    return result
