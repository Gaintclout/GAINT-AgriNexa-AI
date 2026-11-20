from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.crop_advisory_agent import (
    CropAdvisoryRequest,
    build_crop_advisory,
    generate_crop_advisory,
)
from app.weather_agent import (
    WeatherAgentError,
    WeatherResult,
    WeatherRisk,
)


def request(**kwargs):
    values = {
        "crop_name": "rice",
        "growth_stage": "vegetative",
    }
    values.update(kwargs)
    return CropAdvisoryRequest(**values)


def test_general_advisory():
    result = generate_crop_advisory(request())
    assert len(result.advisories) == 2
    assert result.weather_status == "not_requested"
    assert result.persisted is False
    assert result.advisory_only is True


def test_all_crops_supported():
    for crop in (
        "rice", "wheat", "maize",
        "cotton", "groundnut", "tomato"
    ):
        result = generate_crop_advisory(
            request(crop_name=crop)
        )
        assert result.crop_name == crop


def test_all_growth_stages_supported():
    for stage in (
        "establishment",
        "vegetative",
        "flowering",
        "harvest",
    ):
        result = generate_crop_advisory(
            request(growth_stage=stage)
        )
        assert result.growth_stage == stage


def test_unknown_crop_rejected():
    with pytest.raises(ValidationError):
        request(crop_name="unknown")


def test_extra_fields_rejected():
    with pytest.raises(ValidationError):
        request(secret="unexpected")


def test_coordinates_must_be_paired():
    with pytest.raises(ValueError):
        generate_crop_advisory(
            request(latitude=17.385)
        )


def test_weather_requires_coordinates():
    with pytest.raises(ValueError):
        generate_crop_advisory(
            request(include_weather=True)
        )


def test_weather_not_called_when_disabled():
    with patch(
        "app.crop_advisory_agent.fetch_weather_forecast"
    ) as provider:
        generate_crop_advisory(request())
        provider.assert_not_called()


def test_weather_risks_are_explainable():
    weather = WeatherResult(
        latitude=17.385,
        longitude=78.4867,
        crop_name="rice",
        forecast_date="2026-11-18",
        temperature_max_c=41,
        temperature_min_c=25,
        rainfall_mm=55,
        wind_max_kmh=10,
        precipitation_probability_max=90,
        risks=[
            WeatherRisk(
                code="HEAVY_RAIN",
                severity="high",
                title="Heavy rain",
                recommendation="Review drainage.",
            )
        ],
    )

    result = build_crop_advisory(
        request(growth_stage="harvest"),
        weather,
        "available",
    )

    codes = {item.code for item in result.advisories}

    assert "WEATHER_HEAVY_RAIN" in codes
    assert "HARVEST_RAIN_REVIEW" in codes
    assert result.weather_source == "Open-Meteo"


def test_weather_provider_failure_degrades_safely():
    with patch(
        "app.crop_advisory_agent.fetch_weather_forecast",
        side_effect=WeatherAgentError("offline"),
    ):
        result = generate_crop_advisory(
            request(
                latitude=17.385,
                longitude=78.4867,
                include_weather=True,
            )
        )

    assert result.weather_status == "unavailable"
    assert all(
        item.category != "weather"
        for item in result.advisories
    )


def test_weather_success():
    weather = WeatherResult(
        latitude=17.385,
        longitude=78.4867,
        crop_name="rice",
        forecast_date="2026-11-18",
        temperature_max_c=30,
        temperature_min_c=22,
        rainfall_mm=0,
        wind_max_kmh=10,
        precipitation_probability_max=5,
        risks=[],
    )

    with patch(
        "app.crop_advisory_agent.fetch_weather_forecast",
        return_value=weather,
    ) as provider:
        result = generate_crop_advisory(
            request(
                latitude=17.385,
                longitude=78.4867,
                include_weather=True,
            )
        )

    assert result.weather_status == "available"
    provider.assert_called_once()
