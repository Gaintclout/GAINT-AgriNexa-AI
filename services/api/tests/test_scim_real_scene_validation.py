"""SCIM real-scene validation tests using synthetic local rasters."""
from hashlib import sha256
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from app.scim_real_scene_validation import validate_scene
from app.scim_scene_manifest import StagedSceneManifest

def test_offline_validation_with_approved_manifest(tmp_path):
    names = {"qa": 64, "SR_B4": 10000, "SR_B5": 20000,
             "SR_B3": 15000, "SR_B6": 12000}
    assets = {}
    for name, value in names.items():
        filename = name + ".tif"
        with rasterio.open(tmp_path / filename, "w", driver="GTiff",
                           width=2, height=2, count=1, dtype="uint16",
                           crs="EPSG:4326", transform=from_origin(80, 20, .01, .01),
                           nodata=0) as dst:
            dst.write(np.full((2, 2), value, dtype="uint16"), 1)
        assets[name] = {"filename": filename,
                        "sha256": sha256((tmp_path / filename).read_bytes()).hexdigest()}
    manifest = StagedSceneManifest(provider="landsat-8", scene_id="approved-scene",
        qa=assets["qa"], bands={key: value for key, value in assets.items() if key != "qa"})
    polygon = {"type": "Polygon", "coordinates": [[
        [80, 20], [80.02, 20], [80.02, 19.99], [80, 19.99], [80, 20]]]}
    result = validate_scene(tmp_path, manifest, polygon)
    assert result["valid_pixels"] == 2
    assert result["ndvi_median"] == pytest.approx(.647059, abs=1e-6)
    (tmp_path / "SR_B4.tif").write_bytes(b"changed")
    with pytest.raises(ValueError, match="checksum"):
        validate_scene(tmp_path, manifest, polygon)
