
"""Governed AI Agent Registry for GAINT AgriNexa AI.

Provides authenticated agent discovery and reports configured
execution capabilities.

Intake/Profile execution is available only through its
dedicated, audited preview endpoint when explicitly approved.

Generic execution remains disabled for every agent.
Automatic learning and model training remain disabled.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from . import agent_preview_router
from .database import get_db
from .models import User
from .security import Principal, Role, require_roles


# --------------------------------------------------
# Router configuration
# --------------------------------------------------

router = APIRouter(
    prefix="/api/v1/agents",
    tags=["AI Agent Governance"],
)


# --------------------------------------------------
# Authorized roles
# --------------------------------------------------

AUTHORIZED_ROLES = (
    Role.admin,
    Role.gis_operator,
    Role.ml_team,
)


# --------------------------------------------------
# Registered agents
# --------------------------------------------------

AGENT_NAMES = (
    "INTAKE",
    "PROFILE",
    "WEATHER",
    "CROP_ADVISORY",
    "MARKET",
    "SCHEME",
    "ESCALATION",
    "LEARNING",
)

INTAKE_PROFILE_AGENTS = frozenset(
    ("INTAKE", "PROFILE")
)


# --------------------------------------------------
# Response model
# --------------------------------------------------

class AgentRecord(BaseModel):
    id: str
    status: str = "disabled"
    execution_enabled: bool = False
    learning_enabled: bool = False


# --------------------------------------------------
# Authentication and authorization
# --------------------------------------------------

def verified_principal(
    principal: Principal = Depends(
        require_roles(*AUTHORIZED_ROLES)
    ),
    db: Session = Depends(get_db),
) -> Principal:
    """Verify that the authenticated account is still active.

    The database role must match the authenticated principal.
    """

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

    return principal


# --------------------------------------------------
# Agent validation
# --------------------------------------------------

def normalize_agent_id(agent_id: str) -> str:
    """Normalize and validate an agent identifier."""

    name = agent_id.upper()

    if name not in AGENT_NAMES:
        raise HTTPException(
            status_code=404,
            detail="Agent not found",
        )

    return name


# --------------------------------------------------
# Agent capability resolution
# --------------------------------------------------

def get_agent_record(agent_id: str) -> AgentRecord:
    """Return the configured capability for a known agent.

    This reports approval configuration, not live health
    or database audit readiness.
    """

    name = normalize_agent_id(agent_id)

    intake_profile_approved = (
        agent_preview_router.INTAKE_PROFILE_EXECUTION_APPROVED
        is True
    )

    if (
        name in INTAKE_PROFILE_AGENTS
        and intake_profile_approved
    ):
        return AgentRecord(
            id=name,
            status="enabled",
            execution_enabled=True,
            learning_enabled=False,
        )

    return AgentRecord(
        id=name,
        status="disabled",
        execution_enabled=False,
        learning_enabled=False,
    )


# --------------------------------------------------
# List all registered agents
# --------------------------------------------------

@router.get(
    "",
    response_model=list[AgentRecord],
)
def list_agents(
    _principal: Principal = Depends(verified_principal),
) -> list[AgentRecord]:
    """List agents and their configured capabilities."""

    return [
        get_agent_record(name)
        for name in AGENT_NAMES
    ]


# --------------------------------------------------
# Get individual agent
# --------------------------------------------------

@router.get(
    "/{agent_id}",
    response_model=AgentRecord,
)
def get_agent(
    agent_id: str,
    _principal: Principal = Depends(verified_principal),
) -> AgentRecord:
    """Return the capability of one registered agent."""

    return get_agent_record(agent_id)


# --------------------------------------------------
# Generic execution - fail closed
# --------------------------------------------------

@router.post("/{agent_id}/execute")
def execute_agent(
    agent_id: str,
    _principal: Principal = Depends(verified_principal),
):
    """Reject generic agent execution.

    Approved Intake/Profile execution uses:

    POST /api/v1/agents/intake-profile/preview

    Other agent-specific routes are governed separately.
    """

    normalize_agent_id(agent_id)

    raise HTTPException(
        status_code=403,
        detail="Agent execution is disabled",
    )
