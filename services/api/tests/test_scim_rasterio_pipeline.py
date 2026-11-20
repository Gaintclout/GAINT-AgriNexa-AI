"""Disposable synthetic GeoTIFF tests; no external imagery or network."""
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from app.scim_rasterio_pipeline import evaluate_staged_scene, _trusted_path

def write_band(root, name, data, transform=None):
    path = root / name
    with rasterio.open(path, "w", driver="GTiff", width=data.shape[1],
                       height=data.shape[0], count=1, dtype="uint16",
                       crs="EPSG:4326", transform=transform or from_origin(80, 20, .01, .01),
                       nodata=0) as dst:
        dst.write(data.astype("uint16"), 1)

def test_staged_scene_clips_and_masks(tmp_path):
    values = {"SR_B4": 10000, "SR_B5": 20000, "SR_B3": 15000, "SR_B6": 12000}
    write_band(tmp_path, "qa.tif", np.array([[64, 8], [64, 64]]))
    for band, value in values.items():
        write_band(tmp_path, band + ".tif", np.full((2, 2), value))
    parcel = {"type": "Polygon", "coordinates": [[
        [80, 20], [80.02, 20], [80.02, 19.99], [80, 19.99], [80, 20]
    ]]}
    result = evaluate_staged_scene(tmp_path, "landsat-8", "qa.tif",
        {band: band + ".tif" for band in values}, parcel)
    assert result.parcel_pixels == 2
    assert result.clear_pixels == 1
    assert result.valid_pixels == 1
    assert result.ndvi_values[0] == pytest.approx(.647059, abs=1e-6)

def test_traversal_rejected(tmp_path):
    (tmp_path / "qa.tif").write_bytes(b"not-a-raster")
    with pytest.raises(ValueError):
        _trusted_path(tmp_path, "../qa.tif")

def test_symlink_rejected(tmp_path):
    target = tmp_path / "real.tif"
    target.write_bytes(b"not-a-raster")
    (tmp_path / "link.tif").symlink_to(target)
    with pytest.raises(ValueError, match="Symlink"):
        _trusted_path(tmp_path, "link.tif")

def test_rejects_non_uint16_source(tmp_path):
    path = tmp_path / "qa.tif"
    with rasterio.open(path, "w", driver="GTiff", width=2, height=1,
            count=1, dtype="float32", crs="EPSG:4326",
            transform=from_origin(80, 20, .01, .01)) as dst:
        dst.write(np.array([[64, 8]], dtype="float32"), 1)
    from app.scim_rasterio_pipeline import _read_band
    with pytest.raises(ValueError, match="uint16"):
        _read_band(tmp_path, "qa.tif")

def test_rejects_control_character_path(tmp_path):
    with pytest.raises(ValueError, match="relative local raster paths"):
        _trusted_path(tmp_path, "bad\\nname.tif")
