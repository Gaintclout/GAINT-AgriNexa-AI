"""Authenticated, read-only weather agent API."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .database import get_db
from .models import User
from .security import Principal, Role, require_roles
from .weather_agent import (
    WeatherAgentError,
    WeatherRequest,
    WeatherResult,
    fetch_weather_forecast,
)

router = APIRouter(
    prefix="/api/v1/agents/weather",
    tags=["Weather Agent"],
)

ALLOWED_ROLES = (
    Role.admin,
    Role.gis_operator,
    Role.ml_team,
)


@router.post("/forecast", response_model=WeatherResult)
def weather_forecast(
    request: WeatherRequest,
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
        return fetch_weather_forecast(
            latitude=request.latitude,
            longitude=request.longitude,
            crop_name=request.crop_name,
        )
    except WeatherAgentError as exc:
        raise HTTPException(
            status_code=503,
            detail="Weather forecast temporarily unavailable",
        ) from exc
