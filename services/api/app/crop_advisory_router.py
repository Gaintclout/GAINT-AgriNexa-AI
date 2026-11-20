"""Authenticated crop advisory API with active-account checks."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .crop_advisory_agent import (
    CropAdvisoryRequest,
    CropAdvisoryResult,
    generate_crop_advisory,
)
from .database import get_db
from .models import User
from .security import Principal, Role, require_roles


router = APIRouter(
    prefix="/api/v1/agents/crop-advisory",
    tags=["Crop Advisory Agent"],
)

ALLOWED_ROLES = (
    Role.admin,
    Role.gis_operator,
    Role.ml_team,
)


@router.post("/generate", response_model=CropAdvisoryResult)
def generate_advisory(
    request: CropAdvisoryRequest,
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
        return generate_crop_advisory(request)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc
