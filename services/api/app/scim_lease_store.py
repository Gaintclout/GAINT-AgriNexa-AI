"""Lease-aware SCIM claims; no background execution."""
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.orm import Session
from .scim_job_models import ScimProcessingJob
from .scim_jobs import JobStatus
from .scim_lease_policy import LeasePolicy, make_lease

def claim_with_lease(db: Session, owner: str, policy: LeasePolicy | None = None):
    if not owner or not owner.strip() or len(owner) > 128:
        raise ValueError("Invalid worker owner")
    policy = policy or LeasePolicy()
    with db.begin():
        job = db.scalar(select(ScimProcessingJob)
            .where(ScimProcessingJob.status == JobStatus.queued.value)
            .where(ScimProcessingJob.attempt_count < policy.max_attempts)
            .order_by(ScimProcessingJob.created_at, ScimProcessingJob.id)
            .with_for_update(skip_locked=True).limit(1))
        if job is None:
            return None
        now = datetime.now(timezone.utc)
        lease = make_lease(now, job.attempt_count + 1, policy)
        job.status = JobStatus.running.value
        job.attempt_count = lease.attempt
        job.lease_owner = owner.strip()
        job.lease_token = str(uuid4())
        job.lease_expires_at = lease.expires_at
        job.updated_at = now
        db.flush()
        return job.id, job.lease_token

def complete_with_lease(db: Session, job_id: str, owner: str, token: str, success: bool):
    """Only the current unexpired lease holder may complete a running job."""
    with db.begin():
        job = db.scalar(select(ScimProcessingJob).where(
            ScimProcessingJob.id == job_id).with_for_update())
        if job is None:
            raise LookupError("Job not found")
        now = datetime.now(timezone.utc)
        if (job.status != JobStatus.running.value or
            not token or job.lease_token != token or
            job.lease_owner != owner or job.lease_expires_at is None or
            job.lease_expires_at <= now):
            raise ValueError("Invalid or expired lease")
        job.status = JobStatus.succeeded.value if success else JobStatus.failed.value
        job.lease_owner = None
        job.lease_token = None
        job.lease_expires_at = None
        job.updated_at = now
        db.flush()
        return job

def renew_lease(db: Session, job_id: str, owner: str, token: str,
                policy: LeasePolicy | None = None):
    """Extend an active lease; expired or mismatched tokens cannot revive it."""
    policy = policy or LeasePolicy()
    with db.begin():
        job = db.scalar(select(ScimProcessingJob).where(
            ScimProcessingJob.id == job_id).with_for_update())
        if job is None:
            raise LookupError("Job not found")
        now = datetime.now(timezone.utc)
        if (job.status != JobStatus.running.value or not token or
            job.lease_owner != owner or job.lease_token != token or
            job.lease_expires_at is None or job.lease_expires_at <= now):
            raise ValueError("Invalid or expired lease")
        proposed = make_lease(now, job.attempt_count, policy).expires_at
        job.lease_expires_at = max(job.lease_expires_at, proposed)
        job.updated_at = now
        db.flush()
        return job.lease_expires_at
