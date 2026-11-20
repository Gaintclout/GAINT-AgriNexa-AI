from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_liveness_has_no_dependency_details():
    response = client.get("/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "agrinexa-api"}
    assert response.headers["x-request-id"]

def test_readiness_fails_closed_without_dependencies():
    with patch("app.health.make_engine", side_effect=RuntimeError("secret-host")), patch("app.health.storage_root", side_effect=RuntimeError("secret-path")):
        response = client.get("/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "checks": {"database": False, "migration": False, "postgis": False, "photo_storage": False}}
    assert "secret" not in response.text

def test_readiness_passes_only_with_expected_schema_and_storage(tmp_path):
    connection = Mock()
    connection.execute.return_value.one.return_value = ("0012_agent_audit_governance", True)
    context = Mock()
    context.__enter__ = Mock(return_value=connection)
    context.__exit__ = Mock(return_value=False)
    engine = Mock()
    engine.connect.return_value = context
    with patch("app.health.make_engine", return_value=engine), patch("app.health.storage_root", return_value=tmp_path):
        response = client.get("/ready", headers={"X-Request-ID": "m22-test-request"})
    assert response.status_code == 200
    assert response.headers["x-request-id"] == "m22-test-request"
    assert response.json()["status"] == "ready"

def test_invalid_request_id_is_replaced():
    response = client.get("/live", headers={"X-Request-ID": "bad value with spaces"})
    assert response.headers["x-request-id"] != "bad value with spaces"
