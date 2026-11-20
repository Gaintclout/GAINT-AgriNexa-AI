from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    assert client.get("/health").json()["status"] == "ok"

def test_eight_agents_and_scim_distinction():
    data = client.get("/api/v1/metadata").json()
    assert len(data["agents"]) == 8
    assert data["scim_is_agent"] is False

def test_parcels_are_not_public():
    assert client.get("/api/v1/parcels").status_code == 401
    assert client.post("/api/v1/parcels", json={"external_id": "test-1", "village_code": "TG-001", "area_hectares": 1.5}).status_code == 401
