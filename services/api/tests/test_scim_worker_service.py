"""SCIM worker integration tests without database or satellite network."""
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import pytest
from app.scim_worker_service import run_worker_cycle, process_approved_claim
from app.scim_scene_manifest import StagedSceneManifest

class DB:
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def get(self, model, job_id):
        return SimpleNamespace(scene_id="scene-a", provider="landsat-8",
            status="running", lease_owner="worker", lease_token="secret",
            lease_expires_at=datetime.now(timezone.utc) + timedelta(minutes=5))

def session_factory():
    return DB()

def test_cycle_without_queued_job(tmp_path):
    with patch("app.scim_worker_service.run_scheduler_tick",
               return_value=SimpleNamespace(requeued=1, exhausted=2, claim=None)):
        result = run_worker_cycle(session_factory, owner="worker", root=tmp_path,
                                  manifest_loader=lambda _: None)
    assert result == {"requeued": 1, "exhausted": 2, "processed": False}

def test_cycle_rejects_unapproved_manifest_and_marks_failed(tmp_path):
    with patch("app.scim_worker_service.run_scheduler_tick",
               return_value=SimpleNamespace(requeued=0, exhausted=0,
                                            claim=("job-a", "secret"))), patch(
        "app.scim_worker_service.complete_with_lease") as complete:
        with pytest.raises(ValueError, match="manifest"):
            run_worker_cycle(session_factory, owner="worker", root=tmp_path,
                             manifest_loader=lambda _: None)
    complete.assert_called_once()

def test_cycle_processes_approved_manifest(tmp_path):
    manifest = StagedSceneManifest(
        provider="landsat-8", scene_id="scene-a",
        qa={"filename": "qa.tif", "sha256": "0" * 64},
        bands={band: {"filename": band+".tif", "sha256": "0" * 64}
               for band in ("SR_B4", "SR_B5", "SR_B3", "SR_B6")})
    with patch("app.scim_worker_service.run_scheduler_tick",
               return_value=SimpleNamespace(requeued=0, exhausted=0,
                                            claim=("job-a", "secret"))), patch(
        "app.scim_worker_service.process_approved_claim",
        return_value={"valid_pixels": 1}) as process:
        result = run_worker_cycle(session_factory, owner="worker", root=tmp_path,
                                  manifest_loader=lambda _: manifest)
    assert result["summary"]["valid_pixels"] == 1
    process.assert_called_once()

def test_claim_rejects_mismatched_scene(tmp_path):
    manifest = StagedSceneManifest(
        provider="landsat-8", scene_id="other-scene",
        qa={"filename": "qa.tif", "sha256": "0" * 64},
        bands={band: {"filename": band+".tif", "sha256": "0" * 64}
               for band in ("SR_B4", "SR_B5", "SR_B3", "SR_B6")})
    with pytest.raises(ValueError, match="match"):
        process_approved_claim(session_factory, "job-a", "worker", "secret",
                               tmp_path, manifest)

def test_expired_lease_rejected_before_file_verification(tmp_path):
    class ExpiredDB(DB):
        def get(self, model, job_id):
            job = super().get(model, job_id)
            job.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            return job
    manifest = StagedSceneManifest(
        provider="landsat-8", scene_id="scene-a",
        qa={"filename": "qa.tif", "sha256": "0" * 64},
        bands={band: {"filename": band+".tif", "sha256": "0" * 64}
               for band in ("SR_B4", "SR_B5", "SR_B3", "SR_B6")})
    with patch("app.scim_worker_service.verify_staged_manifest") as verify:
        with pytest.raises(ValueError, match="lease"):
            process_approved_claim(lambda: ExpiredDB(), "job-a", "worker", "secret",
                                   tmp_path, manifest)
    verify.assert_not_called()
