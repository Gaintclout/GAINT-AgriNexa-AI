import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.database import get_db
from app.models import User
from app.security import AuthenticationConfigurationError, Role, create_access_token, hash_password, verify_password, require_roles
from app.auth_router import router

@pytest.fixture(autouse=True)
def secret(monkeypatch):
    monkeypatch.setenv("AGRINEXA_JWT_SECRET", "development-test-secret-not-for-production-12345")

def test_password_hash():
    hashed = hash_password("secure-passphrase-123")
    assert hashed != "secure-passphrase-123"
    assert verify_password("secure-passphrase-123", hashed)
    assert not verify_password("wrong-password", hashed)

def test_password_minimum():
    with pytest.raises(ValueError):
        hash_password("short")

def test_auth_missing_and_valid():
    app = FastAPI()
    app.include_router(router)
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    User.__table__.create(engine)
    with Session(engine) as db:
        db.add(User(id="user-1", email="officer@example.com", password_hash=hash_password("secure-passphrase-123"), role=Role.officer.value, is_active=True))
        db.commit()
    def override_db():
        with Session(engine) as db:
            yield db
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        assert client.get("/api/v1/auth/me").status_code == 401
        token = create_access_token("user-1", Role.officer)
        response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json() == {"subject": "user-1", "role": "officer"}
    engine.dispose()

def test_invalid_token():
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid"}).status_code == 401

def test_rbac():
    app = FastAPI()
    @app.get("/officer")
    def officer(_=Depends(require_roles(Role.officer))):
        return {"ok": True}
    client = TestClient(app)
    farmer = create_access_token("u1", Role.farmer)
    officer = create_access_token("u2", Role.officer)
    assert client.get("/officer", headers={"Authorization": f"Bearer {farmer}"}).status_code == 403
    assert client.get("/officer", headers={"Authorization": f"Bearer {officer}"}).status_code == 200

def test_missing_secret(monkeypatch):
    monkeypatch.delenv("AGRINEXA_JWT_SECRET", raising=False)
    with pytest.raises(AuthenticationConfigurationError):
        create_access_token("u", Role.admin)
