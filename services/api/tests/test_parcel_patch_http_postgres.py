"""AG-11G: Real PostgreSQL HTTP parcel PATCH integration.

Safety:
- Uses only AGRINEXA_TEST_DATABASE_URL.
- Requires the existing guarded disposable database.
- All test data rolls back after each test.
- Never uses the application's development DATABASE_URL.
"""

import os
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import app
from app.models import District, Mandal, Parcel, State, User, Village
from app.security import Role, create_access_token
from db_safety import create_guarded_test_engine


@pytest.fixture(autouse=True)
def test_jwt_secret(monkeypatch):
    monkeypatch.setenv(
        "AGRINEXA_JWT_SECRET",
        "test-only-32-character-secret-for-ci-12345",
    )


@pytest.fixture
def pg_http():
    url = os.getenv("AGRINEXA_TEST_DATABASE_URL")

    if not url:
        pytest.skip("Disposable PostgreSQL test database not configured")

    engine = create_guarded_test_engine(
        url,
        pool_pre_ping=True,
    )

    previous_override = app.dependency_overrides.get(get_db)

    try:
        with engine.connect() as conn:
            outer_transaction = conn.begin()

            try:
                with Session(
                    bind=conn,
                    join_transaction_mode="create_savepoint",
                    expire_on_commit=False,
                ) as db:

                    key = uuid4().hex[:12]

                    state_code = "S" + key
                    district_code = "D" + key
                    mandal_code = "M" + key
                    village_one = "V1" + key
                    village_two = "V2" + key

                    admin_id = str(uuid4())
                    farmer_id = str(uuid4())
                    parcel_id = str(uuid4())
                    second_id = str(uuid4())

                    first_external = "HTTP-A-" + key
                    second_external = "HTTP-B-" + key

                    db.add(
                        State(
                            code=state_code,
                            name="HTTP Test State",
                        )
                    )
                    db.flush()

                    db.add(
                        District(
                            code=district_code,
                            name="HTTP Test District",
                            state_code=state_code,
                        )
                    )
                    db.flush()

                    db.add(
                        Mandal(
                            code=mandal_code,
                            name="HTTP Test Mandal",
                            district_code=district_code,
                        )
                    )
                    db.flush()

                    db.add_all([
                        Village(
                            code=village_one,
                            name="HTTP Village One",
                            district_code=district_code,
                            mandal_code=mandal_code,
                        ),
                        Village(
                            code=village_two,
                            name="HTTP Village Two",
                            district_code=district_code,
                            mandal_code=mandal_code,
                        ),
                    ])
                    db.flush()

                    db.add_all([
                        User(
                            id=admin_id,
                            email=f"admin-{key}@example.com",
                            password_hash="test-hash",
                            role="admin",
                            is_active=True,
                        ),
                        User(
                            id=farmer_id,
                            email=f"farmer-{key}@example.com",
                            password_hash="test-hash",
                            role="farmer",
                            is_active=True,
                        ),
                    ])
                    db.flush()

                    db.add_all([
                        Parcel(
                            id=parcel_id,
                            external_id=first_external,
                            village_code=village_one,
                            farmer_id=farmer_id,
                            area_hectares=Decimal("1.0000"),
                        ),
                        Parcel(
                            id=second_id,
                            external_id=second_external,
                            village_code=village_one,
                            area_hectares=Decimal("2.0000"),
                        ),
                    ])
                    db.flush()

                    geometry = """
                    {
                      "type": "MultiPolygon",
                      "coordinates": [
                        [
                          [
                            [78.0, 17.0],
                            [78.01, 17.0],
                            [78.01, 17.01],
                            [78.0, 17.0]
                          ]
                        ]
                      ]
                    }
                    """

                    db.execute(
                        text("""
                            UPDATE parcels
                            SET geom = ST_SetSRID(
                                ST_GeomFromGeoJSON(:geometry),
                                4326
                            )
                            WHERE id = :parcel_id
                        """),
                        {
                            "geometry": geometry,
                            "parcel_id": parcel_id,
                        },
                    )
                    db.flush()

                    # Commit only the seed session's SAVEPOINT, not the
                    # outer PostgreSQL transaction. Fixture rows remain
                    # visible to request sessions on this connection.
                    db.commit()
                    db.expire_all()

                    # Each HTTP request must own its own session/savepoint.
                    # A 409 IntegrityError rollback must not erase the seed.
                    def override_db():
                        with Session(
                            bind=conn,
                            join_transaction_mode="create_savepoint",
                            expire_on_commit=False,
                        ) as request_db:
                            yield request_db

                    app.dependency_overrides[get_db] = override_db

                    headers = {
                        "Authorization": "Bearer " +
                        create_access_token(admin_id, Role.admin)
                    }

                    with TestClient(app) as client:
                        yield {
                            "client": client,
                            "db": db,
                            "headers": headers,
                            "parcel_id": parcel_id,
                            "second_id": second_id,
                            "farmer_id": farmer_id,
                            "first_external": first_external,
                            "second_external": second_external,
                            "village_one": village_one,
                            "village_two": village_two,
                        }

            finally:
                outer_transaction.rollback()

    finally:
        if previous_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous_override

        engine.dispose()


def test_http_patch_area_persists(pg_http):
    ctx = pg_http

    response = ctx["client"].patch(
        f'/api/v1/parcels/{ctx["parcel_id"]}',
        json={"area_hectares": "4.2500"},
        headers=ctx["headers"],
    )

    assert response.status_code == 200, response.text
    assert float(response.json()["area_hectares"]) == 4.25

    ctx["db"].expire_all()

    persisted = ctx["db"].get(Parcel, ctx["parcel_id"])

    assert persisted.area_hectares == Decimal("4.2500")


def test_http_patch_external_id_persists(pg_http):
    ctx = pg_http
    updated_external = "HTTP-UPDATED-" + uuid4().hex[:10]

    response = ctx["client"].patch(
        f'/api/v1/parcels/{ctx["parcel_id"]}',
        json={"external_id": updated_external},
        headers=ctx["headers"],
    )

    assert response.status_code == 200, response.text

    ctx["db"].expire_all()

    persisted = ctx["db"].get(Parcel, ctx["parcel_id"])

    assert persisted.external_id == updated_external


def test_http_patch_village_persists(pg_http):
    ctx = pg_http

    response = ctx["client"].patch(
        f'/api/v1/parcels/{ctx["parcel_id"]}',
        json={"village_code": ctx["village_two"]},
        headers=ctx["headers"],
    )

    assert response.status_code == 200, response.text

    ctx["db"].expire_all()

    persisted = ctx["db"].get(Parcel, ctx["parcel_id"])

    assert persisted.village_code == ctx["village_two"]


def test_http_patch_preserves_geometry(pg_http):
    ctx = pg_http
    db = ctx["db"]

    before = db.execute(
        text("""
            SELECT ST_AsEWKB(geom)
            FROM parcels
            WHERE id = :id
        """),
        {"id": ctx["parcel_id"]},
    ).scalar_one()

    response = ctx["client"].patch(
        f'/api/v1/parcels/{ctx["parcel_id"]}',
        json={"area_hectares": "6.0000"},
        headers=ctx["headers"],
    )

    assert response.status_code == 200, response.text

    after = db.execute(
        text("""
            SELECT ST_AsEWKB(geom)
            FROM parcels
            WHERE id = :id
        """),
        {"id": ctx["parcel_id"]},
    ).scalar_one()

    assert before is not None
    assert before == after


def test_http_patch_preserves_farmer_owner(pg_http):
    ctx = pg_http

    response = ctx["client"].patch(
        f'/api/v1/parcels/{ctx["parcel_id"]}',
        json={
            "area_hectares": "7.0000",
            "farmer_id": str(uuid4()),
        },
        headers=ctx["headers"],
    )

    assert response.status_code == 200, response.text

    ctx["db"].expire_all()

    persisted = ctx["db"].get(Parcel, ctx["parcel_id"])

    assert persisted.farmer_id == ctx["farmer_id"]


def test_http_patch_duplicate_reference_returns_409(pg_http):
    ctx = pg_http

    response = ctx["client"].patch(
        f'/api/v1/parcels/{ctx["parcel_id"]}',
        json={"external_id": ctx["second_external"]},
        headers=ctx["headers"],
    )

    assert response.status_code == 409, response.text

    # The rejected request must not change or remove either parcel.
    ctx["db"].expire_all()
    persisted = ctx["db"].get(Parcel, ctx["parcel_id"])
    other = ctx["db"].get(Parcel, ctx["second_id"])

    assert persisted is not None, "Original parcel disappeared after 409"
    assert other is not None, "Conflicting parcel disappeared after 409"
    assert persisted.external_id == ctx["first_external"]
    assert other.external_id == ctx["second_external"]


def test_http_patch_invalid_village_returns_422(pg_http):
    ctx = pg_http

    response = ctx["client"].patch(
        f'/api/v1/parcels/{ctx["parcel_id"]}',
        json={"village_code": "UNKNOWN-VILLAGE"},
        headers=ctx["headers"],
    )

    assert response.status_code == 422, response.text


def test_http_patch_missing_parcel_returns_404(pg_http):
    ctx = pg_http

    response = ctx["client"].patch(
        f'/api/v1/parcels/{uuid4()}',
        json={"area_hectares": "3.0000"},
        headers=ctx["headers"],
    )

    assert response.status_code == 404, response.text
