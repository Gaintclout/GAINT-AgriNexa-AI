from unittest.mock import patch
import io
import json

import pytest

from app.weather_agent import (
    WeatherAgentError,
    evaluate_weather_risks,
    fetch_weather_forecast,
)


def test_extreme_heat():
    risks = evaluate_weather_risks(42, 0, 10, 0)
    assert any(r.code == "EXTREME_HEAT" for r in risks)


def test_heavy_rain():
    risks = evaluate_weather_risks(28, 65, 10, 90)
    assert any(r.code == "HEAVY_RAIN" for r in risks)


def test_high_wind():
    risks = evaluate_weather_risks(29, 0, 60, 0)
    assert any(r.code == "HIGH_WIND" for r in risks)


def test_no_alerts():
    assert evaluate_weather_risks(28, 2, 8, 20) == []


def test_missing_measurements():
    assert evaluate_weather_risks(None, None, None, None) == []


def test_forecast_parsing():
    payload = {
        "daily": {
            "time": ["2026-11-18"],
            "temperature_2m_max": [36],
            "temperature_2m_min": [23],
            "precipitation_sum": [5],
            "wind_speed_10m_max": [12],
            "precipitation_probability_max": [30],
        }
    }

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, size):
            return json.dumps(payload).encode()

    with patch(
        "app.weather_agent.urllib.request.urlopen",
        return_value=Response(),
    ):
        result = fetch_weather_forecast(17.385, 78.4867, "Rice")

    assert result.temperature_max_c == 36
    assert result.source == "Open-Meteo"
    assert result.persisted is False
    assert result.advisory_only is True


def test_provider_failure():
    with patch(
        "app.weather_agent.urllib.request.urlopen",
        side_effect=OSError("network unavailable"),
    ):
        with pytest.raises(WeatherAgentError):
            fetch_weather_forecast(17.385, 78.4867)
