"""SCIM job endpoints and SQL construction regression checks."""
from sqlalchemy.dialects import postgresql
from app.main import app
from app.scim_job_models import ScimProcessingJob
from app.scim_jobs import JobStatus, ALLOWED

def test_job_routes_registered():
    paths = app.openapi()["paths"]
    assert "/api/v1/scim/jobs/plan" in paths
    assert "/api/v1/scim/jobs/{job_id}/cancel" in paths

def test_job_creation_is_unique_per_scene_and_parcel():
    constraints = {c.name for c in ScimProcessingJob.__table__.constraints}
    assert "uq_scim_job_parcel_scene_provider" in constraints

def test_running_job_cannot_be_cancelled():
    assert JobStatus.cancelled not in ALLOWED[JobStatus.running]

def test_cancelled_job_cannot_be_requeued():
    assert not ALLOWED[JobStatus.cancelled]

def test_job_read_routes_registered():
    paths = app.openapi()["paths"]
    assert "/api/v1/scim/jobs" in paths
    assert "/api/v1/scim/jobs/{job_id}" in paths

def test_job_list_pagination_constraints():
    operation = app.openapi()["paths"]["/api/v1/scim/jobs"]["get"]
    params = {p["name"]: p["schema"] for p in operation["parameters"]}
    assert params["limit"]["maximum"] == 100
    assert params["limit"]["minimum"] == 1
    assert params["offset"]["minimum"] == 0
