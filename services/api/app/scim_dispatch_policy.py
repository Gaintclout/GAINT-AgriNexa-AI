"""SCIM worker-dispatch eligibility policy; does not dispatch jobs."""
from .scim_jobs import JobStatus

def can_enqueue(status: JobStatus) -> bool:
    """Only planned jobs are eligible to be queued."""
    return status is JobStatus.planned

def can_claim(status: JobStatus) -> bool:
    """Only queued jobs may be claimed by a worker."""
    return status is JobStatus.queued
