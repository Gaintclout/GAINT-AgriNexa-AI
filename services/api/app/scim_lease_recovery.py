"""Transactional recovery of expired SCIM leases; no scheduler is started."""
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from .scim_job_models import ScimProcessingJob
from .scim_jobs import JobStatus
from .scim_lease_policy import LeasePolicy

def recover_expired_leases(db: Session, policy: LeasePolicy | None = None,
                           limit: int = 50) -> tuple[int, int]:
    """Return (requeued, failed). Invalidate old tokens before retry."""
    if not 1 <= limit <= 100:
        raise ValueError("Recovery limit must be between 1 and 100")
    policy = policy or LeasePolicy()
    with db.begin():
        now = datetime.now(timezone.utc)
        jobs = list(db.scalars(
            select(ScimProcessingJob)
            .where(ScimProcessingJob.status == JobStatus.running.value)
            .where(ScimProcessingJob.lease_expires_at <= now)
            .order_by(ScimProcessingJob.lease_expires_at, ScimProcessingJob.id)
            .with_for_update(skip_locked=True).limit(limit)))
        requeued = failed = 0
        for job in jobs:
            if job.attempt_count >= policy.max_attempts:
                job.status = JobStatus.failed.value
                failed += 1
            else:
                job.status = JobStatus.queued.value
                requeued += 1
            job.lease_owner = None
            job.lease_token = None
            job.lease_expires_at = None
            job.updated_at = now
        db.flush()
        return requeued, failed
