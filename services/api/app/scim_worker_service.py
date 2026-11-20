"""Operator-controlled SCIM worker loop.

Run only with a disposable or explicitly approved database and staged imagery.
Every job requires an independently approved checksum manifest. No automatic
download, no web API, no background startup at import time.
"""
import logging
import time
from datetime import datetime, timezone
from threading import Event
from pathlib import Path
from sqlalchemy.orm import sessionmaker
from .scim_scheduler_tick import run_scheduler_tick
from .scim_scene_manifest import StagedSceneManifest, verify_staged_manifest
from .scim_staged_worker import process_staged_job, _verify_lease
from .scim_lease_store import complete_with_lease
from .scim_lease_heartbeat import LeaseHeartbeat

LOG = logging.getLogger(__name__)

def process_approved_claim(session_factory, job_id: str, owner: str, token: str,
                           root: Path, manifest: StagedSceneManifest):
    """Verify all staged bands and bind the manifest to the claimed scene."""
    from .scim_job_models import ScimProcessingJob
    with session_factory() as db:
        job = db.get(ScimProcessingJob, job_id)
        _verify_lease(job, owner, token, datetime.now(timezone.utc))
        if job.scene_id != manifest.scene_id or job.provider != manifest.provider.value:
            raise ValueError("Manifest does not match claimed SCIM job")
    verify_staged_manifest(root, manifest)
    with LeaseHeartbeat(session_factory, job_id, owner, token):
        return process_staged_job(
            session_factory, job_id, owner, token, root,
            manifest.qa.filename,
            {key: value.filename for key, value in manifest.bands.items()},
            sentinel_quantification=manifest.sentinel_quantification,
            sentinel_offsets=manifest.sentinel_offsets,
        )

def run_worker_cycle(session_factory, *, owner: str, root: Path,
                     manifest_loader, recovery_limit: int = 50):
    """Process at most one job. Missing manifests leave the job failed, not stuck."""
    tick = run_scheduler_tick(session_factory, owner=owner, claim=True,
                              recovery_limit=recovery_limit)
    if tick.claim is None:
        return {"requeued": tick.requeued, "exhausted": tick.exhausted,
                "processed": False}
    job_id, token = tick.claim
    try:
        manifest = manifest_loader(job_id)
        if not isinstance(manifest, StagedSceneManifest):
            raise ValueError("Approved SCIM scene manifest required")
        summary = process_approved_claim(session_factory, job_id, owner, token,
                                         root, manifest)
        LOG.info("SCIM job succeeded: %s", job_id)
        return {"requeued": tick.requeued, "exhausted": tick.exhausted,
                "processed": True, "job_id": job_id, "summary": summary}
    except Exception:
        LOG.exception("SCIM job failed: %s", job_id)
        try:
            with session_factory() as db:
                complete_with_lease(db, job_id, owner, token, success=False)
        except (LookupError, ValueError):
            LOG.warning("SCIM job lease expired or changed before failure marking: %s", job_id)
        raise

def run_worker_forever(session_factory, *, owner: str, root: Path,
                       manifest_loader, interval_seconds: float = 15,
                       stop_event: Event | None = None):
    """Blocking supervised worker loop with cooperative shutdown between jobs.

    A shutdown request does not interrupt an in-progress leased job.
    """
    if not 1 <= interval_seconds <= 300:
        raise ValueError("Polling interval must be between 1 and 300 seconds")
    stop = stop_event if stop_event is not None else Event()
    cycles = 0
    while not stop.is_set():
        try:
            result = run_worker_cycle(session_factory, owner=owner, root=root,
                                      manifest_loader=manifest_loader)
            cycles += 1
            LOG.info("SCIM worker cycle=%d processed=%s recovered=%d exhausted=%d",
                     cycles, result["processed"], result["requeued"], result["exhausted"])
        except Exception:
            LOG.exception("SCIM worker cycle failed")
        if stop.wait(interval_seconds):
            break
