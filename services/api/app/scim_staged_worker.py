"""Explicit SCIM offline worker entrypoint; no daemon or automatic scheduler.

Caller must own a valid database lease and supply administrator-staged GeoTIFFs.
Results and job success are committed atomically with lease-token fencing.
"""
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from sqlalchemy import select
from sqlalchemy.orm import Session
from .scim_job_models import ScimProcessingJob
from .scim_result_models import ScimProcessingResult
from .scim_jobs import JobStatus
from .scim_contracts import SatelliteProvider
from .scim_parcel_geometry import load_parcel_geometry
from .scim_rasterio_pipeline import evaluate_staged_scene

def _verify_lease(job, owner: str, token: str, now: datetime):
    if (job is None or job.status != JobStatus.running.value
            or not token or job.lease_token != token
            or job.lease_owner != owner or job.lease_expires_at is None
            or job.lease_expires_at <= now):
        raise ValueError("Invalid or expired SCIM worker lease")

def _summary(result):
    def med(values):
        return round(median(values), 6) if values else None
    return {
        "parcel_pixels": result.parcel_pixels,
        "clear_pixels": result.clear_pixels,
        "valid_pixels": result.valid_pixels,
        "ndvi_median": med(result.ndvi_values),
        "ndwi_median": med(result.ndwi_values),
        "ndmi_median": med(result.ndmi_values),
    }

def process_staged_job(session_factory, job_id: str, owner: str, token: str,
                       root: Path, qa_filename: str, band_files: dict[str, str],
                       *, sentinel_quantification=None, sentinel_offsets=None):
    """Run one leased job; no network and no side effects if lease is stale."""
    with session_factory() as db:
        job = db.get(ScimProcessingJob, job_id)
        _verify_lease(job, owner, token, datetime.now(timezone.utc))
        provider = SatelliteProvider(job.provider)
        parcel = load_parcel_geometry(db, job.parcel_id)
    result = evaluate_staged_scene(
        root, provider, qa_filename, band_files, parcel,
        sentinel_quantification=sentinel_quantification,
        sentinel_offsets=sentinel_offsets)
    summary = _summary(result)
    with session_factory() as db:
        with db.begin():
            job = db.scalar(select(ScimProcessingJob).where(
                ScimProcessingJob.id == job_id).with_for_update())
            now = datetime.now(timezone.utc)
            _verify_lease(job, owner, token, now)
            if db.get(ScimProcessingResult, job_id) is not None:
                raise ValueError("SCIM result already exists")
            db.add(ScimProcessingResult(job_id=job_id, summary=summary,
                                        created_at=now))
            job.status = JobStatus.succeeded.value
            job.lease_owner = None
            job.lease_token = None
            job.lease_expires_at = None
            job.updated_at = now
    return summary
