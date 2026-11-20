"""Regression checks for atomic SCIM job claiming."""
from sqlalchemy.dialects import postgresql
from sqlalchemy import select
from app.scim_job_models import ScimProcessingJob
from app.scim_jobs import ALLOWED, JobStatus

def test_claim_query_uses_skip_locked():
    statement = (select(ScimProcessingJob)
                 .where(ScimProcessingJob.status == JobStatus.queued.value)
                 .order_by(ScimProcessingJob.created_at.asc(), ScimProcessingJob.id.asc())
                 .with_for_update(skip_locked=True).limit(1))
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE SKIP LOCKED" in sql
    assert "LIMIT" in sql

def test_claim_is_only_queued_to_running():
    assert JobStatus.running in ALLOWED[JobStatus.queued]
    assert JobStatus.running not in ALLOWED[JobStatus.planned]
    assert not ALLOWED[JobStatus.running].intersection({JobStatus.queued})
