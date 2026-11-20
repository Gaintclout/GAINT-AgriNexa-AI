"""Database-backed authentication tests using a temporary SQLite users table."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.database import get_db
from app.main import app
from app.models import User

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("AGRINEXA_JWT_SECRET", "unit-test-only-not-a-production-secret-12345")
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    User.__table__.create(engine)
    def db_override():
        with Session(engine) as session:
            yield session
    app.dependency_overrides[get_db] = db_override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    engine.dispose()

def test_register_login_me(client):
    credentials = {"email": "Farmer@Example.com", "password": "a-strong-password-123"}
    created = client.post("/api/v1/auth/register/farmer", json=credentials)
    assert created.status_code == 201
    assert created.json()["role"] == "farmer"
    assert created.json()["email"] == "farmer@example.com"
    assert client.post("/api/v1/auth/register/farmer", json=credentials).status_code == 409
    token = client.post("/api/v1/auth/login", json=credentials)
    assert token.status_code == 200
    me = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + token.json()["access_token"]})
    assert me.status_code == 200
    assert me.json()["role"] == "farmer"

def test_login_rejects_bad_credentials(client):
    response = client.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": "wrong"})
    assert response.status_code == 401

def test_login_returns_service_unavailable_when_signing_secret_is_missing(client, monkeypatch):
    credentials = {"email": "setup@example.test", "password": "synthetic-password-for-test"}
    assert client.post("/api/v1/auth/register/farmer", json=credentials).status_code == 201
    monkeypatch.delenv("AGRINEXA_JWT_SECRET", raising=False)

    response = client.post("/api/v1/auth/login", json=credentials)

    assert response.status_code == 503
    assert response.json() == {"detail": "Authentication service temporarily unavailable"}

def test_me_requires_existing_active_user(client, monkeypatch):
    from app.security import create_access_token, Role
    token = create_access_token("not-in-database", Role.admin)
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + token}).status_code == 401

def test_registration_cannot_choose_admin_role(client):
    result = client.post("/api/v1/auth/register/farmer", json={"email": "a@example.com", "password": "a-strong-password-123", "role": "admin"})
    assert result.status_code == 201
    assert result.json()["role"] == "farmer"
