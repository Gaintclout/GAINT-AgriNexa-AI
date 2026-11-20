"""SCIM schema verification on the disposable PostGIS CI database."""
import os
import pytest
from sqlalchemy import inspect
from db_safety import create_guarded_test_engine

@pytest.mark.skipif(not os.getenv("AGRINEXA_TEST_DATABASE_URL"), reason="Requires disposable PostGIS test DB")
def test_scim_job_migration_applied():
    engine = create_guarded_test_engine(os.environ["AGRINEXA_TEST_DATABASE_URL"])
    try:
        inspector = inspect(engine)
        constraints = inspector.get_unique_constraints("scim_processing_jobs")
        assert any(c["name"] == "uq_scim_job_parcel_scene_provider" for c in constraints)
        checks = inspector.get_check_constraints("scim_processing_jobs")
        assert any(c["name"] == "ck_scim_job_status" for c in checks)
        assert any(c["name"] == "ck_scim_job_attempt_count" for c in checks)
        assert any(c["name"] == "ck_scim_job_lease_consistency" for c in checks)
        assert "scim_processing_results" in inspector.get_table_names()
        result_columns = {column["name"] for column in inspector.get_columns("scim_processing_results")}
        assert {"job_id", "summary", "created_at"} <= result_columns
        columns = {column["name"] for column in inspector.get_columns("scim_processing_jobs")}
        assert {"id", "parcel_id", "scene_id", "provider", "status", "created_at", "updated_at", "attempt_count", "lease_owner", "lease_token", "lease_expires_at"} <= columns
    finally:
        engine.dispose()

@pytest.mark.skipif(not os.getenv("AGRINEXA_TEST_DATABASE_URL"), reason="Requires disposable PostGIS test DB")
def test_scim_job_lifecycle_roundtrip():
    from datetime import datetime, timezone
    from uuid import uuid4
    from sqlalchemy.orm import Session
    from app.models import State, District, Mandal, Village, Parcel
    from app.scim_plan import PlanRequest
    from app.scim_job_store import create_planned_job, change_job_status, get_job, list_jobs, claim_next_queued_job, queue_planned_job
    from app.scim_jobs import JobStatus
    from app.scim_job_models import ScimProcessingJob
    from app.scim_lease_recovery import recover_expired_leases
    from datetime import timedelta
    from app.scim_lease_store import claim_with_lease, complete_with_lease, renew_lease
    engine = create_guarded_test_engine(os.environ["AGRINEXA_TEST_DATABASE_URL"])
    key = uuid4().hex
    parcel_id = str(uuid4())
    try:
        with engine.connect() as conn:
            outer = conn.begin()
            try:
                with Session(bind=conn, join_transaction_mode="create_savepoint") as db, db.begin():
                    db.add(State(code="S"+key, name="SCIM State"))
                    db.flush()
                    db.add(District(code="D"+key, name="SCIM District", state_code="S"+key))
                    db.flush()
                    db.add(Mandal(code="M"+key, name="SCIM Mandal", district_code="D"+key))
                    db.flush()
                    db.add(Village(code="V"+key, name="SCIM Village",
                                   district_code="D"+key, mandal_code="M"+key))
                    db.flush()
                    db.add(Parcel(id=parcel_id, external_id=key, village_code="V"+key, area_hectares=1))
                    db.flush()
                request = PlanRequest(
                    provider="sentinel-2", parcel_id=parcel_id, scene_id="scene-"+key,
                    captured_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
                    available_bands=["red", "green", "nir", "swir16"],
                    cloud_cover_percent=12)
                with Session(bind=conn, join_transaction_mode="create_savepoint") as db:
                    created_job, created = create_planned_job(db, request)
                    job_id = created_job.id
                    assert created and created_job.status == "planned"
                with Session(bind=conn, join_transaction_mode="create_savepoint") as db:
                    repeated, created = create_planned_job(db, request)
                    assert not created and repeated.id == job_id
                with Session(bind=conn, join_transaction_mode="create_savepoint") as db:
                    assert get_job(db, job_id) is not None
                    assert any(j.id == job_id for j in list_jobs(db, parcel_id=parcel_id))
                    assert any(j.id == job_id for j in list_jobs(db, status=JobStatus.planned))
                with Session(bind=conn, join_transaction_mode="create_savepoint") as db:
                    cancelled = change_job_status(db, job_id, JobStatus.cancelled)
                    assert cancelled.status == "cancelled"
                with Session(bind=conn, join_transaction_mode="create_savepoint") as db:
                    assert not any(j.id == job_id for j in list_jobs(db, status=JobStatus.planned))
                with Session(bind=conn, join_transaction_mode="create_savepoint") as db:
                    with pytest.raises(ValueError, match="Invalid job status transition"):
                        change_job_status(db, job_id, JobStatus.queued)
                with Session(bind=conn, join_transaction_mode="create_savepoint") as db:
                    assert get_job(db, job_id).status == "cancelled"
                    assert [j.id for j in list_jobs(db, parcel_id=parcel_id, status=JobStatus.cancelled)] == [job_id]
                    assert list_jobs(db, parcel_id=parcel_id, limit=1, offset=1) == []
                # A second scene exercises queue -> atomic claim -> running.
                second = request.model_copy(update={"scene_id": "claim-"+key})
                with Session(bind=conn, join_transaction_mode="create_savepoint") as db:
                    pending, created = create_planned_job(db, second)
                    assert created
                    second_id = pending.id
                with Session(bind=conn, join_transaction_mode="create_savepoint") as db:
                    queued = queue_planned_job(db, second_id)
                    assert queued.status == "queued"
                with Session(bind=conn, join_transaction_mode="create_savepoint") as db:
                    with pytest.raises(ValueError, match="Invalid job status transition"):
                        queue_planned_job(db, second_id)
                with Session(bind=conn, join_transaction_mode="create_savepoint") as db:
                    claimed = claim_with_lease(db, "ci-worker")
                    assert claimed is not None
                    assert claimed[0] == second_id
                with Session(bind=conn, join_transaction_mode="create_savepoint") as db:
                    assert claim_with_lease(db, "ci-worker-2") is None
                with Session(bind=conn, join_transaction_mode="create_savepoint") as db:
                    assert get_job(db, second_id).status == "running"
                with Session(bind=conn, join_transaction_mode="create_savepoint") as db:
                    with pytest.raises(ValueError, match="Invalid or expired lease"):
                        complete_with_lease(db, second_id, "ci-worker", "wrong-token", True)
                with Session(bind=conn, join_transaction_mode="create_savepoint") as db:
                    with pytest.raises(ValueError, match="Invalid or expired lease"):
                        renew_lease(db, second_id, "ci-worker", "wrong-token")
                with Session(bind=conn, join_transaction_mode="create_savepoint") as db:
                    previous = get_job(db, second_id).lease_expires_at
                with Session(bind=conn, join_transaction_mode="create_savepoint") as db:
                    renewed = renew_lease(db, second_id, "ci-worker", claimed[1])
                    assert renewed >= previous
                with Session(bind=conn, join_transaction_mode="create_savepoint") as db:
                    with pytest.raises(ValueError, match="lease-aware"):
                        change_job_status(db, second_id, JobStatus.succeeded)
                with Session(bind=conn, join_transaction_mode="create_savepoint") as db, db.begin():
                    db.get(ScimProcessingJob, second_id).lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
                with Session(bind=conn, join_transaction_mode="create_savepoint") as db:
                    assert recover_expired_leases(db) == (1, 0)
                with Session(bind=conn, join_transaction_mode="create_savepoint") as db:
                    with pytest.raises(ValueError, match="Invalid or expired lease"):
                        complete_with_lease(db, second_id, "ci-worker", claimed[1], True)
                with Session(bind=conn, join_transaction_mode="create_savepoint") as db:
                    retry = claim_with_lease(db, "ci-worker-retry")
                    assert retry is not None and retry[0] == second_id and retry[1] != claimed[1]
                with Session(bind=conn, join_transaction_mode="create_savepoint") as db:
                    completed = complete_with_lease(db, second_id, "ci-worker-retry", retry[1], True)
                    assert completed.status == "succeeded"
            finally:
                outer.rollback()
    finally:
        engine.dispose()
