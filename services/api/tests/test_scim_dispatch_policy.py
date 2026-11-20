"""Dispatch policy unit tests; no queue or database required."""
import pytest
from app.scim_jobs import JobStatus
from app.scim_dispatch_policy import can_enqueue, can_claim

@pytest.mark.parametrize("status", list(JobStatus))
def test_only_planned_jobs_can_enqueue(status):
    assert can_enqueue(status) == (status == JobStatus.planned)

@pytest.mark.parametrize("status", list(JobStatus))
def test_only_queued_jobs_can_be_claimed(status):
    assert can_claim(status) == (status == JobStatus.queued)
