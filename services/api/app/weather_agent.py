"""Read-only agricultural weather intelligence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import json
import math
import urllib.error
import urllib.parse
import urllib.request

from pydantic import BaseModel, Field


FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


class WeatherAgentError(Exception):
    pass


class WeatherRequest(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    crop_name: str | None = Field(default=None, max_length=80)


class WeatherRisk(BaseModel):
    code: str
    severity: str
    title: str
    recommendation: str


class WeatherResult(BaseModel):
    latitude: float
    longitude: float
    crop_name: str | None
    forecast_date: str
    temperature_max_c: float | None
    temperature_min_c: float | None
    rainfall_mm: float | None
    wind_max_kmh: float | None
    precipitation_probability_max: float | None
    risks: list[WeatherRisk]
    source: str = "Open-Meteo"
    advisory_only: bool = True
    persisted: bool = False


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if not isinstance(value, (int, float)):
        return None
    value = float(value)
    if not math.isfinite(value):
        return None
    return value


def evaluate_weather_risks(
    maximum_temperature: float | None,
    rainfall: float | None,
    wind: float | None,
    precipitation_probability: float | None,
) -> list[WeatherRisk]:
    risks: list[WeatherRisk] = []

    if maximum_temperature is not None and maximum_temperature >= 40:
        risks.append(
            WeatherRisk(
                code="EXTREME_HEAT",
                severity="high",
                title="Extreme heat forecast",
                recommendation=(
                    "Monitor crop moisture and irrigation needs. "
                    "Avoid unnecessary field work during peak heat."
                ),
            )
        )
    elif maximum_temperature is not None and maximum_temperature >= 35:
        risks.append(
            WeatherRisk(
                code="HEAT",
                severity="medium",
                title="High temperature forecast",
                recommendation=(
                    "Monitor soil moisture and crop heat stress."
                ),
            )
        )

    if rainfall is not None and rainfall >= 50:
        risks.append(
            WeatherRisk(
                code="HEAVY_RAIN",
                severity="high",
                title="Heavy rainfall forecast",
                recommendation=(
                    "Check field drainage and avoid unnecessary "
                    "irrigation or chemical application."
                ),
            )
        )
    elif rainfall is not None and rainfall >= 20:
        risks.append(
            WeatherRisk(
                code="RAIN",
                severity="medium",
                title="Significant rainfall forecast",
                recommendation=(
                    "Review irrigation plans and monitor drainage."
                ),
            )
        )

    if wind is not None and wind >= 50:
        risks.append(
            WeatherRisk(
                code="HIGH_WIND",
                severity="high",
                title="Strong wind forecast",
                recommendation=(
                    "Avoid spraying and secure vulnerable farm equipment."
                ),
            )
        )

    if (
        precipitation_probability is not None
        and precipitation_probability >= 80
        and (rainfall is None or rainfall < 20)
    ):
        risks.append(
            WeatherRisk(
                code="RAIN_PROBABILITY",
                severity="low",
                title="High chance of precipitation",
                recommendation=(
                    "Check the latest forecast before irrigation or spraying."
                ),
            )
        )

    return risks


def fetch_weather_forecast(
    latitude: float,
    longitude: float,
    crop_name: str | None = None,
) -> WeatherResult:
    params = urllib.parse.urlencode(
        {
            "latitude": latitude,
            "longitude": longitude,
            "daily": (
                "temperature_2m_max,"
                "temperature_2m_min,"
                "precipitation_sum,"
                "wind_speed_10m_max,"
                "precipitation_probability_max"
            ),
            "forecast_days": 1,
            "timezone": "auto",
        }
    )

    request = urllib.request.Request(
        f"{FORECAST_URL}?{params}",
        headers={
            "Accept": "application/json",
            "User-Agent": "GAINT-AgriNexa-AI/1.0",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            if response.status != 200:
                raise WeatherAgentError("Weather provider unavailable")

            payload = json.loads(response.read(200000))

    except (
        urllib.error.URLError,
        TimeoutError,
        OSError,
        ValueError,
    ) as exc:
        raise WeatherAgentError(
            "Weather forecast temporarily unavailable"
        ) from exc

    if not isinstance(payload, dict):
        raise WeatherAgentError("Invalid weather provider response")

    daily = payload.get("daily")

    if not isinstance(daily, dict):
        raise WeatherAgentError("Weather forecast data missing")

    def first(key: str) -> Any:
        values = daily.get(key)
        if not isinstance(values, list) or not values:
            return None
        return values[0]

    date = first("time")

    if not isinstance(date, str):
        raise WeatherAgentError("Weather forecast date missing")

    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError as exc:
        raise WeatherAgentError("Invalid weather forecast date") from exc

    tmax = _number(first("temperature_2m_max"))
    tmin = _number(first("temperature_2m_min"))
    rainfall = _number(first("precipitation_sum"))
    wind = _number(first("wind_speed_10m_max"))
    probability = _number(
        first("precipitation_probability_max")
    )

    if all(
        value is None
        for value in (tmax, tmin, rainfall, wind, probability)
    ):
        raise WeatherAgentError("Weather measurements unavailable")

    return WeatherResult(
        latitude=latitude,
        longitude=longitude,
        crop_name=crop_name,
        forecast_date=date,
        temperature_max_c=tmax,
        temperature_min_c=tmin,
        rainfall_mm=rainfall,
        wind_max_kmh=wind,
        precipitation_probability_max=probability,
        risks=evaluate_weather_risks(
            tmax,
            rainfall,
            wind,
            probability,
        ),
    )
