"""Pure worker-claim transition contract. No worker execution."""
from datetime import datetime
from .scim_jobs import JobRecord, JobStatus, transition_job

def claim_transition(job: JobRecord, at: datetime) -> JobRecord:
    """Only queued jobs can transition to running."""
    return transition_job(job, JobStatus.running, at)
