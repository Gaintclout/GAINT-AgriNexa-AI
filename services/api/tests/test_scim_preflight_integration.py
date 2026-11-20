"""Integration contract tests: preflight must fail closed before raster evaluation."""
import pytest
from app import scim_real_scene_validation as validation
from app.scim_scene_manifest import StagedSceneManifest

def manifest():
    digest = "a" * 64
    return StagedSceneManifest(provider="sentinel-2", scene_id="TEST_SCENE",
        qa={"filename": "qa.tif", "sha256": digest},
        bands={band: {"filename": band + ".tif", "sha256": digest}
               for band in ("B04", "B08", "B03", "B11")})

def test_preflight_failure_blocks_evaluation(monkeypatch, tmp_path):
    calls = []
    def reject(*args):
        calls.append("preflight")
        raise ValueError("checksum mismatch")
    def evaluate(*args, **kwargs):
        calls.append("evaluation")
        raise AssertionError("must not evaluate")
    monkeypatch.setattr(validation, "preflight_staged_scene", reject)
    monkeypatch.setattr(validation, "evaluate_staged_scene", evaluate)
    with pytest.raises(ValueError, match="checksum"):
        validation.validate_scene(tmp_path, manifest(), {"type": "Polygon"})
    assert calls == ["preflight"]

def test_consolidated_report_has_preflight_and_summary(monkeypatch, tmp_path):
    report = {"preflight_passed": True, "checksum_verified": True}
    summary = {"valid_pixels": 2, "ndvi_median": 0.5}
    monkeypatch.setattr(validation, "preflight_staged_scene", lambda *args: report)
    monkeypatch.setattr(validation, "_evaluate_verified_scene", lambda *args: summary)
    result = validation.validate_scene_report(tmp_path, manifest(), {"type": "Polygon"})
    assert result["preflight"] == report
    assert result["summary"] == summary
    assert result["reference_comparison"] == "not_performed"
    assert result["provenance_verified"] is False

def test_consolidated_report_preflight_runs_once(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(validation, "preflight_staged_scene",
                        lambda *args: calls.append("preflight") or {"preflight_passed": True})
    monkeypatch.setattr(validation, "_evaluate_verified_scene",
                        lambda *args: calls.append("evaluate") or {"valid_pixels": 1})
    validation.validate_scene_report(tmp_path, manifest(), {"type": "Polygon"})
    assert calls == ["preflight", "evaluate"]
