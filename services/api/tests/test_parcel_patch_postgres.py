"""AG-11F: PostgreSQL parcel PATCH integration tests.

Uses only the guarded disposable agrinexa_test database.
All test records are created inside a transaction that is rolled back.
"""

import os
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import District, Mandal, Parcel, State, Village
from app.registry_router import ParcelUpdateInput, update_parcel
from db_safety import create_guarded_test_engine


TEST_URL_ENV = "AGRINEXA_TEST_DATABASE_URL"


@pytest.fixture
def parcel_database():
    url = os.getenv(TEST_URL_ENV)

    if not url:
        pytest.skip("Dedicated PostgreSQL test database not configured")

    engine = create_guarded_test_engine(
        url,
        pool_pre_ping=True,
    )

    try:
        with engine.connect() as connection:
            transaction = connection.begin()

            try:
                with Session(
                    bind=connection,
                    join_transaction_mode="create_savepoint",
                ) as db:

                    key = uuid4().hex[:12]

                    state_code = "S" + key
                    district_code = "D" + key
                    mandal_code = "M" + key
                    village_one = "V1" + key
                    village_two = "V2" + key

                    db.add(
                        State(
                            code=state_code,
                            name="Parcel Test State",
                        )
                    )
                    db.flush()

                    db.add(
                        District(
                            code=district_code,
                            name="Parcel Test District",
                            state_code=state_code,
                        )
                    )
                    db.flush()

                    db.add(
                        Mandal(
                            code=mandal_code,
                            name="Parcel Test Mandal",
                            district_code=district_code,
                        )
                    )
                    db.flush()

                    db.add_all([
                        Village(
                            code=village_one,
                            name="Parcel Test Village One",
                            district_code=district_code,
                            mandal_code=mandal_code,
                        ),
                        Village(
                            code=village_two,
                            name="Parcel Test Village Two",
                            district_code=district_code,
                            mandal_code=mandal_code,
                        ),
                    ])
                    db.flush()

                    first_id = str(uuid4())
                    second_id = str(uuid4())

                    first_external = "PATCH-A-" + key
                    second_external = "PATCH-B-" + key

                    db.add_all([
                        Parcel(
                            id=first_id,
                            external_id=first_external,
                            village_code=village_one,
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
                            [78.0,17.0],
                            [78.01,17.0],
                            [78.01,17.01],
                            [78.0,17.0]
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
                            "parcel_id": first_id,
                        },
                    )
                    db.flush()

                    yield {
                        "db": db,
                        "first_id": first_id,
                        "second_id": second_id,
                        "first_external": first_external,
                        "second_external": second_external,
                        "village_one": village_one,
                        "village_two": village_two,
                    }

            finally:
                transaction.rollback()

    finally:
        engine.dispose()


def test_postgres_parcel_area_persistence(parcel_database):
    data = parcel_database
    db = data["db"]

    parcel = db.get(Parcel, data["first_id"])
    parcel.area_hectares = Decimal("4.2500")
    db.flush()

    db.expire_all()

    persisted = db.get(Parcel, data["first_id"])

    assert persisted.area_hectares == Decimal("4.2500")


def test_postgres_external_id_update(parcel_database):
    data = parcel_database
    db = data["db"]

    parcel = db.get(Parcel, data["first_id"])
    parcel.external_id = "UPDATED-" + uuid4().hex[:12]

    db.flush()
    db.expire_all()

    persisted = db.get(Parcel, data["first_id"])

    assert persisted.external_id.startswith("UPDATED-")


def test_postgres_village_update(parcel_database):
    data = parcel_database
    db = data["db"]

    parcel = db.get(Parcel, data["first_id"])
    parcel.village_code = data["village_two"]

    db.flush()
    db.expire_all()

    persisted = db.get(Parcel, data["first_id"])

    assert persisted.village_code == data["village_two"]


def test_postgres_geometry_preserved(parcel_database):
    data = parcel_database
    db = data["db"]

    before = db.execute(
        text("""
            SELECT ST_AsEWKB(geom)
            FROM parcels
            WHERE id = :parcel_id
        """),
        {"parcel_id": data["first_id"]},
    ).scalar_one()

    parcel = db.get(Parcel, data["first_id"])
    parcel.area_hectares = Decimal("5.0000")

    db.flush()

    after = db.execute(
        text("""
            SELECT ST_AsEWKB(geom)
            FROM parcels
            WHERE id = :parcel_id
        """),
        {"parcel_id": data["first_id"]},
    ).scalar_one()

    assert before is not None
    assert before == after


def test_postgres_farmer_owner_unchanged(parcel_database):
    data = parcel_database
    db = data["db"]

    parcel = db.get(Parcel, data["first_id"])
    owner_before = parcel.farmer_id

    parcel.area_hectares = Decimal("7.0000")
    db.flush()

    db.expire_all()

    persisted = db.get(Parcel, data["first_id"])

    assert persisted.farmer_id == owner_before


def test_postgres_update_input_contract():
    payload = ParcelUpdateInput(
        external_id=" UPDATED-PARCEL ",
        area_hectares=Decimal("3.2500"),
    )

    assert payload.external_id == "UPDATED-PARCEL"
    assert payload.area_hectares == Decimal("3.2500")
