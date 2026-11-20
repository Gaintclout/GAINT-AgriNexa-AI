"""SCIM processing job lifecycle contracts.

Pure state transitions only; persistence and execution are separate concerns.
"""
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field, model_validator

class JobStatus(str, Enum):
    planned = "planned"
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"

ALLOWED = {
    JobStatus.planned: {JobStatus.queued, JobStatus.cancelled},
    JobStatus.queued: {JobStatus.running, JobStatus.cancelled},
    JobStatus.running: {JobStatus.succeeded, JobStatus.failed},
    JobStatus.succeeded: set(),
    JobStatus.failed: set(),
    JobStatus.cancelled: set(),
}

class JobRecord(BaseModel):
    job_id: str = Field(min_length=1, max_length=36)
    parcel_id: str = Field(min_length=1, max_length=128)
    scene_id: str = Field(min_length=1, max_length=200)
    status: JobStatus = JobStatus.planned
    updated_at: datetime

    @model_validator(mode="after")
    def validate_timestamp(self):
        if self.updated_at.tzinfo is None or self.updated_at.utcoffset() is None:
            raise ValueError("Job timestamp requires timezone")
        return self

def transition_job(job: JobRecord, target: JobStatus, at: datetime) -> JobRecord:
    if target not in ALLOWED[job.status]:
        raise ValueError("Invalid job status transition")
    if at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("Transition timestamp requires timezone")
    if at.astimezone(timezone.utc) < job.updated_at.astimezone(timezone.utc):
        raise ValueError("Transition cannot precede previous update")
    return job.model_copy(update={"status": target, "updated_at": at})
