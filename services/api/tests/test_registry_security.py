import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.database import get_db
from app.main import app
from app.models import User
from app.security import Role, create_access_token

@pytest.fixture(autouse=True)
def secret(monkeypatch):
    monkeypatch.setenv("AGRINEXA_JWT_SECRET", "test-only-32-character-secret-for-ci-12345")

def test_registry_requires_authentication():
    client = TestClient(app)
    for path in ("/api/v1/villages", "/api/v1/parcels", "/api/v1/parcels/any"):
        assert client.get(path).status_code == 401
    assert client.post("/api/v1/parcels", json={"external_id": "p1", "village_code": "v1", "area_hectares": 1}).status_code == 401

def test_farmer_cannot_modify_registry():
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    event.listen(engine, "connect", lambda connection, _: connection.create_function("AsEWKB", 1, lambda value: value))
    User.__table__.create(engine)
    with Session(engine) as db:
        db.add_all([
            User(id="farmer-1", email="farmer@example.com", password_hash="test-hash", role="farmer", is_active=True),
            User(id="farmer-2", email="other@example.com", password_hash="test-hash", role="farmer", is_active=True),
            User(id="admin-1", email="admin@example.com", password_hash="test-hash", role="admin", is_active=True),
        ])
        db.commit()
        db.execute(text("CREATE TABLE parcels (id VARCHAR(36) PRIMARY KEY, external_id VARCHAR(100), village_code VARCHAR(100), farmer_id VARCHAR(36), area_hectares NUMERIC, geom BLOB, created_at DATETIME)"))
        db.execute(text("INSERT INTO parcels VALUES ('owned-1','OWNED','v1','farmer-1',1,NULL,'2026-01-01 00:00:00'), ('other-1','OTHER','v1','farmer-2',2,NULL,'2026-01-01 00:00:00'), ('legacy-1','LEGACY','v1',NULL,3,NULL,'2026-01-01 00:00:00')"))
        db.commit()
    def override_db():
        with Session(engine) as db:
            yield db
    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        token = create_access_token("farmer-1", Role.farmer)
        headers = {"Authorization": "Bearer " + token}
        assert client.post("/api/v1/villages", json={"code": "v1", "name": "Village", "district_code": "d1"}, headers=headers).status_code == 403
        assert client.post("/api/v1/parcels", json={"external_id": "p1", "village_code": "v1", "area_hectares": 1}, headers=headers).status_code == 403
        listed = client.get("/api/v1/parcels", headers=headers)
        assert listed.status_code == 200
        assert [item["id"] for item in listed.json()] == ["owned-1"]
        assert [item["id"] for item in client.get("/api/v1/parcels?search=owned", headers=headers).json()] == ["owned-1"]
        assert client.get("/api/v1/parcels?search=OTHER", headers=headers).json() == []
        assert client.get("/api/v1/parcels?search=%25", headers=headers).json() == []
        assert client.get("/api/v1/parcels/owned-1", headers=headers).status_code == 200
        assert client.get("/api/v1/parcels/other-1", headers=headers).status_code == 404
        assert client.get("/api/v1/parcels/legacy-1", headers=headers).status_code == 404
        assert client.patch("/api/v1/parcels/other-1/owner", json={"farmer_id": "farmer-1"}, headers=headers).status_code == 403
        admin_headers = {"Authorization": "Bearer " + create_access_token("admin-1", Role.admin)}
        assert len(client.get("/api/v1/parcels?limit=1&offset=0", headers=admin_headers).json()) == 1
        farmers = client.get("/api/v1/users/farmers", headers=admin_headers)
        assert farmers.status_code == 200
        assert [item["email"] for item in farmers.json()] == ["farmer@example.com", "other@example.com"]
        assert client.get("/api/v1/users/farmers", headers=headers).status_code == 403
        assert client.patch("/api/v1/parcels/other-1/owner", json={"farmer_id": "missing"}, headers=admin_headers).status_code == 422
        assigned = client.patch("/api/v1/parcels/other-1/owner", json={"farmer_id": "farmer-1"}, headers=admin_headers)
        assert assigned.status_code == 200
        assert assigned.json()["farmer_id"] == "farmer-1"
        assert client.get("/api/v1/parcels/other-1", headers=headers).status_code == 200
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
