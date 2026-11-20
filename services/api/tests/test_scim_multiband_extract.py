"""Synthetic multi-band crop tests; no network or real imagery."""
from hashlib import sha256
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from app.scim_multiband_extract import extract_staged_scene
from app.scim_scene_manifest import StagedSceneManifest, verify_staged_manifest
from app.scim_real_scene_validation import validate_scene

PARCEL = {"type": "Polygon", "coordinates": [[[80, 20], [80.02, 20],
          [80.02, 19.98], [80, 19.98], [80, 20]]]}

def setup_scene(tmp_path):
    source, output = tmp_path / "source", tmp_path / "output"
    source.mkdir()
    output.mkdir()
    assets = {}
    for name, value in {"qa": 64, "SR_B4": 10000, "SR_B5": 20000,
                        "SR_B3": 15000, "SR_B6": 12000}.items():
        path = source / (name + ".tif")
        with rasterio.open(path, "w", driver="GTiff", width=4, height=4,
                           count=1, dtype="uint16", crs="EPSG:4326",
                           transform=from_origin(80, 20, .01, .01)) as dst:
            dst.write(np.full((4, 4), value, dtype="uint16"), 1)
        assets[name] = {"filename": path.name, "sha256": sha256(path.read_bytes()).hexdigest()}
    manifest = StagedSceneManifest(provider="landsat-8", scene_id="TEST",
        qa=assets.pop("qa"), bands=assets)
    return source, output, manifest

def test_crop_manifest_runs_existing_index_pipeline(tmp_path):
    source, output, manifest = setup_scene(tmp_path)
    result = extract_staged_scene(source, manifest, PARCEL, output, margin_pixels=0)
    cropped = StagedSceneManifest.model_validate(result["manifest"])
    verify_staged_manifest(output, cropped)
    summary = validate_scene(output, cropped, PARCEL)
    assert summary["valid_pixels"] > 0
    assert summary["ndvi_median"] == pytest.approx(.647059, abs=1e-6)
    assert result["provenance_verified"] is False

def test_tampered_source_blocks_all_crops(tmp_path):
    source, output, manifest = setup_scene(tmp_path)
    (source / "SR_B4.tif").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="checksum"):
        extract_staged_scene(source, manifest, PARCEL, output)
    assert list(output.iterdir()) == []

def test_nonempty_output_rejected(tmp_path):
    source, output, manifest = setup_scene(tmp_path)
    (output / "existing.txt").write_text("keep")
    with pytest.raises(ValueError, match="empty"):
        extract_staged_scene(source, manifest, PARCEL, output)
    assert (output / "existing.txt").read_text() == "keep"
