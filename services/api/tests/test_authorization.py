import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.authorization import require_active_roles
from app.database import get_db
from app.models import User
from app.security import Role, create_access_token

@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("AGRINEXA_JWT_SECRET", "unit-test-authorization-secret-123456789")
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    User.__table__.create(engine)
    app = FastAPI()
    @app.get("/secure")
    def secure(_=Depends(require_active_roles(Role.officer))):
        return {"ok": True}
    def db_override():
        with Session(engine) as db:
            yield db
    app.dependency_overrides[get_db] = db_override
    with Session(engine) as db:
        db.add(User(id="officer-1", email="officer@example.com", password_hash="test-hash", role="officer", is_active=True))
        db.commit()
    yield TestClient(app), engine
    engine.dispose()

def test_active_officer_allowed(env):
    client, _ = env
    token = create_access_token("officer-1", Role.officer)
    assert client.get("/secure", headers={"Authorization": f"Bearer {token}"}).status_code == 200

def test_missing_user_rejected(env):
    client, _ = env
    token = create_access_token("missing", Role.officer)
    assert client.get("/secure", headers={"Authorization": f"Bearer {token}"}).status_code == 401

def test_role_change_invalidates_token(env):
    client, engine = env
    token = create_access_token("officer-1", Role.officer)
    with Session(engine) as db:
        db.get(User, "officer-1").role = "farmer"
        db.commit()
    assert client.get("/secure", headers={"Authorization": f"Bearer {token}"}).status_code == 401

def test_inactive_user_rejected(env):
    client, engine = env
    token = create_access_token("officer-1", Role.officer)
    with Session(engine) as db:
        db.get(User, "officer-1").is_active = False
        db.commit()
    assert client.get("/secure", headers={"Authorization": f"Bearer {token}"}).status_code == 401

def test_insufficient_role_rejected(env):
    client, engine = env
    with Session(engine) as db:
        db.get(User, "officer-1").role = "farmer"
        db.commit()
    token = create_access_token("officer-1", Role.farmer)
    assert client.get("/secure", headers={"Authorization": f"Bearer {token}"}).status_code == 403
