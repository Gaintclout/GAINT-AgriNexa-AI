"""Synthetic offline parcel-window planning tests."""
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from app.scim_cog_window_plan import plan_parcel_window

def create_raster(root):
    with rasterio.open(root / "band.tif", "w", driver="GTiff", width=20,
                       height=20, count=1, dtype="uint16", crs="EPSG:4326",
                       transform=from_origin(80, 20, .01, .01)) as dst:
        dst.write(np.ones((20, 20), dtype="uint16"), 1)

def parcel(x0=80.05, y0=19.85, x1=80.10, y1=19.90):
    return {"type": "Polygon", "coordinates": [[
        [x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]}

def test_bounded_window(tmp_path):
    create_raster(tmp_path)
    plan = plan_parcel_window(tmp_path, "band.tif", parcel(), margin_pixels=0)
    assert plan["pixels"] <= 36
    assert plan["width"] > 0 and plan["height"] > 0
    assert plan["network_access"] is False
    assert plan["pixel_data_read"] is False
    assert plan["checksum_verified"] is False

def test_distant_parcel_rejected(tmp_path):
    create_raster(tmp_path)
    with pytest.raises(ValueError, match="intersect"):
        plan_parcel_window(tmp_path, "band.tif", parcel(81, 18, 81.1, 18.1))

def test_invalid_margin_rejected(tmp_path):
    create_raster(tmp_path)
    with pytest.raises(ValueError, match="margin"):
        plan_parcel_window(tmp_path, "band.tif", parcel(), margin_pixels=100)

def test_untrusted_path_rejected(tmp_path):
    create_raster(tmp_path)
    with pytest.raises(ValueError):
        plan_parcel_window(tmp_path, "../band.tif", parcel())

def test_invalid_geometry_rejected(tmp_path):
    create_raster(tmp_path)
    with pytest.raises(ValueError, match="polygon"):
        plan_parcel_window(tmp_path, "band.tif", {"type": "Point", "coordinates": [80, 20]})
