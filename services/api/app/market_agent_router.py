"""Authenticated read-only market intelligence API."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .database import get_db
from .models import User
from .security import Principal, Role, require_roles
from .market_agent import (
    MarketDataError,
    MarketRequest,
    MarketResult,
    generate_market_intelligence,
)


router = APIRouter(
    prefix="/api/v1/agents/market",
    tags=["Market Intelligence Agent"],
)

ALLOWED_ROLES = (
    Role.admin,
    Role.gis_operator,
    Role.ml_team,
)


@router.post("/prices", response_model=MarketResult)
def market_prices(
    request: MarketRequest,
    principal: Principal = Depends(
        require_roles(*ALLOWED_ROLES)
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

    try:
        return generate_market_intelligence(request)
    except MarketDataError as exc:
        raise HTTPException(
            status_code=503,
            detail="Verified market data temporarily unavailable",
        ) from exc
