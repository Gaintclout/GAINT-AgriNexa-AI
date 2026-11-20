"""Offline parcel-to-pixel planning tests."""
import pytest
from app.scim_cog_parcel_window import plan_parcel_pixel_window
from app.scim_cog_range_fetch import RangeFetchError

GRID = {"width": 512, "height": 512, "tile_width": 256, "tile_height": 256,
        "tile_columns": 2, "tiles": [
            {"index": i, "row": i//2, "column": i%2, "byte_count": 10}
            for i in range(4)]}
TRANSFORM = (.001, 0, 80, 0, -.001, 20)
PARCEL = {"type": "Polygon", "coordinates": [[
    [80.25, 19.75], [80.27, 19.75], [80.27, 19.73],
    [80.25, 19.73], [80.25, 19.75]]]}

def plan(parcel=PARCEL, transform=TRANSFORM, crs="EPSG:4326", margin=0):
    return plan_parcel_pixel_window(GRID, parcel, transform=transform,
                                    crs=crs, margin_pixels=margin)

def test_parcel_crosses_four_tiles():
    result = plan()
    assert result["tile_indices"] == [0, 1, 2, 3]
    assert result["pixel_window"]["width"] == 20
    assert result["georeferencing_verified_from_tiff"] is False

def test_outside_parcel_rejected():
    outside = {"type": "Polygon", "coordinates": [[
        [90, 30], [91, 30], [91, 29], [90, 29], [90, 30]]]}
    with pytest.raises(RangeFetchError, match="overlap"):
        plan(outside)

def test_untrusted_crs_rejected():
    with pytest.raises(RangeFetchError, match="EPSG"):
        plan(crs="EPSG:3857")

def test_rotated_grid_rejected():
    with pytest.raises(RangeFetchError, match="north-up"):
        plan(transform=(.001, .1, 80, 0, -.001, 20))

def test_unclosed_polygon_rejected():
    bad = {"type": "Polygon", "coordinates": [[
        [80, 20], [80.1, 20], [80.1, 19.9], [80, 19.9]]]}
    with pytest.raises(RangeFetchError, match="unclosed"):
        plan(bad)

def test_excessive_window_rejected():
    large = {"type": "Polygon", "coordinates": [[
        [80, 20], [80.5, 20], [80.5, 19.5], [80, 19.5], [80, 20]]]}
    with pytest.raises(RangeFetchError, match="pixel budget"):
        plan(large)

def test_margin_must_be_bounded():
    with pytest.raises(RangeFetchError, match="margin"):
        plan(margin=17)
