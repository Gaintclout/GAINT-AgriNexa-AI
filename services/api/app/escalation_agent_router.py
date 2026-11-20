"""Authenticated, read-only escalation screening endpoint."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .database import get_db
from .models import User
from .security import Principal, Role, require_roles
from .escalation_agent import (
    EscalationRequest,
    EscalationResult,
)
from .agent_audit_sink import AgentAuditStorageError
from .agent_review_audit_service import execute_audited_escalation_review

router = APIRouter(
    prefix="/api/v1/agents/escalation",
    tags=["Agent Escalation"],
)


@router.post(
    "/screen",
    response_model=EscalationResult,
)
def screen_escalation(
    request: EscalationRequest,
    principal: Principal = Depends(
        require_roles(
            Role.admin,
            Role.gis_operator,
            Role.ml_team,
        )
    ),
    db: Session = Depends(get_db),
):
    user = db.get(User, principal.subject)

    if (
        user is None
        or not user.is_active
        or user.role != principal.role.value
    ):
        raise HTTPException(
            status_code=401,
            detail="Active authorized account required",
        )

    try:
        return execute_audited_escalation_review(principal, request)
    except AgentAuditStorageError as exc:
        raise HTTPException(
            status_code=503,
            detail="Persistent audit storage unavailable",
        ) from exc
