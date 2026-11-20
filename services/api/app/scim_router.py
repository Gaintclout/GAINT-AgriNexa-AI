"""SCIM scene quality preview for authorized GIS and ML operators."""
from fastapi import APIRouter, Depends, HTTPException, Query
from .authorization import require_active_roles
from .scim_contracts import SceneCandidate, SceneAssessment, SatelliteProvider, assess_scene
from .security import Principal, Role
from .scim_indices import ReflectanceSample, SpectralIndices, calculate_indices
from .scim_bands import SensorBandSample, calculate_sensor_indices
from .scim_catalog import CatalogSearch, build_stac_search
from .scim_discovery import CatalogResults, CatalogUnavailable, discover_scenes
from .scim_asset_review import review_assets
from .scim_ranking import rank_scenes
from .scim_parcel_summary import ParcelSummaryRequest, ParcelSpectralSummary, summarize_parcel
from .scim_processing_stages import processing_stages
from .scim_plan import PlanRequest, preview_plan
from .database import session_factory
from .scim_job_store import create_planned_job, change_job_status, get_job, list_jobs
from .scim_jobs import JobStatus
from .scim_job_models import ScimProcessingJob
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/scim", tags=["scim"])

@router.post("/scenes/assess", response_model=SceneAssessment)
def assess_scene_candidate(
    candidate: SceneCandidate,
    max_cloud_percent: float = Query(default=30, ge=0, le=100),
    _: Principal = Depends(require_active_roles(Role.admin, Role.gis_operator, Role.ml_team)),
):
    """Evaluate scene metadata; does not ingest, process or store imagery."""
    return assess_scene(candidate, max_cloud_percent)

@router.post("/indices/calculate", response_model=SpectralIndices)
def calculate_sample_indices(
    sample: ReflectanceSample,
    _: Principal = Depends(require_active_roles(Role.admin, Role.gis_operator, Role.ml_team)),
):
    """Calculate indices for calibrated reflectance inputs, without storing imagery."""
    return calculate_indices(sample)

@router.post("/indices/from-bands", response_model=SpectralIndices)
def calculate_band_indices(
    sample: SensorBandSample,
    _: Principal = Depends(require_active_roles(Role.admin, Role.gis_operator, Role.ml_team)),
):
    """Interpret already-calibrated Sentinel/Landsat reflectance band samples."""
    return calculate_sensor_indices(sample)

@router.post("/catalog/search-preview")
def preview_catalog_search(
    search: CatalogSearch,
    _: Principal = Depends(require_active_roles(Role.admin, Role.gis_operator, Role.ml_team)),
):
    """Return a STAC search request preview; no outbound catalog request is made."""
    return build_stac_search(search)

@router.post("/catalog/discover", response_model=CatalogResults)
def discover_catalog_scenes(
    search: CatalogSearch,
    _: Principal = Depends(require_active_roles(Role.admin, Role.gis_operator, Role.ml_team)),
):
    """Read public STAC scene metadata; no asset download or persistence."""
    try:
        return discover_scenes(search)
    except CatalogUnavailable as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

class AssetReviewRequest(BaseModel):
    provider: SatelliteProvider
    assets: dict[str, dict] = Field(max_length=100)

@router.post("/assets/review")
def review_scene_assets(
    request: AssetReviewRequest,
    _: Principal = Depends(require_active_roles(Role.admin, Role.gis_operator, Role.ml_team)),
):
    """Review STAC asset metadata only; no network or file operations."""
    return review_assets(request.provider, request.assets)

@router.post("/catalog/discover-ranked", response_model=CatalogResults)
def discover_ranked_scenes(
    search: CatalogSearch,
    _: Principal = Depends(require_active_roles(Role.admin, Role.gis_operator, Role.ml_team)),
):
    """Discover and prioritize scene metadata; does not ingest imagery."""
    try:
        results = discover_scenes(search)
    except CatalogUnavailable as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return results.model_copy(update={"scenes": rank_scenes(results)})

@router.post("/parcels/summarize-samples", response_model=ParcelSpectralSummary)
def summarize_parcel_samples(
    request: ParcelSummaryRequest,
    _: Principal = Depends(require_active_roles(Role.admin, Role.gis_operator, Role.ml_team)),
):
    """Summarize supplied clear-pixel reflectance samples without ingesting imagery."""
    return summarize_parcel(request)

@router.get('/processing/stages')
def get_processing_stages(
    _: Principal = Depends(require_active_roles(Role.admin, Role.gis_operator, Role.ml_team)),
):
    return {'stages': processing_stages(), 'execution_enabled': False}

@router.post("/processing/preview")
def preview_processing_plan(
    request: PlanRequest,
    _: Principal = Depends(require_active_roles(Role.admin, Role.gis_operator, Role.ml_team)),
):
    """Validate processing readiness without scheduling or downloading anything."""
    return preview_plan(request)

def job_response(job: ScimProcessingJob) -> dict:
    return {"job_id": job.id, "parcel_id": job.parcel_id, "scene_id": job.scene_id,
            "provider": job.provider, "status": job.status,
            "created_at": job.created_at, "updated_at": job.updated_at,
            "execution_enabled": False}

@router.post("/jobs/plan")
def create_scim_job(
    request: PlanRequest,
    _: Principal = Depends(require_active_roles(Role.admin, Role.gis_operator, Role.ml_team)),
):
    """Persist an idempotent planned job; does not enqueue processing."""
    with session_factory()() as db:
        try:
            job, created = create_planned_job(db, request)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {**job_response(job), "created": created}

@router.post("/jobs/{job_id}/cancel")
def cancel_scim_job(
    job_id: str,
    _: Principal = Depends(require_active_roles(Role.admin, Role.gis_operator, Role.ml_team)),
):
    """Cancel a planned or queued job; terminal and running jobs cannot be cancelled."""
    with session_factory()() as db:
        try:
            job = change_job_status(db, job_id, JobStatus.cancelled)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return job_response(job)

@router.get("/jobs")
def list_scim_jobs(
    parcel_id: str | None = Query(default=None, min_length=1, max_length=36),
    status: JobStatus | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: Principal = Depends(require_active_roles(Role.admin, Role.gis_operator, Role.ml_team)),
):
    """List job metadata; no processing is triggered."""
    with session_factory()() as db:
        jobs = list_jobs(db, parcel_id=parcel_id, status=status, limit=limit, offset=offset)
        return {"items": [job_response(job) for job in jobs],
                "limit": limit, "offset": offset}

@router.get("/jobs/{job_id}")
def get_scim_job(
    job_id: str,
    _: Principal = Depends(require_active_roles(Role.admin, Role.gis_operator, Role.ml_team)),
):
    """Read the status of a single SCIM processing job."""
    with session_factory()() as db:
        job = get_job(db, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return job_response(job)
