"""Geography authorization smoke checks without requiring a live PostGIS service."""
from fastapi.testclient import TestClient
from app.main import app

def test_geography_requires_authentication():
    client = TestClient(app)
    for path in ("/api/v1/geography/states", "/api/v1/geography/districts", "/api/v1/geography/mandals"):
        assert client.get(path).status_code == 401
    assert client.post("/api/v1/geography/states", json={"code": "TG", "name": "Telangana"}).status_code == 401

def test_geography_migration_contract():
    from pathlib import Path
    file = Path(__file__).resolve().parents[1] / "migrations/versions/0002_geography_hierarchy.py"
    text = file.read_text()
    assert 'down_revision = "0001_identity_geo"' in text
    assert 'op.create_table("states"' in text
    assert 'op.create_table("districts"' in text
    assert 'op.create_table("mandals"' in text
