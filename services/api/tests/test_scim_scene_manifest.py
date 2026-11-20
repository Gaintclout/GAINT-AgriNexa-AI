"""Offline SCIM manifest integrity tests."""
from hashlib import sha256
import pytest
from pydantic import ValidationError
from app.scim_scene_manifest import StagedSceneManifest, verify_staged_manifest

BANDS = ("SR_B4", "SR_B5", "SR_B3", "SR_B6")

def manifest(root):
    items = {}
    for name in ("qa", *BANDS):
        payload = ("raster-" + name).encode()
        filename = name + ".tif"
        (root / filename).write_bytes(payload)
        items[name] = {"filename": filename, "sha256": sha256(payload).hexdigest()}
    return StagedSceneManifest(provider="landsat-8", scene_id="scene-1",
        qa=items["qa"], bands={name: items[name] for name in BANDS})

def test_manifest_verifies_all_staged_files(tmp_path):
    data = manifest(tmp_path)
    paths = verify_staged_manifest(tmp_path, data)
    assert set(paths) == {"qa", *BANDS}

def test_manifest_detects_modified_file(tmp_path):
    data = manifest(tmp_path)
    (tmp_path / "SR_B4.tif").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="checksum"):
        verify_staged_manifest(tmp_path, data)

def test_manifest_requires_all_bands(tmp_path):
    data = manifest(tmp_path)
    with pytest.raises(ValidationError, match="required sensor bands"):
        StagedSceneManifest(provider="landsat-8", scene_id="scene-1",
            qa=data.qa, bands={"SR_B4": data.bands["SR_B4"]})

def test_manifest_rejects_reused_filenames(tmp_path):
    data = manifest(tmp_path)
    with pytest.raises(ValidationError, match="reuse"):
        StagedSceneManifest(provider="landsat-8", scene_id="scene-1",
            qa=data.qa, bands={**data.bands, "SR_B4": data.qa})
