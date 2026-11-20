"""Real two-connection lease claim race on disposable PostGIS CI database."""
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from datetime import datetime, timezone
from uuid import uuid4
import pytest
from sqlalchemy import delete
from sqlalchemy.orm import Session
from app.models import State, District, Mandal, Village, Parcel
from app.scim_job_models import ScimProcessingJob
from app.scim_lease_store import claim_with_lease
from db_safety import create_guarded_test_engine

@pytest.mark.skipif(not os.getenv("AGRINEXA_TEST_DATABASE_URL"),
                    reason="Requires disposable PostGIS test database")
def test_two_connections_cannot_claim_same_job():
    engine = create_guarded_test_engine(os.environ["AGRINEXA_TEST_DATABASE_URL"], pool_size=3)
    key = uuid4().hex
    s, d, m, v = ("S"+key, "D"+key, "M"+key, "V"+key)
    parcel_id, job_id = str(uuid4()), str(uuid4())
    try:
        with Session(engine) as db, db.begin():
            db.add(State(code=s, name="SCIM Concurrency State"))
            db.flush()
            db.add(District(code=d, name="SCIM District", state_code=s))
            db.flush()
            db.add(Mandal(code=m, name="SCIM Mandal", district_code=d))
            db.flush()
            db.add(Village(code=v, name="SCIM Village", district_code=d, mandal_code=m))
            db.flush()
            db.add(Parcel(id=parcel_id, external_id=key, village_code=v, area_hectares=1))
            db.flush()
            now = datetime.now(timezone.utc)
            db.add(ScimProcessingJob(id=job_id, parcel_id=parcel_id, scene_id="race-"+key,
                provider="sentinel-2", status="queued", created_at=now, updated_at=now))
        gate = Barrier(2)
        def attempt(owner):
            gate.wait(timeout=10)
            with Session(engine) as db:
                return claim_with_lease(db, owner)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(attempt, owner) for owner in ("worker-a", "worker-b")]
            results = [future.result(timeout=15) for future in futures]
        winners = [item for item in results if item is not None and item[0] == job_id]
        assert len(winners) == 1
        with Session(engine) as db:
            job = db.get(ScimProcessingJob, job_id)
            assert job.status == "running"
            assert job.attempt_count == 1
            assert job.lease_token == winners[0][1]
    finally:
        try:
            with Session(engine) as db, db.begin():
                db.execute(delete(ScimProcessingJob).where(ScimProcessingJob.id == job_id))
                db.execute(delete(Parcel).where(Parcel.id == parcel_id))
                db.execute(delete(Village).where(Village.code == v))
                db.execute(delete(Mandal).where(Mandal.code == m))
                db.execute(delete(District).where(District.code == d))
                db.execute(delete(State).where(State.code == s))
        finally:
            engine.dispose()
