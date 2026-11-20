"""Explainable, read-only agricultural crop advisory engine."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, ConfigDict

from .weather_agent import (
    WeatherAgentError,
    WeatherResult,
    fetch_weather_forecast,
)


CropName = Literal[
    "rice",
    "wheat",
    "maize",
    "cotton",
    "groundnut",
    "tomato",
]

CropStage = Literal[
    "establishment",
    "vegetative",
    "flowering",
    "harvest",
]

Severity = Literal["low", "medium", "high"]


class CropAdvisoryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    crop_name: CropName
    growth_stage: CropStage

    latitude: float | None = Field(
        default=None,
        ge=-90,
        le=90,
    )

    longitude: float | None = Field(
        default=None,
        ge=-180,
        le=180,
    )

    include_weather: bool = False


class CropAdvisoryItem(BaseModel):
    code: str
    category: str
    severity: Severity
    title: str
    explanation: str
    recommendation: str
    evidence_source: str


class CropAdvisoryResult(BaseModel):
    crop_name: CropName
    growth_stage: CropStage
    advisories: list[CropAdvisoryItem]
    weather_status: str
    weather_forecast_date: str | None = None
    weather_source: str | None = None
    advisory_only: bool = True
    persisted: bool = False
    methodology: str = (
        "Transparent, conservative crop-stage rules and "
        "optional forecast threshold screening."
    )


CROP_GUIDANCE = {
    "rice": (
        "Monitor field water conditions and drainage.",
        "Observe leaves and crop development for unusual changes.",
    ),
    "wheat": (
        "Monitor soil moisture and avoid unnecessary irrigation.",
        "Observe crop growth and field conditions regularly.",
    ),
    "maize": (
        "Monitor soil moisture and crop establishment.",
        "Inspect plants for visible stress or unusual growth.",
    ),
    "cotton": (
        "Monitor field drainage and plant moisture stress.",
        "Inspect plants regularly for unusual leaf or boll changes.",
    ),
    "groundnut": (
        "Avoid prolonged waterlogging and monitor soil moisture.",
        "Observe crop development and field conditions.",
    ),
    "tomato": (
        "Maintain appropriate moisture and field drainage.",
        "Inspect leaves and fruit for visible changes.",
    ),
}

STAGE_GUIDANCE = {
    "establishment": (
        "Establishment monitoring",
        "Check germination or transplant establishment and "
        "observe moisture conditions.",
    ),
    "vegetative": (
        "Vegetative growth monitoring",
        "Observe plant growth, field moisture and visible stress.",
    ),
    "flowering": (
        "Flowering-stage monitoring",
        "Monitor moisture stress and weather conditions carefully "
        "during flowering.",
    ),
    "harvest": (
        "Harvest readiness",
        "Check crop maturity and field conditions before planning "
        "harvest operations.",
    ),
}


def build_crop_advisory(
    request: CropAdvisoryRequest,
    weather: WeatherResult | None = None,
    weather_status: str = "not_requested",
) -> CropAdvisoryResult:
    guidance, observation = CROP_GUIDANCE[request.crop_name]
    stage_title, stage_recommendation = STAGE_GUIDANCE[
        request.growth_stage
    ]

    advisories = [
        CropAdvisoryItem(
            code="CROP_FIELD_MONITORING",
            category="crop",
            severity="low",
            title="Crop field monitoring",
            explanation=(
                f"General monitoring guidance for {request.crop_name}."
            ),
            recommendation=f"{guidance} {observation}",
            evidence_source="general_crop_guidance",
        ),
        CropAdvisoryItem(
            code="GROWTH_STAGE_MONITORING",
            category="growth_stage",
            severity="low",
            title=stage_title,
            explanation=(
                f"The selected crop stage is {request.growth_stage}."
            ),
            recommendation=stage_recommendation,
            evidence_source="growth_stage_rule",
        ),
    ]

    if weather is not None:
        for risk in weather.risks:
            advisories.append(
                CropAdvisoryItem(
                    code=f"WEATHER_{risk.code}",
                    category="weather",
                    severity=risk.severity,
                    title=risk.title,
                    explanation=(
                        "A forecast threshold was reached. "
                        "This is not a measured field condition."
                    ),
                    recommendation=risk.recommendation,
                    evidence_source="open_meteo_forecast_threshold",
                )
            )

        if request.growth_stage == "harvest":
            rain = weather.rainfall_mm

            if rain is not None and rain >= 20:
                advisories.append(
                    CropAdvisoryItem(
                        code="HARVEST_RAIN_REVIEW",
                        category="harvest",
                        severity="medium",
                        title="Review harvest timing",
                        explanation=(
                            "Forecast rainfall may affect planned "
                            "harvest operations."
                        ),
                        recommendation=(
                            "Check local conditions and updated forecasts "
                            "before scheduling harvest."
                        ),
                        evidence_source="forecast_and_stage_rule",
                    )
                )

    return CropAdvisoryResult(
        crop_name=request.crop_name,
        growth_stage=request.growth_stage,
        advisories=advisories,
        weather_status=weather_status,
        weather_forecast_date=(
            weather.forecast_date if weather is not None else None
        ),
        weather_source=(
            weather.source if weather is not None else None
        ),
    )


def generate_crop_advisory(
    request: CropAdvisoryRequest,
) -> CropAdvisoryResult:
    has_lat = request.latitude is not None
    has_lon = request.longitude is not None

    if has_lat != has_lon:
        raise ValueError(
            "Latitude and longitude must be supplied together"
        )

    if request.include_weather and not (has_lat and has_lon):
        raise ValueError(
            "Coordinates are required for weather integration"
        )

    if not request.include_weather:
        return build_crop_advisory(request)

    try:
        weather = fetch_weather_forecast(
            latitude=request.latitude,
            longitude=request.longitude,
            crop_name=request.crop_name,
        )
    except WeatherAgentError:
        return build_crop_advisory(
            request,
            weather_status="unavailable",
        )

    return build_crop_advisory(
        request,
        weather=weather,
        weather_status="available",
    )
