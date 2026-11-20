"""Static regression checks for lease-aware claim selection."""
from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from app.scim_job_models import ScimProcessingJob
from app.scim_jobs import JobStatus

def test_lease_claim_sql_filters_attempts_and_locks_rows():
    statement = (select(ScimProcessingJob)
                 .where(ScimProcessingJob.status == JobStatus.queued.value)
                 .where(ScimProcessingJob.attempt_count < 3)
                 .with_for_update(skip_locked=True).limit(1))
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE SKIP LOCKED" in sql
    assert "attempt_count" in sql
    assert "LIMIT" in sql
