from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from app.weather_agent import WeatherRequest, WeatherAgentError
from app.weather_agent_router import weather_forecast


class Principal:
    subject = "test-user"
    role = Mock(value="admin")


class User:
    is_active = True
    role = "admin"


def test_weather_requires_active_account():
    db = Mock()
    db.get.return_value = None

    with pytest.raises(HTTPException) as exc:
        weather_forecast(
            WeatherRequest(latitude=17.385, longitude=78.4867),
            Principal(),
            db,
        )

    assert exc.value.status_code == 401


def test_weather_success():
    db = Mock()
    db.get.return_value = User()

    with patch(
        "app.weather_agent_router.fetch_weather_forecast",
        return_value={"source": "Open-Meteo"},
    ) as provider:
        result = weather_forecast(
            WeatherRequest(latitude=17.385, longitude=78.4867),
            Principal(),
            db,
        )

    assert result["source"] == "Open-Meteo"
    provider.assert_called_once()


def test_weather_provider_failure_returns_503():
    db = Mock()
    db.get.return_value = User()

    with patch(
        "app.weather_agent_router.fetch_weather_forecast",
        side_effect=WeatherAgentError("provider failure"),
    ):
        with pytest.raises(HTTPException) as exc:
            weather_forecast(
                WeatherRequest(latitude=17.385, longitude=78.4867),
                Principal(),
                db,
            )

    assert exc.value.status_code == 503


def test_invalid_coordinates_rejected():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        WeatherRequest(latitude=120, longitude=78)
