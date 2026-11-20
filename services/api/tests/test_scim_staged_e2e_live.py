"""Disposable PostGIS + synthetic GeoTIFF SCIM end-to-end test."""
import os
from datetime import datetime, timezone
from uuid import uuid4
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from sqlalchemy import delete, text
from sqlalchemy.orm import Session
from app.models import State, District, Mandal, Village, Parcel
from app.scim_job_models import ScimProcessingJob
from app.scim_result_models import ScimProcessingResult
from app.scim_lease_store import claim_with_lease
from app.scim_staged_worker import process_staged_job
from db_safety import create_guarded_test_engine

@pytest.mark.skipif(not os.getenv("AGRINEXA_TEST_DATABASE_URL"),
                    reason="Requires disposable PostGIS test database")
def test_offline_staged_scene_end_to_end(tmp_path):
    engine = create_guarded_test_engine(os.environ["AGRINEXA_TEST_DATABASE_URL"])
    key = uuid4().hex
    s, d, m, v = ("S"+key, "D"+key, "M"+key, "V"+key)
    parcel_id, job_id = str(uuid4()), str(uuid4())
    bands = {"SR_B4": 10000, "SR_B5": 20000, "SR_B3": 15000, "SR_B6": 12000}
    def write(name, array):
        with rasterio.open(tmp_path / name, "w", driver="GTiff", count=1,
                height=2, width=2, dtype="uint16", crs="EPSG:4326",
                transform=from_origin(80, 20, .01, .01), nodata=0) as dst:
            dst.write(array.astype("uint16"), 1)
    write("qa.tif", np.array([[64, 8], [64, 64]]))
    for band, dn in bands.items():
        write(band+".tif", np.full((2, 2), dn))
    try:
        with Session(engine) as db, db.begin():
            db.add(State(code=s, name="SCIM End-to-end State"))
            db.flush()
            db.add(District(code=d, name="SCIM District", state_code=s))
            db.flush()
            db.add(Mandal(code=m, name="SCIM Mandal", district_code=d))
            db.flush()
            db.add(Village(code=v, name="SCIM Village", district_code=d, mandal_code=m))
            db.flush()
            db.add(Parcel(id=parcel_id, external_id=key, village_code=v, area_hectares=1))
            db.flush()
            db.execute(text("""UPDATE parcels SET geom = ST_Multi(
                ST_GeomFromText('POLYGON((80 20,80.02 20,80.02 19.99,80 19.99,80 20))',4326))
                WHERE id = :id"""), {"id": parcel_id})
            now = datetime.now(timezone.utc)
            db.add(ScimProcessingJob(id=job_id, parcel_id=parcel_id, scene_id="e2e-"+key,
                provider="landsat-8", status="queued", created_at=now, updated_at=now))
        with Session(engine) as db:
            claimed = claim_with_lease(db, "scim-ci")
            assert claimed is not None and claimed[0] == job_id
        summary = process_staged_job(lambda: Session(engine), job_id, "scim-ci",
            claimed[1], tmp_path, "qa.tif",
            {band: band+".tif" for band in bands})
        assert summary["parcel_pixels"] == 2
        assert summary["valid_pixels"] == 1
        assert summary["ndvi_median"] == pytest.approx(.647059, abs=1e-6)
        with Session(engine) as db:
            assert db.get(ScimProcessingJob, job_id).status == "succeeded"
            assert db.get(ScimProcessingResult, job_id).summary == summary
    finally:
        try:
            with Session(engine) as db, db.begin():
                db.execute(delete(ScimProcessingResult).where(ScimProcessingResult.job_id == job_id))
                db.execute(delete(ScimProcessingJob).where(ScimProcessingJob.id == job_id))
                db.execute(delete(Parcel).where(Parcel.id == parcel_id))
                db.execute(delete(Village).where(Village.code == v))
                db.execute(delete(Mandal).where(Mandal.code == m))
                db.execute(delete(District).where(District.code == d))
                db.execute(delete(State).where(State.code == s))
        finally:
            engine.dispose()
