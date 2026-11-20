"""SCIM job metadata schema checks; does not require a live database."""
from app.database import Base
from app import scim_job_models

def test_scim_job_table_registered():
    table = Base.metadata.tables["scim_processing_jobs"]
    assert {"id", "parcel_id", "scene_id", "provider", "status", "created_at", "updated_at"} <= set(table.columns.keys())
    assert len(table.foreign_keys) == 1
    assert next(iter(table.foreign_keys)).target_fullname == "parcels.id"

def test_scim_job_constraints_present():
    table = Base.metadata.tables["scim_processing_jobs"]
    names = {constraint.name for constraint in table.constraints}
    assert "uq_scim_job_parcel_scene_provider" in names
    assert "ck_scim_job_status" in names
