"""HTTP contract tests for disabled Intake/Profile execution."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


def test_unauthenticated_preview_is_rejected():
    client = TestClient(app)

    response = client.post(
        "/api/v1/agents/intake-profile/preview",
        json={"parcel_id": "parcel-1"},
    )

    assert response.status_code in (401, 403)


def test_unauthenticated_availability_is_rejected():
    client = TestClient(app)

    response = client.get(
        "/api/v1/agents/intake-profile/availability"
    )

    assert response.status_code in (401, 403)


def test_preview_does_not_call_execution_service_without_auth():
    client = TestClient(app)

    with patch(
        "app.agent_execution_service.execute_audited_intake_profile"
    ) as execute:
        response = client.post(
            "/api/v1/agents/intake-profile/preview",
            json={"parcel_id": "parcel-1"},
        )

    assert response.status_code in (401, 403)
    execute.assert_not_called()
