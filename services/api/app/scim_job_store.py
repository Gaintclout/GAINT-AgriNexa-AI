"""Transactional SCIM job metadata operations; no worker or asset download."""
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from .models import Parcel
from .scim_job_models import ScimProcessingJob
from .scim_jobs import JobRecord, JobStatus, transition_job
from .scim_plan import PlanRequest

def create_planned_job(db: Session, request: PlanRequest) -> tuple[ScimProcessingJob, bool]:
    """Idempotent by parcel, scene and provider; DB uniqueness handles concurrent requests."""
    with db.begin():
        if db.get(Parcel, request.parcel_id) is None:
            raise LookupError("Parcel not found")
        query = select(ScimProcessingJob).where(
            ScimProcessingJob.parcel_id == request.parcel_id,
            ScimProcessingJob.scene_id == request.scene_id,
            ScimProcessingJob.provider == request.provider.value,
        )
        existing = db.scalar(query)
        if existing is not None:
            return existing, False
        statement = insert(ScimProcessingJob).values(
            id=str(uuid4()),
            parcel_id=request.parcel_id, scene_id=request.scene_id,
            provider=request.provider.value, status=JobStatus.planned.value,
            created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
        ).on_conflict_do_nothing(constraint="uq_scim_job_parcel_scene_provider").returning(ScimProcessingJob.id)
        inserted_id = db.scalar(statement)
        job = db.get(ScimProcessingJob, inserted_id) if inserted_id else db.scalar(query)
        return job, inserted_id is not None

def change_job_status(db: Session, job_id: str, target: JobStatus) -> ScimProcessingJob:
    """Lock the row and apply the lifecycle contract atomically."""
    with db.begin():
        job = db.scalar(select(ScimProcessingJob).where(
            ScimProcessingJob.id == job_id).with_for_update())
        if job is None:
            raise LookupError("Job not found")
        if job.status == JobStatus.running.value or target == JobStatus.running:
            raise ValueError("Running jobs require lease-aware operations")
        current = JobRecord(job_id=job.id, parcel_id=job.parcel_id,
                            scene_id=job.scene_id, status=JobStatus(job.status),
                            updated_at=job.updated_at)
        updated = transition_job(current, target, datetime.now(timezone.utc))
        job.status = updated.status.value
        job.updated_at = updated.updated_at
        db.flush()
        return job

def get_job(db: Session, job_id: str) -> ScimProcessingJob | None:
    """Read one job without modifying its state."""
    return db.get(ScimProcessingJob, job_id)

def list_jobs(db: Session, *, parcel_id: str | None = None,
              status: JobStatus | None = None, limit: int = 50,
              offset: int = 0) -> list[ScimProcessingJob]:
    """Stable newest-first pagination with optional parcel and status filters."""
    if not 1 <= limit <= 100 or offset < 0:
        raise ValueError("Invalid pagination")
    query = select(ScimProcessingJob)
    if parcel_id is not None:
        query = query.where(ScimProcessingJob.parcel_id == parcel_id)
    if status is not None:
        query = query.where(ScimProcessingJob.status == status.value)
    query = query.order_by(ScimProcessingJob.created_at.desc(),
                           ScimProcessingJob.id.desc()).limit(limit).offset(offset)
    return list(db.scalars(query))

def claim_next_queued_job(db: Session) -> ScimProcessingJob | None:
    """Legacy metadata-only claim is disabled; use claim_with_lease instead."""
    raise RuntimeError("Unsafe legacy claim disabled; use lease-aware claiming")

def queue_planned_job(db: Session, job_id: str) -> ScimProcessingJob:
    """Atomically mark a planned job queued; no broker message is sent.

    Row locking and the lifecycle validator reject duplicate or stale requests.
    """
    return change_job_status(db, job_id, JobStatus.queued)
