
"""AG-10: Registry authentication, authorization and parcel editing tests.

Uses an isolated in-memory SQLite database.

No PostgreSQL development or production database is accessed.
"""

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
    monkeypatch.setenv(
        "AGRINEXA_JWT_SECRET",
        "test-only-32-character-secret-for-ci-12345",
    )


@pytest.fixture
def registry_client():
    """Create an isolated database and override FastAPI DB access."""

    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    event.listen(
        engine,
        "connect",
        lambda connection, _: connection.create_function(
            "AsEWKB",
            1,
            lambda value: value,
        ),
    )

    User.__table__.create(engine)

    with Session(engine) as db:
        db.add_all([
            User(
                id="farmer-1",
                email="farmer@example.com",
                password_hash="test-hash",
                role="farmer",
                is_active=True,
            ),
            User(
                id="farmer-2",
                email="other@example.com",
                password_hash="test-hash",
                role="farmer",
                is_active=True,
            ),
            User(
                id="admin-1",
                email="admin@example.com",
                password_hash="test-hash",
                role="admin",
                is_active=True,
            ),
            User(
                id="gis-1",
                email="gis@example.com",
                password_hash="test-hash",
                role="gis_operator",
                is_active=True,
            ),
        ])

        db.commit()

        db.execute(text("""
            CREATE TABLE villages (
                code VARCHAR(100) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                district_code VARCHAR(100) NOT NULL,
                mandal_code VARCHAR(100)
            )
        """))

        db.execute(text("""
            INSERT INTO villages
                (code, name, district_code, mandal_code)
            VALUES
                ('v1', 'Village One', 'd1', NULL),
                ('v2', 'Village Two', 'd1', NULL)
        """))

        db.execute(text("""
            CREATE TABLE parcels (
                id VARCHAR(36) PRIMARY KEY,
                external_id VARCHAR(100) UNIQUE,
                village_code VARCHAR(100),
                farmer_id VARCHAR(36),
                area_hectares NUMERIC,
                geom BLOB,
                created_at DATETIME
            )
        """))

        db.execute(text("""
            INSERT INTO parcels
                (
                    id,
                    external_id,
                    village_code,
                    farmer_id,
                    area_hectares,
                    geom,
                    created_at
                )
            VALUES
                (
                    'owned-1',
                    'OWNED',
                    'v1',
                    'farmer-1',
                    1,
                    NULL,
                    '2026-01-01 00:00:00'
                ),
                (
                    'other-1',
                    'OTHER',
                    'v1',
                    'farmer-2',
                    2,
                    NULL,
                    '2026-01-01 00:00:00'
                ),
                (
                    'legacy-1',
                    'LEGACY',
                    'v1',
                    NULL,
                    3,
                    NULL,
                    '2026-01-01 00:00:00'
                )
        """))

        db.commit()

    def override_db():
        with Session(engine) as db:
            yield db

    previous_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_db

    try:
        with TestClient(app) as client:
            yield client
    finally:
        if previous_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous_override

        engine.dispose()


def auth_headers(user_id, role):
    token = create_access_token(user_id, role)

    return {
        "Authorization": "Bearer " + token
    }


# --------------------------------------------------
# Authentication
# --------------------------------------------------

def test_registry_requires_authentication(registry_client):
    client = registry_client

    for path in (
        "/api/v1/villages",
        "/api/v1/parcels",
        "/api/v1/parcels/owned-1",
    ):
        assert client.get(path).status_code == 401

    assert client.post(
        "/api/v1/parcels",
        json={
            "external_id": "p1",
            "village_code": "v1",
            "area_hectares": 1,
        },
    ).status_code == 401

    assert client.patch(
        "/api/v1/parcels/owned-1",
        json={"area_hectares": 2},
    ).status_code == 401


# --------------------------------------------------
# Farmer access restrictions
# --------------------------------------------------

def test_farmer_cannot_modify_registry(registry_client):
    client = registry_client
    headers = auth_headers("farmer-1", Role.farmer)

    assert client.post(
        "/api/v1/villages",
        json={
            "code": "v3",
            "name": "Village Three",
            "district_code": "d1",
        },
        headers=headers,
    ).status_code == 403

    assert client.post(
        "/api/v1/parcels",
        json={
            "external_id": "p1",
            "village_code": "v1",
            "area_hectares": 1,
        },
        headers=headers,
    ).status_code == 403

    assert client.patch(
        "/api/v1/parcels/owned-1",
        json={"area_hectares": "5.0000"},
        headers=headers,
    ).status_code == 403

    assert client.patch(
        "/api/v1/parcels/other-1/owner",
        json={"farmer_id": "farmer-1"},
        headers=headers,
    ).status_code == 403


def test_farmer_can_only_view_owned_parcels(registry_client):
    client = registry_client
    headers = auth_headers("farmer-1", Role.farmer)

    listed = client.get(
        "/api/v1/parcels",
        headers=headers,
    )

    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [
        "owned-1"
    ]

    assert [
        item["id"]
        for item in client.get(
            "/api/v1/parcels?search=owned",
            headers=headers,
        ).json()
    ] == ["owned-1"]

    assert client.get(
        "/api/v1/parcels?search=OTHER",
        headers=headers,
    ).json() == []

    assert client.get(
        "/api/v1/parcels?search=%25",
        headers=headers,
    ).json() == []

    assert client.get(
        "/api/v1/parcels/owned-1",
        headers=headers,
    ).status_code == 200

    assert client.get(
        "/api/v1/parcels/other-1",
        headers=headers,
    ).status_code == 404

    assert client.get(
        "/api/v1/parcels/legacy-1",
        headers=headers,
    ).status_code == 404


# --------------------------------------------------
# Admin read access and ownership assignment
# --------------------------------------------------

def test_admin_registry_and_owner_assignment(registry_client):
    client = registry_client

    admin = auth_headers("admin-1", Role.admin)
    farmer = auth_headers("farmer-1", Role.farmer)

    response = client.get(
        "/api/v1/parcels?limit=1&offset=0",
        headers=admin,
    )

    assert response.status_code == 200
    assert len(response.json()) == 1

    farmers = client.get(
        "/api/v1/users/farmers",
        headers=admin,
    )

    assert farmers.status_code == 200

    assert [
        item["email"]
        for item in farmers.json()
    ] == [
        "farmer@example.com",
        "other@example.com",
    ]

    assert client.get(
        "/api/v1/users/farmers",
        headers=farmer,
    ).status_code == 403

    assert client.patch(
        "/api/v1/parcels/other-1/owner",
        json={"farmer_id": "missing"},
        headers=admin,
    ).status_code == 422

    assigned = client.patch(
        "/api/v1/parcels/other-1/owner",
        json={"farmer_id": "farmer-1"},
        headers=admin,
    )

    assert assigned.status_code == 200
    assert assigned.json()["farmer_id"] == "farmer-1"

    assert client.get(
        "/api/v1/parcels/other-1",
        headers=farmer,
    ).status_code == 200


# --------------------------------------------------
# Admin parcel editing
# --------------------------------------------------

def test_admin_can_update_parcel_area(registry_client):
    client = registry_client
    headers = auth_headers("admin-1", Role.admin)

    response = client.patch(
        "/api/v1/parcels/owned-1",
        json={"area_hectares": "2.5000"},
        headers=headers,
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert float(data["area_hectares"]) == 2.5
    assert data["farmer_id"] == "farmer-1"
    assert data["external_id"] == "OWNED"

    persisted = client.get(
        "/api/v1/parcels/owned-1",
        headers=headers,
    )

    assert persisted.status_code == 200
    assert float(persisted.json()["area_hectares"]) == 2.5


def test_admin_can_update_parcel_reference(registry_client):
    client = registry_client
    headers = auth_headers("admin-1", Role.admin)

    response = client.patch(
        "/api/v1/parcels/owned-1",
        json={"external_id": "UPDATED-PARCEL"},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["external_id"] == "UPDATED-PARCEL"
    assert response.json()["id"] == "owned-1"


def test_admin_can_update_village(registry_client):
    client = registry_client
    headers = auth_headers("admin-1", Role.admin)

    response = client.patch(
        "/api/v1/parcels/owned-1",
        json={"village_code": "v2"},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["village_code"] == "v2"


# --------------------------------------------------
# GIS Operator editing
# --------------------------------------------------

def test_gis_operator_can_update_parcel(registry_client):
    client = registry_client
    headers = auth_headers("gis-1", Role.gis_operator)

    response = client.patch(
        "/api/v1/parcels/owned-1",
        json={"area_hectares": "4.2500"},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert float(response.json()["area_hectares"]) == 4.25


# --------------------------------------------------
# Invalid updates
# --------------------------------------------------

@pytest.mark.parametrize(
    "area",
    [0, -1, "1.12345"],
)
def test_invalid_area_rejected(registry_client, area):
    client = registry_client
    headers = auth_headers("admin-1", Role.admin)

    response = client.patch(
        "/api/v1/parcels/owned-1",
        json={"area_hectares": area},
        headers=headers,
    )

    assert response.status_code == 422


def test_unknown_village_rejected(registry_client):
    client = registry_client
    headers = auth_headers("admin-1", Role.admin)

    response = client.patch(
        "/api/v1/parcels/owned-1",
        json={"village_code": "unknown-village"},
        headers=headers,
    )

    assert response.status_code == 422


def test_duplicate_parcel_reference_rejected(registry_client):
    client = registry_client
    headers = auth_headers("admin-1", Role.admin)

    response = client.patch(
        "/api/v1/parcels/owned-1",
        json={"external_id": "OTHER"},
        headers=headers,
    )

    assert response.status_code == 409

    # The original reference must remain unchanged.
    persisted = client.get(
        "/api/v1/parcels/owned-1",
        headers=headers,
    )

    assert persisted.status_code == 200
    assert persisted.json()["external_id"] == "OWNED"


def test_missing_parcel_returns_404(registry_client):
    client = registry_client
    headers = auth_headers("admin-1", Role.admin)

    response = client.patch(
        "/api/v1/parcels/nonexistent",
        json={"area_hectares": "2.0000"},
        headers=headers,
    )

    assert response.status_code == 404


def test_empty_update_rejected(registry_client):
    client = registry_client
    headers = auth_headers("admin-1", Role.admin)

    response = client.patch(
        "/api/v1/parcels/owned-1",
        json={},
        headers=headers,
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "field",
    [
        "external_id",
        "village_code",
        "area_hectares",
    ],
)
def test_explicit_null_rejected(registry_client, field):
    client = registry_client
    headers = auth_headers("admin-1", Role.admin)

    response = client.patch(
        "/api/v1/parcels/owned-1",
        json={field: None},
        headers=headers,
    )

    assert response.status_code == 422


# --------------------------------------------------
# Protected fields
# --------------------------------------------------

def test_general_edit_preserves_ownership(registry_client):
    client = registry_client
    headers = auth_headers("admin-1", Role.admin)

    response = client.patch(
        "/api/v1/parcels/owned-1",
        json={
            "area_hectares": "6.0000",
            "farmer_id": "farmer-2",
        },
        headers=headers,
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert float(data["area_hectares"]) == 6
    assert data["farmer_id"] == "farmer-1"


def test_general_edit_preserves_record_id(registry_client):
    client = registry_client
    headers = auth_headers("admin-1", Role.admin)

    response = client.patch(
        "/api/v1/parcels/owned-1",
        json={
            "external_id": "NEW-REFERENCE",
            "id": "another-record",
        },
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["id"] == "owned-1"
