"""Isolated authenticated HTTP UAT for registered agent workflows.

External weather data is explicitly fixture-backed. Market and Scheme run
with sources unconfigured. No production database or external service is used.
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.security import Role, create_access_token
from app.weather_agent import WeatherResult


class ActiveAdminDb:
    def get(self, _model, subject):
        return SimpleNamespace(id=subject, role="admin", is_active=True)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv(
        "AGRINEXA_JWT_SECRET",
        "agent-functional-uat-http-secret-32-characters",
    )
    monkeypatch.delenv("AGRINEXA_MARKET_SNAPSHOT_PATH", raising=False)
    monkeypatch.delenv("AGRINEXA_SCHEME_CATALOGUE_PATH", raising=False)
    app.dependency_overrides[get_db] = lambda: ActiveAdminDb()
    token = create_access_token("uat-admin", Role.admin)
    try:
        with TestClient(app) as test_client:
            test_client.headers.update({"Authorization": f"Bearer {token}"})
            yield test_client
    finally:
        app.dependency_overrides.clear()


def test_metadata_and_registry_are_consistent(client):
    metadata = client.get("/api/v1/metadata")
    registry = client.get("/api/v1/agents")
    assert metadata.status_code == registry.status_code == 200
    assert [item["id"] for item in registry.json()] == metadata.json()["agents"]
    assert len(registry.json()) == 8


def test_intake_profile_availability_reports_approval(client):
    response = client.get("/api/v1/agents/intake-profile/availability")
    assert response.status_code == 200
    assert response.json()["available"] is True
    assert "audit" in response.json()["reason"].lower()


def test_weather_http_contract_with_explicit_provider_fixture(client):
    forecast = WeatherResult(
        latitude=17.385,
        longitude=78.4867,
        crop_name="rice",
        forecast_date="2026-11-19",
        temperature_max_c=36,
        temperature_min_c=23,
        rainfall_mm=2,
        wind_max_kmh=12,
        precipitation_probability_max=20,
        risks=[],
    )
    with patch("app.weather_agent_router.fetch_weather_forecast", return_value=forecast):
        response = client.post(
            "/api/v1/agents/weather/forecast",
            json={"latitude": 17.385, "longitude": 78.4867, "crop_name": "rice"},
        )
    assert response.status_code == 200
    assert response.json()["source"] == "Open-Meteo"
    assert response.json()["persisted"] is False


def test_crop_advisory_http_contract_without_weather(client):
    response = client.post(
        "/api/v1/agents/crop-advisory/generate",
        json={"crop_name": "rice", "growth_stage": "vegetative", "include_weather": False},
    )
    assert response.status_code == 200
    assert response.json()["weather_status"] == "not_requested"
    assert response.json()["advisory_only"] is True
    assert response.json()["advisories"]


def test_market_reports_unconfigured_source_without_fabrication(client):
    response = client.post("/api/v1/agents/market/prices", json={"commodity": "rice"})
    assert response.status_code == 200
    assert response.json()["source_status"] == "not_configured"
    assert response.json()["records"] == []
    assert response.json()["available"] is False


def test_scheme_reports_unconfigured_source_without_fabrication(client):
    response = client.post("/api/v1/agents/schemes/screen", json={})
    assert response.status_code == 200
    assert response.json()["source_status"] == "not_configured"
    assert response.json()["schemes"] == []
    assert response.json()["available"] is False


def test_escalation_is_advisory_and_performs_no_action(client):
    from app.escalation_agent import evaluate_escalation
    with patch(
        "app.escalation_agent_router.execute_audited_escalation_review",
        side_effect=lambda _principal, request: evaluate_escalation(request).model_copy(
            update={"correlation_id": "00000000-0000-4000-8000-000000000018"}
        ),
    ):
        response = client.post(
            "/api/v1/agents/escalation/screen",
            json={
                "case_reference": "UAT-CASE-001",
                "indicators": [{
                    "indicator": "crop_damage",
                    "description": "Documented crop damage requiring human review",
                    "source_type": "field_observation",
                }],
            },
        )
    assert response.status_code == 200
    assert response.json()["human_review_required"] is True
    assert response.json()["external_action_performed"] is False
    assert response.json()["notifications_sent"] is False


def test_learning_is_review_only_and_performs_no_training(client):
    from app.learning_agent import evaluate_learning
    with patch(
        "app.learning_agent_router.execute_audited_learning_review",
        side_effect=lambda _principal, request: evaluate_learning(request).model_copy(
            update={"correlation_id": "00000000-0000-4000-8000-000000000019"}
        ),
    ):
        response = client.post(
            "/api/v1/agents/learning/review",
            json={
                "review_reference": "UAT-REVIEW-001",
                "feedback": [{
                    "feedback_id": "UAT-FB-001",
                    "agent_domain": "crop_advisory",
                    "recommendation_reference": "UAT-REC-001",
                    "outcome": "incomplete",
                    "explanation": "Recommendation needs additional verified evidence",
                }],
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert body["training_performed"] is False
    assert body["model_updated"] is False
    assert body["feedback_persisted"] is False


def test_generic_execution_stays_blocked(client):
    for agent_id in (
        "INTAKE", "PROFILE", "WEATHER", "CROP_ADVISORY",
        "MARKET", "SCHEME", "ESCALATION", "LEARNING",
    ):
        response = client.post(f"/api/v1/agents/{agent_id}/execute")
        assert response.status_code == 403
        assert response.json()["detail"] == "Agent execution is disabled"
