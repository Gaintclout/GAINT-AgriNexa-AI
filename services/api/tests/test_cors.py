import pytest
from fastapi.testclient import TestClient
from app.cors import allowed_origins
from app.main import app

def test_local_origin_config(monkeypatch):
    monkeypatch.setenv("AGRINEXA_CORS_ORIGINS", "http://localhost:5173")
    assert allowed_origins() == ["http://localhost:5173"]

def test_multiple_origins(monkeypatch):
    monkeypatch.setenv("AGRINEXA_CORS_ORIGINS", "http://localhost:5173,https://portal.example.org")
    assert len(allowed_origins()) == 2

def test_wildcard_is_rejected(monkeypatch):
    monkeypatch.setenv("AGRINEXA_CORS_ORIGINS", "*")
    with pytest.raises(RuntimeError):
        allowed_origins()

def test_configured_origin_can_preflight_patch():
    response = TestClient(app).options('/api/v1/parcels/example/owner', headers={
        'Origin': 'http://localhost:5173', 'Access-Control-Request-Method': 'PATCH'
    })
    assert response.status_code == 200
    assert 'PATCH' in response.headers['access-control-allow-methods']
