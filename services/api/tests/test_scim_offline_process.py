"""End-to-end offline SCIM processing and fail-closed cleanup regression tests."""
import json
from hashlib import sha256
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from app import scim_offline_process as processing
from app.scim_scene_manifest import StagedSceneManifest, verify_staged_manifest

PARCEL = {"type": "Polygon", "coordinates": [[[80, 20], [80.02, 20],
          [80.02, 19.98], [80, 19.98], [80, 20]]]}

def scene(tmp_path):
    source, output = tmp_path / "source", tmp_path / "output"
    source.mkdir()
    output.mkdir()
    assets = {}
    for key, value in {"qa": 64, "SR_B4": 10000, "SR_B5": 20000,
                       "SR_B3": 15000, "SR_B6": 12000}.items():
        path = source / (key + ".tif")
        with rasterio.open(path, "w", driver="GTiff", width=4, height=4,
                           count=1, dtype="uint16", crs="EPSG:4326",
                           transform=from_origin(80, 20, .01, .01)) as dst:
            dst.write(np.full((4, 4), value, dtype="uint16"), 1)
        assets[key] = {"filename": path.name, "sha256": sha256(path.read_bytes()).hexdigest()}
    manifest = StagedSceneManifest(provider="landsat-8", scene_id="OFFLINE-TEST",
                                   qa=assets.pop("qa"), bands=assets)
    return source, output, manifest

def test_end_to_end_generates_verified_manifest_and_report(tmp_path):
    source, output, manifest = scene(tmp_path)
    result = processing.process_local_scene(source, manifest, PARCEL, output, margin_pixels=0)
    saved = StagedSceneManifest.model_validate_json((output / "cropped-manifest.json").read_text())
    verify_staged_manifest(output, saved)
    report = json.loads((output / "validation-report.json").read_text())
    assert report == result
    assert report["summary"]["valid_pixels"] > 0
    assert report["summary"]["ndvi_median"] == pytest.approx(.647059, abs=1e-6)
    assert report["preflight"]["preflight_passed"]
    assert report["extraction"]["output_checksum_verified"]
    assert report["provenance_verified"] is False
    assert report["extraction"]["network_access"] is False

def test_corrupt_source_leaves_output_empty(tmp_path):
    source, output, manifest = scene(tmp_path)
    (source / "SR_B4.tif").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="checksum"):
        processing.process_local_scene(source, manifest, PARCEL, output)
    assert list(output.iterdir()) == []

def test_invalid_parcel_leaves_output_empty(tmp_path):
    source, output, manifest = scene(tmp_path)
    with pytest.raises(ValueError, match="polygon"):
        processing.process_local_scene(source, manifest,
                                       {"type": "Point", "coordinates": [80, 20]}, output)
    assert list(output.iterdir()) == []

def test_report_failure_removes_only_generated_files(tmp_path, monkeypatch):
    source, output, manifest = scene(tmp_path)
    original = processing.write_validation_report
    def fail_on_manifest(path, payload):
        if path.name == "cropped-manifest.json":
            (output / "unrelated.txt").write_text("preserve")
            raise OSError("simulated report failure")
        return original(path, payload)
    monkeypatch.setattr(processing, "write_validation_report", fail_on_manifest)
    with pytest.raises(OSError, match="simulated"):
        processing.process_local_scene(source, manifest, PARCEL, output)
    assert (output / "unrelated.txt").read_text() == "preserve"
    assert sorted(p.name for p in output.iterdir()) == ["unrelated.txt"]

def test_nonempty_output_refused_without_changes(tmp_path):
    source, output, manifest = scene(tmp_path)
    (output / "unrelated.txt").write_text("preserve")
    with pytest.raises(ValueError, match="empty"):
        processing.process_local_scene(source, manifest, PARCEL, output)
    assert (output / "unrelated.txt").read_text() == "preserve"
