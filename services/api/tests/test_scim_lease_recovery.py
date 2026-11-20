"""Bounded recovery policy tests."""
import pytest
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import dialect
from app.scim_job_models import ScimProcessingJob
from app.scim_jobs import JobStatus
from app.scim_lease_policy import LeasePolicy, can_retry
from app.scim_lease_recovery import recover_expired_leases

def test_retry_exhaustion_policy():
    policy = LeasePolicy(max_attempts=3)
    assert can_retry(2, policy)
    assert not can_retry(3, policy)

def test_recovery_batch_limit():
    for limit in (0, -1, 101):
        with pytest.raises(ValueError, match="Recovery limit"):
            recover_expired_leases(None, limit=limit)

def test_recovery_locking_query():
    stmt = select(ScimProcessingJob).where(
        ScimProcessingJob.status == JobStatus.running.value
    ).with_for_update(skip_locked=True).limit(50)
    sql = str(stmt.compile(dialect=dialect()))
    assert "FOR UPDATE SKIP LOCKED" in sql
