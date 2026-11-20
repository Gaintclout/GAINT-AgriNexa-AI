"""Offline mocked remote parcel plan integration tests."""
import pytest
from app import scim_cog_remote_parcel_plan as module
from app.scim_cog_range_fetch import RangeFetchError

URL = "https://sentinel-cogs.s3.us-west-2.amazonaws.com/sample.tif"
PARCEL = {"type": "Polygon", "coordinates": [[
    [80.25, 19.75], [80.27, 19.75], [80.27, 19.73],
    [80.25, 19.73], [80.25, 19.75]]]}

def install(monkeypatch, *, crs="EPSG:4326"):
    calls = []
    def grid(*args, **kwargs):
        calls.append("grid")
        return {"crs": crs, "transform": (.001, 0, 80, 0, -.001, 20)}
    def table(*args, **kwargs):
        calls.append("table")
        return {"width": 512, "height": 512, "tile_width": 256,
                "tile_height": 256, "tile_columns": 2,
                "tile_ranges_verified": True,
                "tiles": [{"index": i, "row": i // 2, "column": i % 2,
                           "byte_count": 100} for i in range(4)]}
    monkeypatch.setattr(module, "inspect_remote_geotiff_grid", grid)
    monkeypatch.setattr(module, "inspect_remote_tile_table", table)
    return calls

def test_remote_parcel_plan_selects_four_tiles(monkeypatch):
    calls = install(monkeypatch)
    result = module.plan_remote_parcel_tiles(URL, PARCEL, approved=True,
                                             margin_pixels=0)
    assert calls == ["grid", "table"]
    assert result["tile_indices"] == [0, 1, 2, 3]
    assert result["pixel_window"]["width"] == 20
    assert result["tile_payload_downloaded"] is False
    assert result["source_authenticated"] is False

def test_approval_required_before_remote_probes(monkeypatch):
    calls = install(monkeypatch)
    with pytest.raises(RangeFetchError, match="approval"):
        module.plan_remote_parcel_tiles(URL, PARCEL)
    assert calls == []

def test_unsupported_crs_rejected(monkeypatch):
    install(monkeypatch, crs="EPSG:32644")
    with pytest.raises(RangeFetchError, match="CRS"):
        module.plan_remote_parcel_tiles(URL, PARCEL, approved=True)

def test_invalid_parcel_rejected(monkeypatch):
    install(monkeypatch)
    with pytest.raises(RangeFetchError, match="Polygon"):
        module.plan_remote_parcel_tiles(URL, {"type": "Point"}, approved=True)

def test_window_budget_rejected(monkeypatch):
    install(monkeypatch)
    large = {"type": "Polygon", "coordinates": [[
        [80, 20], [80.5, 20], [80.5, 19.5], [80, 19.5], [80, 20]]]}
    with pytest.raises(RangeFetchError, match="pixel budget"):
        module.plan_remote_parcel_tiles(URL, large, approved=True)
