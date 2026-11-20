"""Authenticated read-only government scheme guidance API."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .database import get_db
from .models import User
from .security import Principal, Role, require_roles
from .scheme_agent import (
    SchemeDataError,
    SchemeRequest,
    SchemeResult,
    generate_scheme_guidance,
)

router = APIRouter(
    prefix="/api/v1/agents/schemes",
    tags=["Government Scheme Agent"],
)

ALLOWED_ROLES = (
    Role.admin,
    Role.gis_operator,
    Role.ml_team,
)

@router.post("/screen", response_model=SchemeResult)
def screen_schemes(
    request: SchemeRequest,
    principal: Principal = Depends(require_roles(*ALLOWED_ROLES)),
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

    try:
        return generate_scheme_guidance(request)
    except SchemeDataError as exc:
        raise HTTPException(
            status_code=503,
            detail="Verified scheme catalogue temporarily unavailable",
        ) from exc
