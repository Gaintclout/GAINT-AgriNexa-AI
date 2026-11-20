from datetime import datetime, timedelta, timezone
import pytest
from app.scim_jobs import JobRecord, JobStatus, transition_job

NOW = datetime(2026, 11, 1, tzinfo=timezone.utc)

def job(status=JobStatus.planned):
    return JobRecord(job_id="job-1", parcel_id="parcel-1",
                     scene_id="scene-1", status=status, updated_at=NOW)

def test_valid_lifecycle():
    queued = transition_job(job(), JobStatus.queued, NOW)
    running = transition_job(queued, JobStatus.running, NOW)
    finished = transition_job(running, JobStatus.succeeded, NOW)
    assert finished.status == JobStatus.succeeded
    assert job().status == JobStatus.planned

@pytest.mark.parametrize("current,target", [
    (JobStatus.planned, JobStatus.running),
    (JobStatus.queued, JobStatus.succeeded),
    (JobStatus.succeeded, JobStatus.queued),
    (JobStatus.failed, JobStatus.running),
    (JobStatus.cancelled, JobStatus.queued),
])
def test_invalid_transition_rejected(current, target):
    with pytest.raises(ValueError):
        transition_job(job(current), target, NOW)

def test_timestamp_cannot_move_backward():
    with pytest.raises(ValueError):
        transition_job(job(), JobStatus.queued, NOW - timedelta(seconds=1))

def test_cannot_cancel_running_job():
    with pytest.raises(ValueError):
        transition_job(job(JobStatus.running), JobStatus.cancelled, NOW)
