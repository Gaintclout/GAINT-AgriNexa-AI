"""HTTP authorization regression tests for dedicated agent workflows."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.security import Role, create_access_token


ROUTES = (
    ("/api/v1/agents/intake-profile/preview", {"parcel_id": "parcel-1"}),
    ("/api/v1/agents/weather/forecast", {"latitude": 17.385, "longitude": 78.4867}),
    ("/api/v1/agents/crop-advisory/generate", {"crop_name": "rice", "growth_stage": "vegetative"}),
    ("/api/v1/agents/market/prices", {"commodity": "rice"}),
    ("/api/v1/agents/schemes/screen", {}),
    ("/api/v1/agents/escalation/screen", {
        "case_reference": "CASE-001",
        "indicators": [{
            "indicator": "crop_damage",
            "description": "Documented agricultural field observation",
            "source_type": "field_observation",
        }],
    }),
    ("/api/v1/agents/learning/review", {
        "review_reference": "REVIEW-001",
        "feedback": [{
            "feedback_id": "FB-001",
            "agent_domain": "crop_advisory",
            "recommendation_reference": "REC-001",
            "outcome": "incomplete",
            "explanation": "Recommendation requires additional review",
        }],
    }),
)


@pytest.fixture(autouse=True)
def jwt_secret(monkeypatch):
    monkeypatch.setenv(
        "AGRINEXA_JWT_SECRET",
        "dedicated-agent-http-security-secret-32-chars",
    )


@pytest.mark.parametrize("path,payload", ROUTES)
def test_dedicated_workflow_rejects_anonymous(path, payload):
    with TestClient(app) as client:
        response = client.post(path, json=payload)

    assert response.status_code == 401


@pytest.mark.parametrize("path,payload", ROUTES)
def test_dedicated_workflow_rejects_farmer_role(path, payload):
    token = create_access_token("farmer-1", Role.farmer)

    with TestClient(app) as client:
        response = client.post(
            path,
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 403


def test_learning_workflow_rejects_gis_operator_role():
    path, payload = ROUTES[-1]
    token = create_access_token("gis-1", Role.gis_operator)

    with TestClient(app) as client:
        response = client.post(
            path,
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 403
