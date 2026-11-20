"""Live PostGIS round-trip test. Requires a dedicated disposable test database.

Set AGRINEXA_TEST_DATABASE_URL to opt in. Never point it at production.
"""
import os
from uuid import uuid4
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.models import District, Mandal, Parcel, State, Village
from app.boundary import normalize_boundary
from db_safety import create_guarded_test_engine

@pytest.mark.skipif(not os.getenv("AGRINEXA_TEST_DATABASE_URL"), reason="No disposable PostGIS test database configured")
def test_postgis_parcel_roundtrip():
    url = os.environ["AGRINEXA_TEST_DATABASE_URL"]
    assert url.startswith(("postgresql://", "postgresql+psycopg://"))
    engine = create_guarded_test_engine(url, pool_pre_ping=True)
    key = uuid4().hex
    state_code, district_code, mandal_code, village_code = [prefix + key for prefix in ("S", "D", "M", "V")]
    parcel_id = str(uuid4())
    boundary = normalize_boundary({"type": "Polygon", "coordinates": [
        [[78.0, 17.0], [78.01, 17.0], [78.01, 17.01], [78.0, 17.0]]
    ]})
    import json
    try:
        # Single transaction rolls back all test data; no production data is modified.
        with engine.connect() as conn:
            transaction = conn.begin()
            try:
                with Session(bind=conn, join_transaction_mode="create_savepoint") as db:
                    db.add(State(code=state_code, name="Integration Test State"))
                    db.flush()
                    db.add(District(code=district_code, name="Integration Test District", state_code=state_code))
                    db.flush()
                    db.add(Mandal(code=mandal_code, name="Integration Test Mandal", district_code=district_code))
                    db.flush()
                    db.add(Village(code=village_code, name="Integration Test Village", district_code=district_code, mandal_code=mandal_code))
                    db.flush()
                    db.add(Parcel(id=parcel_id, external_id=key, village_code=village_code, area_hectares=1))
                    db.flush()
                    geometry = json.dumps(boundary)
                    assert db.execute(text("SELECT ST_IsValid(ST_GeomFromGeoJSON(:geometry))"), {"geometry": geometry}).scalar_one()
                    db.execute(text("UPDATE parcels SET geom = ST_SetSRID(ST_GeomFromGeoJSON(:geometry),4326) WHERE id = :id"), {"geometry": geometry, "id": parcel_id})
                    found = db.execute(text("""SELECT ST_AsGeoJSON(geom) FROM parcels
                        WHERE id = :id AND ST_Intersects(geom, ST_MakeEnvelope(77.9,16.9,78.1,17.1,4326))"""), {"id": parcel_id}).scalar_one()
                    assert json.loads(found)["type"] == "MultiPolygon"
            finally:
                transaction.rollback()
    finally:
        engine.dispose()
