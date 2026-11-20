"""Synthetic local rasters only; never reaches external satellite services."""
from hashlib import sha256
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from app.scim_raster_preflight import preflight_staged_scene
from app.scim_scene_manifest import StagedSceneManifest

PARCEL = {"type": "Polygon", "coordinates": [[[80, 20], [80.02, 20],
          [80.02, 19.98], [80, 19.98], [80, 20]]]}

def prepare(root, *, bad_dtype=False):
    bands = {}
    for name in ("qa", "B04", "B08", "B03", "B11"):
        path = root / (name + ".tif")
        dtype = "float32" if bad_dtype and name == "B04" else "uint16"
        with rasterio.open(path, "w", driver="GTiff", width=2, height=2,
                           count=1, dtype=dtype, crs="EPSG:4326",
                           transform=from_origin(80, 20, .01, .01)) as dst:
            dst.write(np.ones((2, 2), dtype=dtype), 1)
        entry = {"filename": path.name, "sha256": sha256(path.read_bytes()).hexdigest()}
        if name == "qa":
            qa = entry
        else:
            bands[name] = entry
    return StagedSceneManifest(provider="sentinel-2", scene_id="SYNTHETIC_TEST",
                               qa=qa, bands=bands)

def test_valid_preflight(tmp_path):
    manifest = prepare(tmp_path)
    report = preflight_staged_scene(tmp_path, manifest, PARCEL)
    assert report["preflight_passed"]
    assert report["checksum_verified"]
    assert not report["provenance_verified"]
    assert len(report["assets"]) == 5

def test_checksum_tampering_rejected(tmp_path):
    manifest = prepare(tmp_path)
    (tmp_path / "B04.tif").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="checksum"):
        preflight_staged_scene(tmp_path, manifest, PARCEL)

def test_wrong_dtype_rejected(tmp_path):
    manifest = prepare(tmp_path, bad_dtype=True)
    with pytest.raises(ValueError, match="uint16"):
        preflight_staged_scene(tmp_path, manifest, PARCEL)

def test_distant_parcel_rejected(tmp_path):
    manifest = prepare(tmp_path)
    distant = {"type": "Polygon", "coordinates": [[[60, 10], [61, 10],
                [61, 11], [60, 11], [60, 10]]]}
    with pytest.raises(ValueError, match="intersect"):
        preflight_staged_scene(tmp_path, manifest, distant)

def test_invalid_parcel_rejected(tmp_path):
    manifest = prepare(tmp_path)
    with pytest.raises(ValueError, match="polygon"):
        preflight_staged_scene(tmp_path, manifest, {"type": "Point", "coordinates": [80, 20]})
