"""Governed Intake/Profile preview API.

Execution requires explicit approval and fails closed unless its
persistent audit event is committed successfully.
"""

from fastapi import APIRouter, Depends, HTTPException
from .agent_audit_sink import AgentAuditStorageError
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .agent_pipeline import PipelineRequest, PipelineResult
from .database import get_db
from .agent_execution_service import execute_audited_intake_profile
from .models import User
from .security import Principal, Role, require_roles


INTAKE_PROFILE_EXECUTION_APPROVED = True


router = APIRouter(
    prefix="/api/v1/agents",
    tags=["AI Agent Preview"],
)


class PreviewAvailability(BaseModel):
    available: bool = False
    reason: str = "Persistent audit verification pending"


@router.get(
    "/intake-profile/availability",
    response_model=PreviewAvailability,
)
def preview_availability(
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
            detail="Account no longer active",
        )

    return PreviewAvailability(
        available=INTAKE_PROFILE_EXECUTION_APPROVED,
        reason=(
            "Intake/Profile execution approved; persistent audit required"
            if INTAKE_PROFILE_EXECUTION_APPROVED
            else "Intake/Profile execution not approved"
        ),
    )


@router.post(
    "/intake-profile/preview",
    response_model=PipelineResult,
)
def preview_intake_profile(
    _request: PipelineRequest,
    _principal: Principal = Depends(
        require_roles(
            Role.admin,
            Role.gis_operator,
            Role.ml_team,
        )
    ),
    db: Session = Depends(get_db),
):
    user = db.get(User, _principal.subject)

    if (
        user is None
        or not user.is_active
        or user.role != _principal.role.value
    ):
        raise HTTPException(
            status_code=401,
            detail="Account no longer active",
        )

    # Approval may be revoked independently of route registration.
    if not INTAKE_PROFILE_EXECUTION_APPROVED:
        raise HTTPException(
            status_code=503,
            detail="Intake/Profile preview awaits verified persistent auditing",
        )

    try:
        return execute_audited_intake_profile(
            db,
            _principal,
            _request,
        )
    except AgentAuditStorageError:
        raise HTTPException(
            status_code=503,
            detail="Persistent audit storage unavailable",
        )
